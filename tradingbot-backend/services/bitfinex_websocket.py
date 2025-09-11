"""
Bitfinex WebSocket Service - TradingBot Backend

Denna modul hanterar WebSocket-anslutning till Bitfinex för realtids tickdata.
Inkluderar automatisk återanslutning och tickdata-hantering.
"""

import asyncio
import json
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

from websockets.client import connect as ws_connect  # type: ignore[attr-defined]
from websockets.exceptions import ConnectionClosed  # type: ignore[attr-defined]

from config.settings import Settings
from utils.logger import get_logger
from ws.auth import build_ws_auth_payload

# Lazy import i metoder för att undvika cirkulär import

logger = get_logger(__name__)


class BitfinexWebSocketService:
    """Service för WebSocket-anslutning till Bitfinex."""

    def __init__(self):
        self.settings = Settings()
        # Standard: använd auth-URI (api) som bas. Publika subar kan specialhanteras vid behov.
        self.ws_url = getattr(self.settings, "BITFINEX_WS_AUTH_URI", None) or self.settings.BITFINEX_WS_URI
        self.websocket = None
        self.is_connected = False
        self.is_authenticated = False
        self.subscriptions = {}
        self.callbacks = {}
        # OBS: chanId är per‑socket. Använd ws‑namespacing
        self.channel_callbacks = {}
        self.channel_info = {}
        self._chan_callbacks = {}  # (ws, chanId) -> callback
        self._chan_info = {}  # (ws, chanId) -> {channel, symbol, key}
        self.private_event_callbacks = {}
        self.latest_prices = {}  # Spara senaste priser
        self.price_history = {}  # Spara pris-historik för strategi
        self._last_tick_ts = {}  # symbol -> last tick timestamp
        self.latest_ticker_frames = {}  # symbol -> senaste fulla ticker-dict (bid/ask/vol/high/low)
        # Throttle/log-state för strategiutvärdering per symbol
        self._last_eval_ts = {}  # symbol -> senast evaluerad (epoch sek)
        self._last_strategy_signal = {}  # symbol -> senaste signal
        self._last_strategy_reason = {}  # symbol -> senaste reason
        self._last_strategy_log_ts = {}  # symbol -> senast loggad (epoch sek)
        self.strategy_callbacks = {}  # Callbacks för strategiutvärdering
        # Synk-event för auth-ack
        import asyncio as _asyncio

        self._asyncio = _asyncio
        self._auth_event = _asyncio.Event()
        # Aktivitetsspårning och notifiering
        self.active_tickers = set()
        self._live_notified = set()
        # Spåra önskade symboler (rå input) för auto-resubscribe
        self._requested_symbols = set()
        # WS Margin state
        self.margin_base = None  # type: ignore[assignment]
        self.margin_sym: dict[str, list] = {}
        self._last_margin_ts = None  # type: ignore[assignment]
        self._last_margin_sym_ts: dict[str, float] = {}
        # Registrera default-handler för margin info updates (miu)
        self.private_event_callbacks["miu"] = self._handle_miu
        # Periodisk symbol-refresh (configs) loop-task
        self._symbol_refresh_task = None
        self._symbol_refresh_interval = 3600.0

        # Pool för publika sockets (skalning). Index 0 reserveras implicit av self.websocket vid behov.
        self._pool_public: list = []
        self._pool_sub_counts: dict = {}  # ws -> antal subs
        self._pool_enabled: bool = bool(getattr(self.settings, "WS_USE_POOL", True))
        # Spårning av subkey -> ws/chanId för unsubscribe
        self._sub_socket: dict[str, Any] = {}
        self._chanid_by_subkey: dict[tuple, int] = {}
        self._pool_max_sockets: int = int(getattr(self.settings, "WS_PUBLIC_SOCKETS_MAX", 3))
        self._pool_max_subs: int = int(getattr(self.settings, "WS_MAX_SUBS_PER_SOCKET", 200))

        # Heartbeat/ping & reconnect state
        self._last_msg_ts: float = 0.0
        self._ping_task = None
        self._hb_task = None
        self._reconnecting: bool = False
        # Konfig med default
        try:
            self._ping_interval = float(getattr(self.settings, "WS_PING_INTERVAL_SEC", 20.0) or 20.0)
            self._hb_timeout = float(getattr(self.settings, "WS_HEARTBEAT_TIMEOUT_SEC", 60.0) or 60.0)
        except Exception:
            self._ping_interval = 20.0
            self._hb_timeout = 60.0

        # Spåra candles-subs för auto-resubscribe
        self._requested_candles: dict[tuple[str, str], Callable] = {}

    async def _get_public_socket(self):
        """
        Hämta en lämplig public‑socket att sub:a på, skapa ny vid behov.
        """
        try:
            if not self._pool_enabled:
                # Använd huvudsocket
                if not self.is_connected:
                    await self.connect()
                return self.websocket
            # Rensa döda sockets
            self._pool_public = [ws for ws in self._pool_public if ws and not ws.closed]
            # Välj socket med minst subs
            best = None
            best_cnt = 1 << 30
            for ws in self._pool_public:
                cnt = int(self._pool_sub_counts.get(ws, 0))
                if cnt < best_cnt:
                    best = ws
                    best_cnt = cnt
            # Skapa ny om ingen finns eller om alla passerat gräns och vi kan skala ut
            if best is None or (best_cnt >= self._pool_max_subs and len(self._pool_public) < self._pool_max_sockets):
                # öppna ny public‑socket
                ws = await self._open_public_socket()
                if ws:
                    self._pool_public.append(ws)
                    self._pool_sub_counts[ws] = 0
                    best = ws
                    best_cnt = 0
            # Säkerställ minst en socket
            if best is None:
                ws = await self._open_public_socket()
                if ws:
                    self._pool_public.append(ws)
                    self._pool_sub_counts[ws] = 0
                    best = ws
            return best
        except Exception:
            # Fallback till huvudsocket
            if not self.is_connected:
                await self.connect()
            return self.websocket

    async def _open_public_socket(self):
        try:
            import time as _t

            uri = getattr(self.settings, "BITFINEX_WS_PUBLIC_URI", None) or self.settings.BITFINEX_WS_URI
            _t0 = _t.perf_counter()
            ws = await ws_connect(uri)
            _t1 = _t.perf_counter()
            asyncio.create_task(self._listen_loop(ws))
            logger.info("🧩 Öppnade ny public WS socket (%.0f ms)", (_t1 - _t0) * 1000)
            return ws
        except Exception as e:
            logger.warning("Kunde inte öppna public socket: %s", e)
            return None

    def get_pool_status(self) -> dict[str, Any]:
        """Returnerar status för WS‑pool och huvudsocket."""
        try:
            sockets = []
            for idx, ws in enumerate(self._pool_public):
                try:
                    sockets.append(
                        {
                            "index": idx,
                            "subs": int(self._pool_sub_counts.get(ws, 0)),
                            "closed": bool(getattr(ws, "closed", False)),
                        }
                    )
                except Exception:
                    sockets.append({"index": idx, "subs": 0, "closed": True})
            totals = {"ticker": 0, "trades": 0, "candles": 0, "book": 0}
            subs_list: list[str] = []
            try:
                for key in list(self.subscriptions.keys()):
                    subs_list.append(str(key))
                    if key.startswith("ticker|"):
                        totals["ticker"] += 1
                    elif key.startswith("trades|"):
                        totals["trades"] += 1
                    elif key.startswith("candles|"):
                        totals["candles"] += 1
                    elif key.startswith("book|"):
                        totals["book"] += 1
            except Exception:
                pass
            import time as _t

            now = _t.time()
            return {
                "pool_enabled": bool(self._pool_enabled),
                "pool_max_sockets": int(self._pool_max_sockets),
                "pool_max_subs": int(self._pool_max_subs),
                "pool_sockets": sockets,
                "totals": totals,
                "subscriptions": subs_list,
                "main": {
                    "connected": bool(self.is_connected),
                    "authenticated": bool(self.is_authenticated),
                    "ping_interval_sec": float(getattr(self, "_ping_interval", 0.0) or 0.0),
                    "hb_timeout_sec": float(getattr(self, "_hb_timeout", 0.0) or 0.0),
                    "last_msg_ts": float(self._last_msg_ts or 0.0),
                    "last_msg_age_sec": float((now - float(self._last_msg_ts)) if self._last_msg_ts else -1.0),
                },
            }
        except Exception:
            return {
                "pool_enabled": bool(self._pool_enabled),
                "pool_sockets": [],
                "totals": {},
                "main": {
                    "connected": bool(self.is_connected),
                    "authenticated": bool(self.is_authenticated),
                },
            }

    async def _listen_loop(self, ws):
        try:
            async for message in ws:
                try:
                    data = json.loads(message)
                    # Markera aktuell ws för chanId‑routning
                    self._current_incoming_ws = ws
                    # Vi återanvänder channel‑callbacks från huvudobjektet; Bitfinex skickar chanId per socket.
                    if isinstance(data, list) and len(data) > 1:
                        await self._handle_channel_message(data)
                    elif isinstance(data, dict):
                        await self._handle_event_message(data)
                except Exception as e:
                    logger.debug("Pool socket parse fel: %s", e)
                finally:
                    try:
                        self._current_incoming_ws = None
                    except Exception:
                        pass
        except Exception as e:
            logger.warning("Pool socket stängd: %s", e)

    # Publikt API för andra moduler
    def register_handler(self, event_code: str, callback: Callable[[Any], Any]):
        """Registrera callback för privat kanal 0-event (t.ex. 'ws','wu','ps','pu','on','oc','te','tu','auth')."""
        self.private_event_callbacks[event_code] = callback

    async def ensure_authenticated(self) -> bool:
        """Säkerställ att WS är ansluten och autentiserad.

        Returns:
            bool: True om ansluten och autentiserad, annars False
        """
        try:
            if not self.is_connected:
                ok = await self.connect()
                if not ok:
                    return False
            if not self.is_authenticated:
                # Försök auth igen och vänta kort på ack
                try:
                    # Nollställ event och försök igen
                    try:
                        self._auth_event.clear()
                    except Exception:
                        pass
                    await self.authenticate()
                    await self._asyncio.wait_for(self._auth_event.wait(), timeout=5)
                except Exception:
                    pass
            return bool(self.is_connected and self.is_authenticated)
        except Exception:
            return False

    # --- Hjälpare: normalisera publika symbols för TEST‑par till riktiga Bitfinex‑symbols ---
    @staticmethod
    def _normalize_public_symbol(symbol: str) -> str:
        try:
            import re as _re

            s = (symbol or "").strip()
            # tTESTBTC:TESTUSD -> tBTCUSD
            m = _re.match(r"^tTEST([A-Z0-9]+):TESTUSD$", s)
            if m:
                return f"t{m.group(1)}USD"
            # tTESTUSD:TESTBTC -> tBTCUSD
            m = _re.match(r"^tTESTUSD:TEST([A-Z0-9]+)$", s)
            if m:
                return f"t{m.group(1)}USD"
            # tTESTBTC:TESTUSDT -> tBTCUST (Bitfinex använder UST för USDT i tikers)
            m = _re.match(r"^tTEST([A-Z0-9]+):TESTUSDT$", s)
            if m:
                return f"t{m.group(1)}UST"
            # tTESTUSDT:TESTBTC -> tBTCUST
            m = _re.match(r"^tTESTUSDT:TEST([A-Z0-9]+)$", s)
            if m:
                return f"t{m.group(1)}UST"
            # tTEST<ASSET>USD (utan kolontecken) -> t<ASSET>USD
            m = _re.match(r"^tTEST([A-Z0-9]+)USD$", s)
            if m:
                return f"t{m.group(1)}USD"
            # Fallback: redan giltig Bitfinex symbol
            return s
        except Exception:
            return symbol

    async def _choose_available_pair(self, eff_symbol: str) -> str:
        """Välj närmaste giltiga Bitfinex‑symbol baserat på /conf listan.

        Om <ASSET>USD inte finns men <ASSET>UST finns (USDT), använd UST.
        Cacha listan en stund för att undvika överpollning.
        """
        try:
            s = (eff_symbol or "").strip()
            if not s.startswith("t") or len(s) < 6:
                return s
            base = s[1:-3]
            quote = s[-3:]
            # Hämta currency sym-map (fwd) från REST-configs och applicera (ex. ALGO->ALG)
            try:
                from services.market_data_facade import get_market_data

                svc = get_market_data()
                fwd, _ = await svc.get_currency_symbol_map()
                mapped = fwd.get(base.upper())
                if mapped and mapped.upper() != base.upper():
                    base = mapped
                elif base.upper() == "ALGO":
                    base = "ALG"
            except Exception:
                # Fallback för kända avvikelser
                if base.upper() == "ALGO":
                    base = "ALG"
            # Enkel cache i instansen
            now_ts = None
            try:
                import time as _t

                now_ts = _t.time()
            except Exception:
                pass
            cache = getattr(self, "_pairs_cache", None)
            cache_ttl = 3600.0
            pairs: list | None = None
            if cache and isinstance(cache, dict):
                ts = cache.get("ts", 0)
                items = cache.get("pairs")
                if items and now_ts and (now_ts - float(ts)) <= cache_ttl:
                    pairs = items
            if pairs is None:
                try:
                    # Lazy import via MarketDataFacade
                    from services.market_data_facade import get_market_data

                    svc = get_market_data()
                    pairs = await svc.get_configs_symbols() or []
                    self._pairs_cache = {"ts": now_ts or 0, "pairs": pairs}
                except Exception:
                    pairs = []
            # Om vi inte har parlistan, returnera original
            if not pairs:
                return s
            # Kandidater att testa i ordning (med och utan kolon)
            candidates = [
                f"{base}{quote}",
                f"{base}:{quote}",
            ]
            if quote == "USD":
                candidates += [f"{base}UST", f"{base}:UST"]
            for cand in candidates:
                if cand in pairs:
                    eff = f"t{cand}"
                    if eff != s:
                        try:
                            logger.info("🔁 WS symbol fallback: %s → %s", s, eff)
                        except Exception:
                            pass
                    return eff
            return s
        except Exception:
            return eff_symbol

    async def send(self, payload: dict[str, Any] | str):
        """Skicka rått WS-meddelande. Accepterar dict (json.dumps) eller str."""
        try:
            if not self.websocket:
                logger.warning("WS send ignorerad: ingen anslutning")
                return
            if isinstance(payload, (dict, list)):
                await self.websocket.send(json.dumps(payload))
            elif isinstance(payload, str):
                await self.websocket.send(payload)
            else:
                await self.websocket.send(json.dumps(payload))
        except Exception as e:
            logger.error(f"❌ WS send misslyckades: {e}")

    async def connect(self):
        """Ansluter till Bitfinex WebSocket."""
        try:
            logger.info("🔌 Ansluter till Bitfinex WebSocket...")
            self.websocket = await ws_connect(self.ws_url)
            self.is_connected = True
            logger.info("✅ Ansluten till Bitfinex WebSocket")
            # Starta lyssnare i bakgrunden direkt för att fånga auth-ack (endast om inte redan startad)
            if not hasattr(self, "_message_listener_task") or self._message_listener_task.done():
                self._message_listener_task = self._asyncio.create_task(
                    self.listen_for_messages(), name="ws-message-listener"
                )
            # Starta ping/heartbeat‑övervakning
            try:
                await self._start_heartbeat_tasks()
            except Exception:
                pass
            # Försök autentisera om nycklar finns
            await self.authenticate()
            # Starta symbol-refresh i bakgrunden (ej under pytest)
            try:
                import os as _os

                if not _os.environ.get("PYTEST_CURRENT_TEST") and not self._symbol_refresh_task:
                    self._symbol_refresh_task = self._asyncio.create_task(
                        self._symbol_refresh_loop(), name="ws-symbol-refresh"
                    )
            except Exception:
                pass
            return True
        except Exception as e:
            logger.error(f"❌ WebSocket-anslutning misslyckades: {e}")
            return False

    async def authenticate(self):
        """Autentiserar WS-sessionen med Bitfinex v2 auth-event."""
        try:
            # Skicka auth-payload
            auth_msg = build_ws_auth_payload()
            if not self.websocket:
                logger.warning("WS auth: ingen anslutning")
                return
            await self.websocket.send(auth_msg)
            logger.info("🔐 WS auth skickad, inväntar bekräftelse...")
            try:
                await self._asyncio.wait_for(self._auth_event.wait(), timeout=10)
            except Exception:
                logger.warning("⚠️ Ingen auth-bekräftelse inom timeout. Fortsätter utan auth.")
        except Exception as e:
            logger.warning(f"⚠️ Kunde inte skicka WS auth: {e}")

    async def send_conf(self, flags: int = 0):
        """Skickar conf-event för att aktivera flaggor (t.ex. seq/checksums)."""
        try:
            msg = {"event": "conf", "flags": flags}
            if not self.websocket:
                logger.warning("WS conf: ingen anslutning")
                return
            await self.websocket.send(json.dumps(msg))
            logger.info(f"⚙️ WS conf skickad med flags={flags}")
        except Exception as e:
            logger.warning(f"⚠️ Kunde inte skicka conf: {e}")

    # --- WS Orderkommandon ---
    async def order_update(
        self,
        order_id: int,
        price: float | None = None,
        amount: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Skicka WS order update (ou) för att uppdatera pris/mängd/flags.

        Args:
            order_id: ID för ordern
            price: nytt pris (valfritt)
            amount: ny mängd (valfritt)
            extra: extra fält att inkludera (t.ex. flags)

        Returns:
            Dict med status
        """
        payload: dict[str, Any] = {"id": int(order_id)}
        if price is not None:
            payload["price"] = str(price)
        if amount is not None:
            payload["amount"] = str(amount)
        if isinstance(extra, dict):
            payload.update(extra)

        if not await self.ensure_authenticated():
            return {"success": False, "error": "ws_not_authenticated"}
        try:
            msg = [0, "ou", None, payload]
            await self.send(msg)
            logger.info(f"📝 WS ou skickad: id=%s price=%s amount=%s", order_id, price, amount)
            return {"success": True, "sent": True}
        except Exception as e:
            logger.error(f"❌ WS ou fel: {e}")
            return {"success": False, "error": str(e)}

    async def order_cancel_multi(
        self,
        ids: list[int] | None = None,
        cids: list[int] | None = None,
        cid_date: str | None = None,
    ) -> dict[str, Any]:
        """Skicka WS oc_multi för att avbryta flera ordrar.

        Stödjer både id-lista och cid+cid_date-lista.
        """
        items: list[dict[str, Any]] = []
        if ids:
            for oid in ids:
                try:
                    items.append({"id": int(oid)})
                except Exception:
                    pass
        if cids:
            # Bitfinex kräver cid_date (YYYY-MM-DD) tillsammans med cid
            for cid in cids:
                entry = {"cid": int(cid)}
                if cid_date:
                    entry["cid_date"] = cid_date
                items.append(entry)

        if not items:
            return {"success": False, "error": "no_items"}
        if not await self.ensure_authenticated():
            return {"success": False, "error": "ws_not_authenticated"}
        try:
            msg = [0, "oc_multi", None, items]
            await self.send(msg)
            logger.info("🧹 WS oc_multi skickad: ids=%s cids=%s", ids or [], cids or [])
            return {"success": True, "count": len(items)}
        except Exception as e:
            logger.error(f"❌ WS oc_multi fel: {e}")
            return {"success": False, "error": str(e)}

    async def order_ops(self, ops: list[Any]) -> dict[str, Any]:
        """Skicka WS ops (batch av ['on'|'oc'|'ou', payload]).

        Args:
            ops: lista av operationer, var och en antingen [code, payload]
                 eller dict {"code": code, "payload": {...}}
        """
        if not isinstance(ops, list) or not ops:
            return {"success": False, "error": "empty_ops"}
        if not await self.ensure_authenticated():
            return {"success": False, "error": "ws_not_authenticated"}

        # Normalisera och sanera payloads (amount/price -> str)
        normalized: list[list[Any]] = []
        allowed = {"on", "oc", "ou"}
        for item in ops:
            try:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    code = str(item[0])
                    data = dict(item[1])
                elif isinstance(item, dict) and "code" in item and "payload" in item:
                    code = str(item.get("code"))
                    data = dict(item.get("payload") or {})
                else:
                    continue
                code_l = code.lower()
                if code_l not in allowed:
                    continue
                # Konvertera pris/amount till str enligt Bitfinex-krav
                if "price" in data and data["price"] is not None:
                    data["price"] = str(data["price"])
                if "amount" in data and data["amount"] is not None:
                    data["amount"] = str(data["amount"])
                # id/cid till int om möjligt
                for key in ("id", "cid"):
                    if key in data and data[key] is not None:
                        try:
                            data[key] = int(data[key])
                        except Exception:
                            pass
                normalized.append([code_l, data])
            except Exception:
                pass

        if not normalized:
            return {"success": False, "error": "no_valid_ops"}
        try:
            msg = [0, "ops", None, normalized]
            await self.send(msg)
            logger.info("📦 WS ops skickad: %s operationer", len(normalized))
            return {"success": True, "count": len(normalized)}
        except Exception as e:
            logger.error(f"❌ WS ops fel: {e}")
            return {"success": False, "error": str(e)}

    async def enable_dead_man_switch(self, timeout_ms: int = 60000):
        """Aktiverar Dead Man's Switch (auto-cancel vid frånkoppling)."""
        try:
            msg = {"event": "dms", "status": 1, "timeout": timeout_ms}
            if not self.websocket:
                logger.warning("WS DMS: ingen anslutning")
                return
            await self.websocket.send(json.dumps(msg))
            logger.info(f"🛡️ WS DMS aktiverad med timeout={timeout_ms} ms")
        except Exception as e:
            logger.warning(f"⚠️ Kunde inte aktivera DMS: {e}")

    def on_private_event(self, event_code: str, callback: Callable[[Any], Any]):
        """Registrerar callback för privat WS-event (t.ex. 'os','on','wu','tu',...)."""
        self.private_event_callbacks[event_code] = callback

    async def disconnect(self):
        """Kopplar från WebSocket."""
        logger.info("🔄 Startar WebSocket disconnect...")

        # Stoppa symbol-refresh loop först
        try:
            if self._symbol_refresh_task and not self._symbol_refresh_task.done():
                self._symbol_refresh_task.cancel()
                logger.info("✅ Symbol refresh task avbruten")
        except Exception as e:
            logger.warning(f"⚠️ Fel vid avbrytning av symbol refresh: {e}")
        finally:
            self._symbol_refresh_task = None

        # Stäng huvudsocket
        try:
            if self.websocket and not self.websocket.closed:
                await self.websocket.close()
                logger.info("✅ Huvudsocket stängd")
        except Exception as e:
            logger.warning(f"⚠️ Fel vid stängning av huvudsocket: {e}")
        finally:
            self.is_connected = False

        # Stäng poolsockets
        try:
            closed_count = 0
            for ws in list(self._pool_public):
                try:
                    if ws and not ws.closed:
                        await ws.close()
                        closed_count += 1
                except Exception:
                    pass
            if closed_count > 0:
                logger.info(f"✅ {closed_count} pool-sockets stängda")
        except Exception as e:
            logger.warning(f"⚠️ Fel vid stängning av pool-sockets: {e}")
        finally:
            self._pool_public.clear()
            self._pool_sub_counts.clear()
            self._sub_socket.clear()
            self._chan_callbacks.clear()
            self._chan_info.clear()
            self._chanid_by_subkey.clear()

        # Rensa aktivitetsstatus
        self.active_tickers.clear()
        self._live_notified.clear()
        self.margin_base = None
        self.margin_sym.clear()

        logger.info("✅ WebSocket disconnect komplett")

    async def _start_heartbeat_tasks(self):
        """Startar ping och heartbeat‑övervakning."""
        # Avsluta tidigare tasks om de finns
        try:
            if self._ping_task and not self._ping_task.done():
                self._ping_task.cancel()
            if self._hb_task and not self._hb_task.done():
                self._hb_task.cancel()
        except Exception:
            pass
        # Starta nya
        self._ping_task = self._asyncio.create_task(self._ping_loop(), name="ws-ping-loop")
        self._hb_task = self._asyncio.create_task(self._heartbeat_watchdog(), name="ws-hb-watchdog")

    async def _ping_loop(self):
        """Skickar ping med jämna mellanrum för att hålla anslutningen vid liv."""
        try:
            while True:
                await self._asyncio.sleep(self._ping_interval)
                try:
                    if not self.websocket or self.websocket.closed:
                        continue
                    # Bitfinex v2 WS stödjer text 'ping' → svarar 'pong'
                    await self.websocket.send("ping")
                except Exception:
                    pass
        except Exception:
            return

    async def _heartbeat_watchdog(self):
        """Övervakar senaste meddelandetid och triggar reconnect vid timeout."""
        try:
            while True:
                await self._asyncio.sleep(5.0)
                try:
                    import time as _t

                    now = _t.time()
                    last = float(self._last_msg_ts or 0.0)
                    if last and (now - last) > self._hb_timeout:
                        logger.warning("⏱️ WS heartbeat timeout – schemalägger reconnect")
                        await self._schedule_reconnect()
                except Exception:
                    pass
        except Exception:
            return

    async def _schedule_reconnect(self):
        """Schemalägger reconnect med exp backoff + jitter och auto-resubscribe."""
        if self._reconnecting:
            return
        self._reconnecting = True
        try:
            # Stäng befintliga sockets först
            try:
                await self.disconnect()
            except Exception:
                pass
            # Exponentiell backoff med jitter
            base = 0.5
            max_delay = 15.0
            delay = base
            for attempt in range(1, 6):  # noqa: B007
                try:
                    ok = await self.connect()
                    if ok:
                        break
                except Exception:
                    pass
                try:
                    import random as _rand

                    jitter = _rand.uniform(0.0, 0.4 * delay)
                except Exception:
                    jitter = 0.0
                await self._asyncio.sleep(delay + jitter)
                delay = min(max_delay, delay * 2)
            # Auto-resubscribe tickers
            try:
                for raw in list(getattr(self, "_requested_symbols", [])):
                    try:
                        await self.subscribe_ticker(raw, self._handle_ticker_with_strategy)
                        await self._asyncio.sleep(0.05)
                    except Exception:
                        pass
            except Exception:
                pass
            # Auto-resubscribe candles
            try:
                for (sym, tf), cb in list(getattr(self, "_requested_candles", {}).items()):
                    try:
                        await self.subscribe_candles(sym, tf, cb)
                        await self._asyncio.sleep(0.05)
                    except Exception:
                        pass
            except Exception:
                pass
        finally:
            self._reconnecting = False

    async def subscribe_ticker(self, symbol: str, callback: Callable):
        """
        Prenumererar på ticker-data för en symbol.

        Args:
            symbol: Trading pair (t.ex. 'tBTCUSD')
            callback: Funktion som anropas vid ny ticker-data
        """
        try:
            if not self.is_connected:
                await self.connect()
            # Central resolve via SymbolService
            try:
                from services.symbols import SymbolService

                sym_svc = SymbolService()
                await sym_svc.refresh()
                eff_symbol = sym_svc.resolve(symbol)
                if not sym_svc.listed(eff_symbol):
                    logger.warning("⛔ WS skip subscribe: pair_not_listed %s", eff_symbol)
                    return
            except Exception:
                # Fallback till tidigare lokala normalisering + choose_available_pair
                eff_symbol = self._normalize_public_symbol(symbol)
                eff_symbol = await self._choose_available_pair(eff_symbol)
            # Dedupe: hoppa över om redan aktiv eller pending (per eff_symbol)
            key = f"ticker|{eff_symbol}"
            if eff_symbol in self.active_tickers or key in self.subscriptions:
                logger.info("ℹ️ Ticker redan aktiv/pending: %s", eff_symbol)
                # Säkerställ callback är satt
                if key not in self.callbacks:
                    self.callbacks[key] = callback
                return
            # Registrera önskad symbol (rå) för framtida refresh/resubscribe
            try:
                self._requested_symbols.add(symbol)
            except Exception:
                pass
            # Verifiera att paret finns i configs; annars hoppa över och logga en gång
            try:
                pair = eff_symbol[1:] if eff_symbol.startswith("t") else eff_symbol
                pairs = None
                cache = getattr(self, "_pairs_cache", None)
                if cache and isinstance(cache, dict):
                    pairs = cache.get("pairs")
                if isinstance(pairs, list) and pair not in pairs:
                    logger.warning("⛔ WS skip subscribe: pair_not_listed %s", eff_symbol)
                    return
            except Exception:
                pass
            # Skapa subscription-meddelande
            subscribe_msg = {
                "event": "subscribe",
                "channel": "ticker",
                "symbol": eff_symbol,
            }

            # Skicka över poolad socket
            target_ws = await self._get_public_socket()
            if not target_ws:
                logger.warning("WS subscribe_ticker: ingen anslutning")
                return
            await target_ws.send(json.dumps(subscribe_msg))
            self.subscriptions[key] = subscribe_msg
            self.callbacks[key] = callback
            try:
                self._pool_sub_counts[target_ws] = int(self._pool_sub_counts.get(target_ws, 0)) + 1
            except Exception:
                pass
            # Markera var subben ligger (för unsubscribe)
            try:
                self._sub_socket[key] = target_ws
            except Exception:
                pass

            logger.info("📊 Prenumererar på ticker för %s", eff_symbol)

        except Exception as e:
            logger.error(f"❌ Ticker-prenumeration misslyckades: {e}")

    async def unsubscribe(self, sub_key: str):
        """Avsluta en prenumeration med sub_key (t.ex. 'ticker|tBTCUSD', 'trades|tBTCUSD', 'candles|trade:1m:tBTCUSD')."""
        try:
            ws = self._sub_socket.get(sub_key)
            if not ws:
                return
            chan_id = self._chanid_by_subkey.get((ws, sub_key))
            if chan_id is None:
                return
            msg = {"event": "unsubscribe", "chanId": chan_id}
            await ws.send(json.dumps(msg))
            # Lokalt cleanup
            try:
                self._pool_sub_counts[ws] = max(0, int(self._pool_sub_counts.get(ws, 0)) - 1)
            except Exception:
                pass
            self._sub_socket.pop(sub_key, None)
            self._chanid_by_subkey.pop((ws, sub_key), None)
            # Ta bort callback/info
            self._chan_callbacks.pop((ws, chan_id), None)
            self._chan_info.pop((ws, chan_id), None)
            self.subscriptions.pop(sub_key, None)
            self.callbacks.pop(sub_key, None)
            logger.info("🔕 Unsubscribed %s (chanId=%s)", sub_key, chan_id)
        except Exception as e:
            logger.warning("Unsubscribe fel för %s: %s", sub_key, e)

    async def _symbol_refresh_loop(self):
        """Refreshar configs periodiskt och resubscribe:ar saknade listade par för önskade symboler."""
        try:
            from services.symbols import SymbolService

            sym_svc = SymbolService()
            while True:
                try:
                    await sym_svc.refresh()
                    desired = list(getattr(self, "_requested_symbols", []))
                    for raw in desired:
                        eff = sym_svc.resolve(raw)
                        if not sym_svc.listed(eff):
                            continue
                        key = f"ticker|{eff}"
                        if key not in self.subscriptions:
                            try:
                                logger.info("🔄 WS resubscribe: %s (eff=%s)", raw, eff)
                                await self.subscribe_ticker(raw, self._handle_ticker_with_strategy)
                            except Exception:
                                pass
                except Exception as ie:
                    logger.warning("Symbol refresh loop fel: %s", ie)
                await self._asyncio.sleep(float(self._symbol_refresh_interval))
        except Exception:
            return

    async def subscribe_trades(self, symbol: str, callback: Callable):
        """
        Prenumererar på trades-data för en symbol.

        Args:
            symbol: Trading pair
            callback: Funktion som anropas vid ny trade-data
        """
        try:
            if not self.is_connected:
                await self.connect()

            try:
                from services.symbols import SymbolService

                sym_svc = SymbolService()
                await sym_svc.refresh()
                eff_symbol = sym_svc.resolve(symbol)
                if not sym_svc.listed(eff_symbol):
                    logger.warning("⛔ WS skip trades: pair_not_listed %s", eff_symbol)
                    return
            except Exception:
                eff_symbol = self._normalize_public_symbol(symbol)
                eff_symbol = await self._choose_available_pair(eff_symbol)
            subscribe_msg = {
                "event": "subscribe",
                "channel": "trades",
                "symbol": eff_symbol,
            }

            # Verifiera att paret finns
            try:
                pair = eff_symbol[1:] if eff_symbol.startswith("t") else eff_symbol
                pairs = None
                cache = getattr(self, "_pairs_cache", None)
                if cache and isinstance(cache, dict):
                    pairs = cache.get("pairs")
                if isinstance(pairs, list) and pair not in pairs:
                    logger.warning("⛔ WS skip trades: pair_not_listed %s", eff_symbol)
                    return
            except Exception:
                pass
            target_ws = await self._get_public_socket()
            if not target_ws:
                logger.warning("WS subscribe_trades: ingen anslutning")
                return
            await target_ws.send(json.dumps(subscribe_msg))
            key = f"trades|{eff_symbol}"
            self.subscriptions[key] = subscribe_msg
            self.callbacks[key] = callback
            try:
                self._pool_sub_counts[target_ws] = int(self._pool_sub_counts.get(target_ws, 0)) + 1
                self._sub_socket[key] = target_ws
            except Exception:
                pass

            logger.info("💱 Prenumererar på trades för %s", eff_symbol)

        except Exception as e:
            logger.error(f"❌ Trades-prenumeration misslyckades: {e}")

    async def subscribe_with_strategy_evaluation(self, symbol: str, callback: Callable):
        """
        Prenumererar på ticker och kör automatisk strategiutvärdering.

        Args:
            symbol: Trading pair (t.ex. 'tBTCUSD')
            callback: Funktion som anropas med strategi-resultat
        """
        try:
            if not self.is_connected:
                await self.connect()

            # Spara callback för strategiutvärdering
            self.strategy_callbacks[symbol] = callback

            # Prenumerera på ticker (med normalisering/fallback inuti)
            await self.subscribe_ticker(symbol, self._handle_ticker_with_strategy)

            logger.info(f"🎯 Prenumererar på {symbol} med strategiutvärdering")

        except Exception as e:
            logger.error(f"❌ Strategi-prenumeration misslyckades: {e}")

    async def subscribe_candles(self, symbol: str, timeframe: str, callback: Callable):
        """Prenumerera på candles (WS public). key = trade:tf:symbol"""
        try:
            if not self.is_connected:
                await self.connect()

            try:
                from services.symbols import SymbolService

                sym_svc = SymbolService()
                await sym_svc.refresh()
                eff_symbol = sym_svc.resolve(symbol)
                if not sym_svc.listed(eff_symbol):
                    logger.warning("⛔ WS skip candles: pair_not_listed %s", eff_symbol)
                    return
            except Exception:
                eff_symbol = self._normalize_public_symbol(symbol)
                eff_symbol = await self._choose_available_pair(eff_symbol)
            ckey = f"trade:{timeframe}:{eff_symbol}"
            msg = {"event": "subscribe", "channel": "candles", "key": ckey}
            # Verifiera att par finns
            # Verifiera att paret finns
            try:
                pair = eff_symbol[1:] if eff_symbol.startswith("t") else eff_symbol
                pairs = None
                cache = getattr(self, "_pairs_cache", None)
                if cache and isinstance(cache, dict):
                    pairs = cache.get("pairs")
                if isinstance(pairs, list):
                    # candles använder key trade:tf:tPAIR → kontrollera par
                    if pair not in pairs:
                        logger.warning("⛔ WS skip candles: pair_not_listed %s", eff_symbol)
                        return
            except Exception:
                pass
            target_ws = await self._get_public_socket()
            if not target_ws:
                logger.warning("WS subscribe_candles: ingen anslutning")
                return
            await target_ws.send(json.dumps(msg))
            sub_key = f"candles|{ckey}"
            self.subscriptions[sub_key] = msg
            self.callbacks[sub_key] = callback
            try:
                self._pool_sub_counts[target_ws] = int(self._pool_sub_counts.get(target_ws, 0)) + 1
                self._sub_socket[sub_key] = target_ws
            except Exception:
                pass
            # Spåra för auto-resubscribe
            try:
                self._requested_candles[(symbol, timeframe)] = callback
            except Exception:
                pass
            logger.info("🕯️ Prenumererar på candles %s", ckey)
        except Exception as e:
            logger.error(f"❌ Candles-prenumeration misslyckades: {e}")
            # Transient fel (t.ex. "no close frame received or sent") → logga men försök inte igen automatiskt
            # för att undvika oändlig rekursion. Låt användaren starta om eller manuellt prenumerera.
            try:
                msg = str(e).lower()
                if "no close frame" in msg or "websocket is closed" in msg:
                    logger.warning(
                        "⚠️ WS-anslutning instabil - candles-prenumeration pausad. Starta om för att återansluta."
                    )
            except Exception:
                pass

    async def subscribe_book(
        self,
        symbol: str,
        precision: str = "P0",
        freq: str = "F0",
        length: int = 25,
        callback: Callable | None = None,
    ):
        """Prenumerera på orderbok (WS public)."""
        try:
            if not self.is_connected:
                await self.connect()

            try:
                from services.symbols import SymbolService

                sym_svc = SymbolService()
                await sym_svc.refresh()
                eff_symbol = sym_svc.resolve(symbol)
                if not sym_svc.listed(eff_symbol):
                    logger.warning("⛔ WS skip book: pair_not_listed %s", eff_symbol)
                    return
            except Exception:
                eff_symbol = self._normalize_public_symbol(symbol)
                eff_symbol = await self._choose_available_pair(eff_symbol)
            msg = {
                "event": "subscribe",
                "channel": "book",
                "symbol": eff_symbol,
                "prec": precision,
                "freq": freq,
                "len": length,
            }
            if not self.websocket:
                logger.warning("WS subscribe_book: ingen anslutning")
                return
            # Verifiera att paret finns
            try:
                pair = eff_symbol[1:] if eff_symbol.startswith("t") else eff_symbol
                pairs = None
                cache = getattr(self, "_pairs_cache", None)
                if cache and isinstance(cache, dict):
                    pairs = cache.get("pairs")
                if isinstance(pairs, list) and pair not in pairs:
                    logger.warning("⛔ WS skip book: pair_not_listed %s", eff_symbol)
                    return
            except Exception:
                pass
            await self.websocket.send(json.dumps(msg))
            key = f"book|{eff_symbol}|{precision}|{freq}|{length}"
            self.subscriptions[key] = msg
            if callback:
                self.callbacks[key] = callback
            logger.info(
                "📖 Prenumererar på orderbok %s %s/%s/%s",
                eff_symbol,
                precision,
                freq,
                length,
            )
        except Exception as e:
            logger.error(f"❌ Orderbok-prenumeration misslyckades: {e}")

    async def _handle_ticker_with_strategy(self, ticker_data: dict):
        """
        Hanterar ticker-data och kör strategiutvärdering.

        Args:
            ticker_data: Ticker-data från Bitfinex
        """
        try:
            # Säkerställ dict-inmatning
            if not isinstance(ticker_data, dict):
                # Försök normalisera om vi fick en lista (WS rå format)
                if isinstance(ticker_data, list) and len(ticker_data) >= 7:
                    # Vi har inte symbol här, ta 'unknown' – eval sker inte ändå utan history
                    ticker_data = {
                        "symbol": "unknown",
                        "bid": ticker_data[0],
                        "bid_size": ticker_data[1],
                        "ask": ticker_data[2],
                        "ask_size": ticker_data[3],
                        "daily_change": ticker_data[4],
                        "daily_change_relative": ticker_data[5],
                        "last_price": ticker_data[6],
                    }
                else:
                    return
            symbol = ticker_data.get("symbol", "unknown")
            price = ticker_data.get("last_price", 0)

            # Uppdatera senaste pris och hela normerade ticker-frame
            self.latest_prices[symbol] = price
            try:
                # Spara hela ramen så REST-fallback kan få bid/ask m.m. från WS
                if isinstance(ticker_data, dict) and symbol != "unknown":
                    self.latest_ticker_frames[symbol] = ticker_data
            except Exception:
                pass
            try:
                import time as _t

                self._last_tick_ts[symbol] = _t.time()
            except Exception:
                pass

            # Första tick per symbol: markera live och logga
            if symbol != "unknown" and symbol not in self._live_notified:
                self._live_notified.add(symbol)
                self.active_tickers.add(symbol)
                logger.info(f"📡 WS ticker live: {symbol}")

            # Throttle: max 1 eval/sek per symbol → generera enhetlig signal via UnifiedSignalService
            import time as _t

            now_s = _t.time()
            last_eval = float(self._last_eval_ts.get(symbol, 0))
            if now_s - last_eval >= 1.0 and symbol != "unknown":
                self._last_eval_ts[symbol] = now_s
                try:
                    from services.unified_signal_service import (
                        unified_signal_service as _uss,
                    )

                    sig = await _uss.generate_signal(symbol, force_refresh=False)
                    if sig is not None:
                        result = {
                            "symbol": getattr(sig, "symbol", symbol),
                            "signal": getattr(sig, "signal_type", None) or "UNKNOWN",
                            "current_price": (
                                getattr(sig, "current_price", None)
                                if getattr(sig, "current_price", None) is not None
                                else price
                            ),
                            "reason": getattr(sig, "reason", "") or "",
                            "timestamp": datetime.now().isoformat(),
                        }
                        # Anropa callback om registrerad
                        if symbol in self.strategy_callbacks:
                            await self.strategy_callbacks[symbol](result)

                        # Logga endast vid tillståndsskifte eller var 30s
                        now_s2 = _t.time()
                        last_sig = self._last_strategy_signal.get(symbol)
                        last_reason = self._last_strategy_reason.get(symbol)
                        last_log = float(self._last_strategy_log_ts.get(symbol, 0))
                        changed = result.get("signal") != last_sig or result.get("reason") != last_reason
                        min_interval = 30.0
                        _reason_str = str(result.get("reason", "") or "")
                        if "Otillräcklig data" in _reason_str:
                            min_interval = 60.0
                        if changed or (now_s2 - last_log) >= min_interval:
                            logger.info(
                                f"🎯 Strategiutvärdering för {symbol}: {result['signal']} - {result.get('reason','')}"
                            )
                            self._last_strategy_signal[symbol] = result.get("signal")
                            self._last_strategy_reason[symbol] = result.get("reason")
                            self._last_strategy_log_ts[symbol] = now_s2
                except Exception as e:
                    logger.error(f"❌ UnifiedSignalService fel för {symbol}: {e}")

        except Exception as e:
            logger.error(f"❌ Fel vid hantering av ticker med strategi: {e}")

    async def _evaluate_strategy_for_symbol(self, symbol: str):
        """
        Avvecklad: Strategiutvärdering flyttad till UnifiedSignalService.
        Behålls som no-op för bakåtkompatibilitet under övergången.
        """
        try:
            from services.unified_signal_service import unified_signal_service as _uss

            sig = await _uss.generate_signal(symbol, force_refresh=False)
            if sig is None:
                return
            result = {
                "symbol": getattr(sig, "symbol", symbol),
                "signal": getattr(sig, "signal_type", None) or "UNKNOWN",
                "current_price": getattr(sig, "current_price", None) or self.latest_prices.get(symbol, 0),
                "reason": getattr(sig, "reason", "") or "",
                "timestamp": datetime.now().isoformat(),
            }
            if symbol in self.strategy_callbacks:
                await self.strategy_callbacks[symbol](result)
        except Exception as e:
            logger.error(f"❌ UnifiedSignalService fel (legacy wrapper) för {symbol}: {e}")

    async def listen_for_messages(self):
        """Lyssnar på WebSocket-meddelanden."""
        try:
            logger.info("👂 Lyssnar på WebSocket-meddelanden...")

            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    self._current_incoming_ws = self.websocket
                    # Heartbeat: uppdatera senaste meddelandetid
                    try:
                        import time as _t

                        self._last_msg_ts = _t.time()
                    except Exception:
                        pass

                    # Hantera olika meddelandetyper
                    if isinstance(data, list) and len(data) > 1:
                        await self._handle_channel_message(data)
                    elif isinstance(data, dict):
                        await self._handle_event_message(data)

                except json.JSONDecodeError:
                    logger.warning("⚠️ Kunde inte parsa WebSocket-meddelande")
                except Exception as e:
                    logger.error(f"❌ Fel vid hantering av WebSocket-meddelande: {e}")
                finally:
                    try:
                        self._current_incoming_ws = None
                    except Exception:
                        pass

        except ConnectionClosed:
            logger.warning("⚠️ WebSocket-anslutning stängd")
            self.is_connected = False
            await self._schedule_reconnect()
        except Exception as e:
            logger.error(f"❌ WebSocket-lyssnare fel: {e}")
            await self._schedule_reconnect()

    async def _handle_channel_message(self, data: list):
        """Hanterar kanal-meddelanden (publika och privata)."""
        try:
            channel_id = data[0]
            message_data = data[1]

            # Privata kontohändelser sker på channel_id 0 med event-kod som andra element
            if channel_id == 0:
                # Format: [0, 'EVENT_CODE', payload]
                if isinstance(message_data, str):
                    event_code = message_data

                    # OPTIMERING: Hantera calc responses direkt
                    if event_code == "miu":
                        await self._handle_miu(data)
                        return
                    elif event_code == "pu":
                        await self._handle_pu(data)
                        return
                    elif event_code == "wu":
                        await self._handle_wu(data)
                        return
                    elif event_code == "fiu":
                        await self._handle_fiu(data)
                        return

                    cb = self.private_event_callbacks.get(event_code)
                    if cb and callable(cb):
                        # Skicka hela ursprungsmeddelandet så handlers kan läsa msg[1] och msg[2]
                        try:
                            if asyncio.iscoroutinefunction(cb):
                                await cb(data)
                            else:
                                cb(data)
                        except Exception as e:
                            logger.warning(f"⚠️ Callback error for {event_code}: {e}")
                    else:
                        logger.debug(f"ℹ️ Ohanterad privat händelse: {event_code}")
                else:
                    # Heartbeat: [0, 'hb'] eller liknande
                    if message_data == "hb":
                        return
                    logger.debug(f"ℹ️ Oväntat privat meddelande: {data}")
                return

            # Publika kanaler via chanId‑mapping (per socket)
            # För pooled sockets kan vi inte veta ws‑objektet här direkt; Bitfinex chanId är per socket.
            # Heuristik: om meddelandet kommer via huvudlyssnaren (self.listen_for_messages) använd self.websocket,
            # annars har _listen_loop(ws) redan kallat _handle_channel_message i samma kontext.
            current_ws = getattr(self, "_current_incoming_ws", None)
            if current_ws is None:
                current_ws = self.websocket
            cb = self._chan_callbacks.get((current_ws, int(channel_id))) or self.channel_callbacks.get(int(channel_id))
            if cb and callable(cb):
                # Ignorera heartbeat
                if message_data == "hb":
                    return
                info = (
                    self._chan_info.get((current_ws, int(channel_id))) or self.channel_info.get(int(channel_id)) or {}
                )
                chan = info.get("channel")
                symbol = info.get("symbol") or "unknown"
                # Normalisera ticker-frame till dict
                if chan == "ticker" and isinstance(message_data, list) and len(message_data) >= 7:
                    norm = {
                        "symbol": symbol,
                        "bid": message_data[0],
                        "bid_size": message_data[1],
                        "ask": message_data[2],
                        "ask_size": message_data[3],
                        "daily_change": message_data[4],
                        "daily_change_relative": message_data[5],
                        "last_price": message_data[6],
                        "volume": message_data[7] if len(message_data) > 7 else 0,
                        "high": message_data[8] if len(message_data) > 8 else 0,
                        "low": message_data[9] if len(message_data) > 9 else 0,
                    }
                    try:
                        if asyncio.iscoroutinefunction(cb):
                            await cb(norm)
                        else:
                            cb(norm)
                    except Exception as e:
                        logger.warning(f"⚠️ Ticker callback error: {e}")
                    return
                # För övriga kanaler, skicka rå payload vidare
                try:
                    if asyncio.iscoroutinefunction(cb):
                        await cb(message_data)
                    else:
                        cb(message_data)
                except Exception as e:
                    logger.warning(f"⚠️ Channel callback error: {e}")
                return
            # Fallback: heuristik för ticker/trades (äldre väg)
            if isinstance(message_data, list) and len(message_data) >= 7:
                ticker_data = {
                    "symbol": self._get_symbol_from_channel_id(channel_id),
                    "bid": message_data[0],
                    "bid_size": message_data[1],
                    "ask": message_data[2],
                    "ask_size": message_data[3],
                    "daily_change": message_data[4],
                    "daily_change_relative": message_data[5],
                    "last_price": message_data[6],
                    "volume": message_data[7] if len(message_data) > 7 else 0,
                    "high": message_data[8] if len(message_data) > 8 else 0,
                    "low": message_data[9] if len(message_data) > 9 else 0,
                }
                for k, callback in self.callbacks.items():
                    if k.startswith("ticker|") and ticker_data["symbol"] in k and callback and callable(callback):
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(ticker_data)
                            else:
                                callback(ticker_data)
                        except Exception as e:
                            logger.warning(f"⚠️ Fallback ticker callback error: {e}")
                        break

        except Exception as e:
            logger.error(f"❌ Fel vid hantering av kanal-meddelande: {e}")

    def _get_symbol_from_channel_id(self, channel_id: int) -> str:  # noqa: ARG002
        """Hämtar symbol från channel ID baserat på prenumerationer."""
        for symbol, sub_data in self.subscriptions.items():
            if "ticker" in str(sub_data):
                return symbol
        return "unknown"

    async def _handle_event_message(self, data: dict):
        """Hanterar event-meddelanden (subscribe, auth, etc.)."""
        try:
            event = data.get("event")

            if event == "subscribed":
                chan = data.get("channel")
                chan_id = data.get("chanId") or data.get("chanid") or data.get("chan_id")
                symbol = data.get("symbol")
                key = data.get("key")
                logger.info(f"✅ Prenumeration bekräftad: channel={chan} symbol={symbol or key} chanId={chan_id}")
                cb_key = None
                if chan == "ticker" and symbol:
                    cb_key = f"ticker|{symbol}"
                elif chan == "trades" and symbol:
                    cb_key = f"trades|{symbol}"
                elif chan == "candles" and key:
                    cb_key = f"candles|{key}"
                elif chan == "book" and symbol:
                    # försök hitta första matchande book-sub
                    for k in list(self.subscriptions.keys()):
                        if k.startswith(f"book|{symbol}|"):
                            cb_key = k
                            break
                try:
                    if chan_id is not None and cb_key and cb_key in self.callbacks:
                        # Hitta socket från subkey
                        ws = self._sub_socket.get(cb_key)
                        if ws is None:
                            # fallback till huvudsocket
                            ws = self.websocket
                        self._chan_callbacks[(ws, int(chan_id))] = self.callbacks.get(cb_key)
                        self._chan_info[(ws, int(chan_id))] = {
                            "channel": chan,
                            "symbol": symbol,
                            "key": key,
                        }
                        # För snabb lookup åt andra hållet
                        self._chanid_by_subkey[(ws, cb_key)] = int(chan_id)
                except Exception:
                    pass
            elif event == "auth":
                status = data.get("status")
                if status == "OK":
                    self.is_authenticated = True
                    self._auth_event.set()
                    logger.info("✅ WS auth bekräftad")
                else:
                    self.is_authenticated = False
                    self._auth_event.set()
                    logger.error(f"❌ WS auth misslyckades: {data}")
                # Vidarebefordra auth-event till ev. registrerad callback
                cb = self.private_event_callbacks.get("auth")
                if cb:
                    await cb(data)
            elif event == "error":
                msg = str(data.get("msg", "unknown error"))
                if "subscribe: dup" in msg:
                    logger.info("ℹ️ WS: prenumeration redan aktiv (dup)")
                else:
                    # Försök inkludera symbol/key för felsökning
                    sym = data.get("symbol") or data.get("key") or "?"
                    logger.error("❌ WebSocket-fel: %s (sym=%s)", msg, sym)
            elif event == "info":
                logger.info(f"ℹ️ WebSocket-info: {data.get('msg', 'no message')}")

        except Exception as e:
            logger.error(f"❌ Fel vid hantering av event-meddelande: {e}")

    async def _handle_miu(self, msg: list):
        """Hanterar margin info updates (miu) på channel 0.

        Format:
        [0,'miu',['base',[USER_PL,USER_SWAPS,MARGIN_BALANCE,MARGIN_NET,MARGIN_MIN]]]
        eller
        [0,'miu',['sym','tBTCUSD',[TRADABLE_BALANCE,GROSS_BALANCE,BUY,SELL,...]]]
        """
        try:
            if not isinstance(msg, list) or len(msg) < 3:
                return
            payload = msg[2]
            if not isinstance(payload, list) or not payload:
                return
            import time as _t

            kind = payload[0]
            if kind == "base" and len(payload) >= 2 and isinstance(payload[1], list):
                self.margin_base = payload[1]
                self._last_margin_ts = _t.time()
                if "miu:base" not in self._live_notified:
                    self._live_notified.add("miu:base")
                    logger.info("📡 WS margin live: base")
            elif kind == "sym" and len(payload) >= 3:
                symbol = str(payload[1])
                arr = payload[2] if isinstance(payload[2], list) else []
                self.margin_sym[symbol] = arr
                self._last_margin_sym_ts[symbol] = _t.time()
                key = f"miu:{symbol}"
                if key not in self._live_notified:
                    self._live_notified.add(key)
                    logger.info(f"📡 WS margin live: {symbol}")
        except Exception as e:
            logger.warning(f"⚠️ Kunde inte hantera miu: {e}")

    async def _handle_pu(self, msg: list):
        """Hantera Position Updates (pu)."""
        try:
            if len(msg) < 3 or not isinstance(msg[2], list):
                return
            pos_data = msg[2]
            if len(pos_data) < 10:
                return

            symbol = pos_data[0]
            status = pos_data[1]
            amount = float(pos_data[2]) if pos_data[2] is not None else 0.0
            base_price = float(pos_data[3]) if pos_data[3] is not None else 0.0
            pl = float(pos_data[6]) if pos_data[6] is not None else 0.0
            pl_perc = float(pos_data[7]) if pos_data[7] is not None else 0.0

            if not hasattr(self, "positions"):
                self.positions = {}

            self.positions[symbol] = {
                "status": status,
                "amount": amount,
                "base_price": base_price,
                "pl": pl,
                "pl_perc": pl_perc,
                "timestamp": time.time(),
            }

            logger.debug("📊 Position uppdaterad: %s = %s", symbol, self.positions[symbol])
        except Exception as e:
            logger.warning(f"⚠️ Kunde inte hantera pu: {e}")

    async def _handle_wu(self, msg: list):
        """Hantera Wallet Updates (wu)."""
        try:
            if len(msg) < 3 or not isinstance(msg[2], list):
                return
            wallet_data = msg[2]
            if len(wallet_data) < 4:
                return

            wallet_type = wallet_data[0]
            currency = wallet_data[1]
            balance = float(wallet_data[2]) if wallet_data[2] is not None else 0.0
            available = float(wallet_data[4]) if wallet_data[4] is not None else 0.0

            if not hasattr(self, "wallets"):
                self.wallets = {}

            wallet_key = f"{wallet_type}_{currency}"
            self.wallets[wallet_key] = {
                "type": wallet_type,
                "currency": currency,
                "balance": balance,
                "available": available,
                "timestamp": time.time(),
            }

            logger.debug("💰 Wallet uppdaterad: %s = %s", wallet_key, self.wallets[wallet_key])
        except Exception as e:
            logger.warning(f"⚠️ Kunde inte hantera wu: {e}")

    async def _handle_fiu(self, msg: list):
        """Hantera Funding Info Updates (fiu)."""
        try:
            if len(msg) < 3 or not isinstance(msg[2], list):
                return
            funding_data = msg[2]
            if len(funding_data) < 3:
                return

            type_info = funding_data[0]
            if type_info == "sym":
                symbol = funding_data[1]
                rates_data = funding_data[2] if len(funding_data) > 2 else []

                if not hasattr(self, "funding_rates"):
                    self.funding_rates = {}

                self.funding_rates[symbol] = {
                    "rates": rates_data,
                    "timestamp": time.time(),
                }

                logger.debug("📈 Funding rates uppdaterad: %s = %s", symbol, rates_data)
        except Exception as e:
            logger.warning(f"⚠️ Kunde inte hantera fiu: {e}")

    async def margin_calc_if_needed(self, symbol: str) -> dict:
        """
        Skicka WS calc (miu: sym) om buy/sell saknas (None) i margin_sym.
        OPTIMERAD: Calc caching för att respektera rate limits.
        """
        try:
            # Resolve symbol så vi använder eff_symbol i WS
            eff = symbol
            try:
                from services.symbols import SymbolService

                svc = SymbolService()
                await svc.refresh()
                eff = svc.resolve(symbol)
            except Exception:
                pass

            # OPTIMERING: Calc cache (5 minuter TTL)
            cache_key = f"calc_margin_{eff}"
            cache_ttl = 300  # 5 minuter

            if hasattr(self, "_calc_cache"):
                cached = self._calc_cache.get(cache_key)
                if cached and (time.time() - cached["timestamp"]) < cache_ttl:
                    logger.debug(f"📋 Använder cached calc för {eff}")
                    return {"requested": False, "reason": "cached"}
            else:
                self._calc_cache = {}

            arr = (self.margin_sym or {}).get(eff)
            need = not (isinstance(arr, list) and len(arr) >= 4 and arr[2] is not None and arr[3] is not None)
            if not need:
                return {"requested": False, "reason": "fields_present"}
            if not await self.ensure_authenticated():
                return {"requested": False, "error": "ws_not_authenticated"}

            # OPTIMERING: Batch calc requests
            keys = [["margin_base"], [f"margin_sym_{eff}"]]
            msg = [0, "calc", None, keys]
            await self.send(msg)

            # Spara i cache
            self._calc_cache[cache_key] = {"timestamp": time.time(), "requested": True}

            logger.info("🧮 WS margin calc begärd för %s", eff)
            return {"requested": True}
        except Exception as e:
            logger.error("WS margin calc fel: %s", e)
            return {"requested": False, "error": str(e)}

    async def margin_calc_batch_if_needed(self, symbols: list[str]) -> dict[str, dict]:
        """
        OPTIMERAD: Batch-version av margin_calc_if_needed.
        Skickar calc-requests för flera symboler samtidigt.

        Args:
            symbols: Lista med symboler att begära calc för

        Returns:
            Dict med symbol -> result mapping
        """
        try:
            if not await self.ensure_authenticated():
                return {symbol: {"requested": False, "error": "ws_not_authenticated"} for symbol in symbols}

            results = {}
            symbols_to_calc = []

            # Kontrollera cache och behov för varje symbol
            for symbol in symbols:
                eff = symbol
                try:
                    from services.symbols import SymbolService

                    svc = SymbolService()
                    await svc.refresh()
                    eff = svc.resolve(symbol)
                except Exception:
                    pass

                # Kontrollera cache
                cache_key = f"calc_margin_{eff}"
                cache_ttl = 300  # 5 minuter

                if hasattr(self, "_calc_cache"):
                    cached = self._calc_cache.get(cache_key)
                    if cached and (time.time() - cached["timestamp"]) < cache_ttl:
                        results[symbol] = {"requested": False, "reason": "cached"}
                        continue
                else:
                    self._calc_cache = {}

                # Kontrollera om data redan finns
                arr = (self.margin_sym or {}).get(eff)
                need = not (isinstance(arr, list) and len(arr) >= 4 and arr[2] is not None and arr[3] is not None)

                if not need:
                    results[symbol] = {"requested": False, "reason": "fields_present"}
                else:
                    symbols_to_calc.append((symbol, eff))

            if not symbols_to_calc:
                return results

            # Skicka batch calc-request
            try:
                keys = [["margin_base"]]  # Lägg till base först
                for _symbol, eff in symbols_to_calc:
                    keys.append([f"margin_sym_{eff}"])

                msg = [0, "calc", None, keys]
                await self.send(msg)

                # Spara i cache för alla symboler
                now = time.time()
                for symbol, eff in symbols_to_calc:
                    cache_key = f"calc_margin_{eff}"
                    self._calc_cache[cache_key] = {"timestamp": now, "requested": True}
                    results[symbol] = {"requested": True}

                logger.info(f"🧮 Batch WS margin calc begärd för {len(symbols_to_calc)} symboler")

            except Exception as e:
                logger.error(f"❌ Batch WS margin calc fel: {e}")
                for symbol, _eff in symbols_to_calc:
                    results[symbol] = {"requested": False, "error": str(e)}

            return results

        except Exception as e:
            logger.error(f"❌ Batch margin calc fel: {e}")
            return {symbol: {"requested": False, "error": str(e)} for symbol in symbols}

    async def position_calc_if_needed(self, symbol: str) -> dict:
        """
        Skicka WS calc för position info om den saknas.
        OPTIMERAD: Calc caching för att respektera rate limits.
        """
        try:
            # Resolve symbol så vi använder eff_symbol i WS
            eff = symbol
            try:
                from services.symbols import SymbolService

                svc = SymbolService()
                await svc.refresh()
                eff = svc.resolve(symbol)
            except Exception:
                pass

            # OPTIMERING: Calc cache (5 minuter TTL)
            cache_key = f"calc_position_{eff}"
            cache_ttl = 300  # 5 minuter

            if hasattr(self, "_calc_cache"):
                cached = self._calc_cache.get(cache_key)
                if cached and (time.time() - cached["timestamp"]) < cache_ttl:
                    logger.debug(f"📋 Använder cached position calc för {eff}")
                    return {"requested": False, "reason": "cached"}
            else:
                self._calc_cache = {}

            # Kontrollera om position data redan finns
            if hasattr(self, "positions") and eff in self.positions:
                pos_data = self.positions[eff]
                if pos_data and pos_data.get("status") == "ACTIVE":
                    return {"requested": False, "reason": "position_exists"}

            if not await self.ensure_authenticated():
                return {"requested": False, "error": "ws_not_authenticated"}

            # Skicka position calc request
            keys = [[f"position_{eff}"]]
            msg = [0, "calc", None, keys]
            await self.send(msg)

            # Spara i cache
            self._calc_cache[cache_key] = {"timestamp": time.time(), "requested": True}

            logger.info("📊 WS position calc begärd för %s", eff)
            return {"requested": True}
        except Exception as e:
            logger.error("WS position calc fel: %s", e)
            return {"requested": False, "error": str(e)}

    async def wallet_calc_if_needed(self, wallet_type: str = "exchange", currency: str = "USD") -> dict:
        """
        Skicka WS calc för wallet balance info.
        OPTIMERAD: Calc caching för att respektera rate limits.
        """
        try:
            # OPTIMERING: Calc cache (5 minuter TTL)
            cache_key = f"calc_wallet_{wallet_type}_{currency}"
            cache_ttl = 300  # 5 minuter

            if hasattr(self, "_calc_cache"):
                cached = self._calc_cache.get(cache_key)
                if cached and (time.time() - cached["timestamp"]) < cache_ttl:
                    logger.debug(f"📋 Använder cached wallet calc för {wallet_type}:{currency}")
                    return {"requested": False, "reason": "cached"}
            else:
                self._calc_cache = {}

            if not await self.ensure_authenticated():
                return {"requested": False, "error": "ws_not_authenticated"}

            # Skicka wallet calc request
            keys = [[f"wallet_{wallet_type}_{currency}"]]
            msg = [0, "calc", None, keys]
            await self.send(msg)

            # Spara i cache
            self._calc_cache[cache_key] = {"timestamp": time.time(), "requested": True}

            logger.info("💰 WS wallet calc begärd för %s:%s", wallet_type, currency)
            return {"requested": True}
        except Exception as e:
            logger.error("WS wallet calc fel: %s", e)
            return {"requested": False, "error": str(e)}

    async def funding_calc_if_needed(self, currency: str = "USD") -> dict:
        """
        Skicka WS calc för funding info.
        OPTIMERAD: Calc caching för att respektera rate limits.
        """
        try:
            # OPTIMERING: Calc cache (5 minuter TTL)
            cache_key = f"calc_funding_{currency}"
            cache_ttl = 300  # 5 minuter

            if hasattr(self, "_calc_cache"):
                cached = self._calc_cache.get(cache_key)
                if cached and (time.time() - cached["timestamp"]) < cache_ttl:
                    logger.debug(f"📋 Använder cached funding calc för {currency}")
                    return {"requested": False, "reason": "cached"}
            else:
                self._calc_cache = {}

            if not await self.ensure_authenticated():
                return {"requested": False, "error": "ws_not_authenticated"}

            # Skicka funding calc request
            keys = [[f"funding_sym_f{currency}"]]
            msg = [0, "calc", None, keys]
            await self.send(msg)

            # Spara i cache
            self._calc_cache[cache_key] = {"timestamp": time.time(), "requested": True}

            logger.info("📈 WS funding calc begärd för %s", currency)
            return {"requested": True}
        except Exception as e:
            logger.error("WS funding calc fel: %s", e)
            return {"requested": False, "error": str(e)}

    async def start_listening(self):
        """Startar WebSocket-lyssnare i bakgrunden."""
        if not self.is_connected:
            await self.connect()

        # Starta lyssnare i bakgrunden (endast om inte redan startad)
        if not hasattr(self, "_message_listener_task") or self._message_listener_task.done():
            self._message_listener_task = asyncio.create_task(self.listen_for_messages())
            logger.info("🚀 WebSocket-lyssnare startad")
        else:
            logger.info("🚀 WebSocket-lyssnare redan aktiv")


# Global instans för enkel åtkomst
bitfinex_ws = BitfinexWebSocketService()
