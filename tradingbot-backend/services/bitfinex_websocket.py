"""
Bitfinex WebSocket Service - TradingBot Backend

Denna modul hanterar WebSocket-anslutning till Bitfinex för realtids tickdata.
Inkluderar automatisk återanslutning och tickdata-hantering.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from websockets.client import connect as ws_connect  # type: ignore[attr-defined]
from websockets.exceptions import ConnectionClosed  # type: ignore[attr-defined]

from config.settings import Settings
from utils.logger import get_logger
from ws.auth import build_ws_auth_payload

logger = get_logger(__name__)


class BitfinexWebSocketService:
    """Service för WebSocket-anslutning till Bitfinex."""

    def __init__(self):
        self.settings = Settings()
        # Standard: använd auth-URI (api) som bas. Publika subar kan specialhanteras vid behov.
        self.ws_url = (
            getattr(self.settings, "BITFINEX_WS_AUTH_URI", None)
            or self.settings.BITFINEX_WS_URI
        )
        self.websocket = None
        self.is_connected = False
        self.is_authenticated = False
        self.subscriptions = {}
        self.callbacks = {}
        self.channel_callbacks = {}
        self.channel_info = {}
        self.private_event_callbacks = {}
        self.latest_prices = {}  # Spara senaste priser
        self.price_history = {}  # Spara pris-historik för strategi
        self._last_tick_ts = {}  # symbol -> last tick timestamp
        self.latest_ticker_frames = (
            {}
        )  # symbol -> senaste fulla ticker-dict (bid/ask/vol/high/low)
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
        # WS Margin state
        self.margin_base = None  # type: ignore[assignment]
        self.margin_sym: Dict[str, list] = {}
        self._last_margin_ts = None  # type: ignore[assignment]
        self._last_margin_sym_ts: Dict[str, float] = {}
        # Registrera default-handler för margin info updates (miu)
        self.private_event_callbacks["miu"] = self._handle_miu

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

    async def send(self, payload: Any):
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
            # Starta lyssnare i bakgrunden direkt för att fånga auth-ack
            self._asyncio.create_task(self.listen_for_messages())
            # Försök autentisera om nycklar finns
            await self.authenticate()
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
                logger.warning(
                    "⚠️ Ingen auth-bekräftelse inom timeout. Fortsätter utan auth."
                )
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
        price: Optional[float] = None,
        amount: Optional[float] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Skicka WS order update (ou) för att uppdatera pris/mängd/flags.

        Args:
            order_id: ID för ordern
            price: nytt pris (valfritt)
            amount: ny mängd (valfritt)
            extra: extra fält att inkludera (t.ex. flags)

        Returns:
            Dict med status
        """
        payload: Dict[str, Any] = {"id": int(order_id)}
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
        ids: Optional[List[int]] = None,
        cids: Optional[List[int]] = None,
        cid_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Skicka WS oc_multi för att avbryta flera ordrar.

        Stödjer både id-lista och cid+cid_date-lista.
        """
        items: List[Dict[str, Any]] = []
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
            logger.info(
                "🧹 WS oc_multi skickad: ids=%s cids=%s", ids or [], cids or []
            )
            return {"success": True, "count": len(items)}
        except Exception as e:
            logger.error(f"❌ WS oc_multi fel: {e}")
            return {"success": False, "error": str(e)}

    async def order_ops(self, ops: List[Any]) -> Dict[str, Any]:
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
        normalized: List[List[Any]] = []
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
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            logger.info("🔌 Frånkopplad från Bitfinex WebSocket")
        # Rensa aktivitetsstatus
        self.active_tickers.clear()
        self._live_notified.clear()
        self.margin_base = None
        self.margin_sym.clear()

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
            # Dedupe: hoppa över om redan aktiv eller pending
            key = f"ticker|{symbol}"
            if symbol in self.active_tickers or key in self.subscriptions:
                logger.info(f"ℹ️ Ticker redan aktiv/pending: {symbol}")
                # Säkerställ callback är satt
                if key not in self.callbacks:
                    self.callbacks[key] = callback
                return
            # Skapa subscription-meddelande
            subscribe_msg = {
                "event": "subscribe",
                "channel": "ticker",
                "symbol": symbol,
            }

            if not self.websocket:
                logger.warning("WS subscribe_ticker: ingen anslutning")
                return
            await self.websocket.send(json.dumps(subscribe_msg))
            self.subscriptions[key] = subscribe_msg
            self.callbacks[key] = callback

            logger.info(f"📊 Prenumererar på ticker för {symbol}")

        except Exception as e:
            logger.error(f"❌ Ticker-prenumeration misslyckades: {e}")

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

            subscribe_msg = {
                "event": "subscribe",
                "channel": "trades",
                "symbol": symbol,
            }

            if not self.websocket:
                logger.warning("WS subscribe_trades: ingen anslutning")
                return
            await self.websocket.send(json.dumps(subscribe_msg))
            key = f"trades|{symbol}"
            self.subscriptions[key] = subscribe_msg
            self.callbacks[key] = callback

            logger.info(f"💱 Prenumererar på trades för {symbol}")

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

            # Prenumerera på ticker
            await self.subscribe_ticker(symbol, self._handle_ticker_with_strategy)

            logger.info(f"🎯 Prenumererar på {symbol} med strategiutvärdering")

        except Exception as e:
            logger.error(f"❌ Strategi-prenumeration misslyckades: {e}")

    async def subscribe_candles(self, symbol: str, timeframe: str, callback: Callable):
        """Prenumerera på candles (WS public). key = trade:tf:symbol"""
        try:
            if not self.is_connected:
                await self.connect()

            ckey = f"trade:{timeframe}:{symbol}"
            msg = {"event": "subscribe", "channel": "candles", "key": ckey}
            if not self.websocket:
                logger.warning("WS subscribe_candles: ingen anslutning")
                return
            await self.websocket.send(json.dumps(msg))
            sub_key = f"candles|{ckey}"
            self.subscriptions[sub_key] = msg
            self.callbacks[sub_key] = callback
            logger.info(f"🕯️ Prenumererar på candles {ckey}")
        except Exception as e:
            logger.error(f"❌ Candles-prenumeration misslyckades: {e}")

    async def subscribe_book(
        self,
        symbol: str,
        precision: str = "P0",
        freq: str = "F0",
        length: int = 25,
        callback: Optional[Callable] = None,
    ):
        """Prenumerera på orderbok (WS public)."""
        try:
            if not self.is_connected:
                await self.connect()

            msg = {
                "event": "subscribe",
                "channel": "book",
                "symbol": symbol,
                "prec": precision,
                "freq": freq,
                "len": length,
            }
            if not self.websocket:
                logger.warning("WS subscribe_book: ingen anslutning")
                return
            await self.websocket.send(json.dumps(msg))
            key = f"book|{symbol}|{precision}|{freq}|{length}"
            self.subscriptions[key] = msg
            if callback:
                self.callbacks[key] = callback
            logger.info(
                f"📖 Prenumererar på orderbok {symbol} {precision}/{freq}/{length}"
            )
        except Exception as e:
            logger.error(f"❌ Orderbok-prenumeration misslyckades: {e}")

    async def _handle_ticker_with_strategy(self, ticker_data: Dict):
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

            # Lägg till i pris-historik (behåll senaste 100 datapunkter)
            if symbol not in self.price_history:
                self.price_history[symbol] = []

            self.price_history[symbol].append(price)
            if len(self.price_history[symbol]) > 100:
                self.price_history[symbol].pop(0)

            # Kör strategiutvärdering om vi har tillräckligt med data
            if len(self.price_history[symbol]) >= 30:  # Minst 30 datapunkter
                # Throttle: max 1 eval/sek per symbol
                import time as _t

                now_s = _t.time()
                last_eval = float(self._last_eval_ts.get(symbol, 0))
                if now_s - last_eval >= 1.0:
                    self._last_eval_ts[symbol] = now_s
                    await self._evaluate_strategy_for_symbol(symbol)

        except Exception as e:
            logger.error(f"❌ Fel vid hantering av ticker med strategi: {e}")

    async def _evaluate_strategy_for_symbol(self, symbol: str):
        """
        Utvärderar strategi för en symbol baserat på pris-historik.

        Args:
            symbol: Trading pair
        """
        try:
            from services.strategy import evaluate_strategy

            # Förbered data för strategiutvärdering
            prices = self.price_history[symbol]

            # Skapa mock-data för strategi (eftersom vi bara har closes)
            strategy_data = {
                "closes": prices,
                "highs": prices,  # Använd samma värden som approximation
                "lows": prices,  # Använd samma värden som approximation
            }

            # Utvärdera strategi
            result = evaluate_strategy(strategy_data)

            # Lägg till symbol och timestamp
            result["symbol"] = symbol
            result["current_price"] = self.latest_prices.get(symbol, 0)
            result["timestamp"] = datetime.now().isoformat()

            # Anropa callback om den finns
            if symbol in self.strategy_callbacks:
                await self.strategy_callbacks[symbol](result)

            # Logga endast vid tillståndsskifte eller var 30s vid oförändrat läge
            import time as _t

            now_s = _t.time()
            last_sig = self._last_strategy_signal.get(symbol)
            last_reason = self._last_strategy_reason.get(symbol)
            last_log = float(self._last_strategy_log_ts.get(symbol, 0))
            changed = (
                result.get("signal") != last_sig or result.get("reason") != last_reason
            )

            # Underlätta: spamma inte "Otillräcklig data" annat än var 60s om oförändrat
            reason = str(result.get("reason", ""))
            min_interval = 30.0
            if "Otillräcklig data" in reason:
                min_interval = 60.0

            if changed or (now_s - last_log) >= min_interval:
                logger.info(
                    f"🎯 Strategiutvärdering för {symbol}: {result['signal']} - {result['reason']}"
                )
                self._last_strategy_signal[symbol] = result.get("signal")
                self._last_strategy_reason[symbol] = result.get("reason")
                self._last_strategy_log_ts[symbol] = now_s

        except Exception as e:
            logger.error(f"❌ Fel vid strategiutvärdering för {symbol}: {e}")

    async def listen_for_messages(self):
        """Lyssnar på WebSocket-meddelanden."""
        try:
            logger.info("👂 Lyssnar på WebSocket-meddelanden...")

            async for message in self.websocket:
                try:
                    data = json.loads(message)

                    # Hantera olika meddelandetyper
                    if isinstance(data, list) and len(data) > 1:
                        await self._handle_channel_message(data)
                    elif isinstance(data, dict):
                        await self._handle_event_message(data)

                except json.JSONDecodeError:
                    logger.warning("⚠️ Kunde inte parsa WebSocket-meddelande")
                except Exception as e:
                    logger.error(f"❌ Fel vid hantering av WebSocket-meddelande: {e}")

        except ConnectionClosed:
            logger.warning("⚠️ WebSocket-anslutning stängd")
            self.is_connected = False
        except Exception as e:
            logger.error(f"❌ WebSocket-lyssnare fel: {e}")

    async def _handle_channel_message(self, data: List):
        """Hanterar kanal-meddelanden (publika och privata)."""
        try:
            channel_id = data[0]
            message_data = data[1]

            # Privata kontohändelser sker på channel_id 0 med event-kod som andra element
            if channel_id == 0:
                # Format: [0, 'EVENT_CODE', payload]
                if isinstance(message_data, str):
                    event_code = message_data
                    cb = self.private_event_callbacks.get(event_code)
                    if cb:
                        # Skicka hela ursprungsmeddelandet så handlers kan läsa msg[1] och msg[2]
                        await cb(data)
                    else:
                        logger.debug(f"ℹ️ Ohanterad privat händelse: {event_code}")
                else:
                    # Heartbeat: [0, 'hb'] eller liknande
                    if message_data == "hb":
                        return
                    logger.debug(f"ℹ️ Oväntat privat meddelande: {data}")
                return

            # Publika kanaler via chanId‑mapping
            cb = self.channel_callbacks.get(int(channel_id))
            if cb:
                # Ignorera heartbeat
                if message_data == "hb":
                    return
                info = self.channel_info.get(int(channel_id)) or {}
                chan = info.get("channel")
                symbol = info.get("symbol") or "unknown"
                # Normalisera ticker-frame till dict
                if (
                    chan == "ticker"
                    and isinstance(message_data, list)
                    and len(message_data) >= 7
                ):
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
                    await cb(norm)
                    return
                # För övriga kanaler, skicka rå payload vidare
                await cb(message_data)
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
                    if k.startswith("ticker|") and ticker_data["symbol"] in k:
                        await callback(ticker_data)
                        break

        except Exception as e:
            logger.error(f"❌ Fel vid hantering av kanal-meddelande: {e}")

    def _get_symbol_from_channel_id(self, channel_id: int) -> str:
        """Hämtar symbol från channel ID baserat på prenumerationer."""
        for symbol, sub_data in self.subscriptions.items():
            if "ticker" in str(sub_data):
                return symbol
        return "unknown"

    async def _handle_event_message(self, data: Dict):
        """Hanterar event-meddelanden (subscribe, auth, etc.)."""
        try:
            event = data.get("event")

            if event == "subscribed":
                chan = data.get("channel")
                chan_id = (
                    data.get("chanId") or data.get("chanid") or data.get("chan_id")
                )
                symbol = data.get("symbol")
                key = data.get("key")
                logger.info(
                    f"✅ Prenumeration bekräftad: channel={chan} symbol={symbol or key} chanId={chan_id}"
                )
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
                        self.channel_callbacks[int(chan_id)] = self.callbacks.get(
                            cb_key
                        )
                        self.channel_info[int(chan_id)] = {
                            "channel": chan,
                            "symbol": symbol,
                            "key": key,
                        }
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
                    logger.error(f"❌ WebSocket-fel: {msg}")
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

    async def start_listening(self):
        """Startar WebSocket-lyssnare i bakgrunden."""
        if not self.is_connected:
            await self.connect()

        # Starta lyssnare i bakgrunden
        asyncio.create_task(self.listen_for_messages())
        logger.info("🚀 WebSocket-lyssnare startad")


# Global instans för enkel åtkomst
bitfinex_ws = BitfinexWebSocketService()
