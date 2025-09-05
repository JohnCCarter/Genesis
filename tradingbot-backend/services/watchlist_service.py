"""
WatchlistService - extraherad logik för /market/watchlist.

Ansvar:
- Hämta symboler (via Settings/WS_SUBSCRIBE_SYMBOLS eller testlista)
- WS-first hämtning av tickers och candles (1m och 5m)
- Batchad margin-status via REST/WS
- Beräkna strategioutput (1m/5m) och indikator-snapshots
- Valfritt: beräkna sannolikhets-/rekommendationsfält via SignalService
- Enkel in-memory cache med TTL
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from config.settings import Settings
from rest.margin import MarginService as _MS
from services.bitfinex_websocket import bitfinex_ws
from services.market_data_facade import get_market_data
from services.signal_service import SignalService
from services.strategy import evaluate_strategy
from services.symbols import SymbolService
from services.ws_first_data_service import get_ws_first_data_service
from utils.candles import parse_candles_to_strategy_data
from utils.logger import get_logger

logger = get_logger(__name__)


class WatchlistService:
    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_ttl = timedelta(minutes=5)

    async def build_watchlist(self, symbols_param: str | None, include_prob: bool) -> list[dict[str, Any]]:
        cache_key = f"watchlist_{symbols_param}_{include_prob}"
        now = datetime.now()
        cached = self._cache.get(cache_key)
        if cached and (now - cached["timestamp"]) < self._cache_ttl:
            logger.debug("📋 Använder cached watchlist data")
            return cached["data"]  # type: ignore[return-value]

        svc = SymbolService()
        try:
            await svc.refresh()
        except Exception:
            pass

        if symbols_param:
            syms = [s.strip() for s in symbols_param.split(",") if s.strip()]
        else:
            try:
                env_syms = (Settings().WS_SUBSCRIBE_SYMBOLS or "").strip()
                if env_syms:
                    syms = [s.strip() for s in env_syms.split(",") if s.strip()]
                else:
                    syms = svc.get_symbols(test_only=True, fmt="v2")[:10]
            except Exception:
                syms = svc.get_symbols(test_only=True, fmt="v2")[:10]

        # WS live check
        try:
            ws_live_set = set(bitfinex_ws.active_tickers or [])
        except Exception:
            ws_live_set = set()

        # WS-first för marknadsdata
        ws_data_service = get_ws_first_data_service()
        try:
            await ws_data_service.initialize()
        except Exception:
            pass

        tickers: list[Any] = []
        candles_1m: list[Any] = []
        candles_5m: list[Any] = []
        for s in syms:
            try:
                ticker = await ws_data_service.get_ticker(s)
                tickers.append(ticker)
                candles = await ws_data_service.get_candles(s, "1m", 50)
                candles_1m.append(candles)
                candles5 = await ws_data_service.get_candles(s, "5m", 50)
                candles_5m.append(candles5)
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.warning(f"Fel vid hämtning av data för {s}: {e}")
                tickers.append(None)
                candles_1m.append(None)
                candles_5m.append(None)

        # Batchad margin-status
        margin_statuses: dict[str, dict[str, Any]] = {}
        try:
            ms = _MS()
            margin_statuses = await ms.get_symbol_margin_status_batch(syms)
        except Exception as e:
            logger.warning(f"⚠️ Batch margin-status misslyckades: {e}")

        # Bygg svar
        results: list[dict[str, Any]] = []
        env_syms = (Settings().WS_SUBSCRIBE_SYMBOLS or "").strip()
        env_list = [x.strip() for x in env_syms.split(",") if x.strip()]

        for i, s in enumerate(syms):
            try:
                eff = svc.resolve(s)
                listed = bool(svc.listed(eff))
            except Exception:
                eff = s
                listed = None

            show_unlisted = s in env_list
            if listed is False and not show_unlisted:
                continue

            ticker = tickers[i] if i < len(tickers) and not isinstance(tickers[i], Exception) else None
            c1 = candles_1m[i] if i < len(candles_1m) and not isinstance(candles_1m[i], Exception) else None
            c5 = candles_5m[i] if i < len(candles_5m) and not isinstance(candles_5m[i], Exception) else None

            def _safe_float(val: object) -> float | None:
                try:
                    return float(val) if val is not None else None
                except Exception:
                    return None

            last = _safe_float(ticker.get("last_price")) if isinstance(ticker, dict) else None
            vol = _safe_float(ticker.get("volume")) if isinstance(ticker, dict) else None
            ws_live = eff in ws_live_set
            margin_status = margin_statuses.get(s)

            strat = None
            strat_5m = None
            ind1 = (
                ws_data_service.get_indicator_snapshot(s, "1m")
                if hasattr(ws_data_service, "get_indicator_snapshot")
                else None
            )
            ind5 = (
                ws_data_service.get_indicator_snapshot(s, "5m")
                if hasattr(ws_data_service, "get_indicator_snapshot")
                else None
            )

            if c1:
                try:
                    parsed_any = parse_candles_to_strategy_data(c1)
                except Exception:
                    parsed_any = {"closes": [], "highs": [], "lows": []}
                parsed_map: dict[str, Any] = dict(parsed_any) if isinstance(parsed_any, dict) else {}
                parsed_map["symbol"] = s
                if isinstance(ind1, dict):
                    try:
                        parsed_map["ema_snapshot"] = float(ind1.get("ema")) if ind1.get("ema") is not None else None
                        parsed_map["rsi_snapshot"] = float(ind1.get("rsi")) if ind1.get("rsi") is not None else None
                        parsed_map["atr_snapshot"] = float(ind1.get("atr")) if ind1.get("atr") is not None else None
                    except Exception:
                        pass
                strat = evaluate_strategy(parsed_map)  # type: ignore[arg-type]

            if c5:
                try:
                    parsed_any5 = parse_candles_to_strategy_data(c5)
                except Exception:
                    parsed_any5 = {"closes": [], "highs": [], "lows": []}
                parsed_map5: dict[str, Any] = dict(parsed_any5) if isinstance(parsed_any5, dict) else {}
                parsed_map5["symbol"] = s
                if isinstance(ind5, dict):
                    try:
                        parsed_map5["ema_snapshot"] = float(ind5.get("ema")) if ind5.get("ema") is not None else None
                        parsed_map5["rsi_snapshot"] = float(ind5.get("rsi")) if ind5.get("rsi") is not None else None
                        parsed_map5["atr_snapshot"] = float(ind5.get("atr")) if ind5.get("atr") is not None else None
                    except Exception:
                        pass
                strat_5m = evaluate_strategy(parsed_map5)  # type: ignore[arg-type]

            indicators_payload: dict[str, Any] = {}
            if isinstance(ind1, dict) and any(k in ind1 for k in ("ema", "rsi", "atr")):
                indicators_payload["1m"] = {k: ind1.get(k) for k in ("ema", "rsi", "atr")}
            if isinstance(ind5, dict) and any(k in ind5 for k in ("ema", "rsi", "atr")):
                indicators_payload["5m"] = {k: ind5.get(k) for k in ("ema", "rsi", "atr")}

            item: dict[str, Any] = {
                "symbol": s,
                "eff_symbol": eff,
                "listed": listed,
                "ws_live": ws_live,
                "margin_status": margin_status,
                "last": last,
                "volume": vol,
                "strategy": strat,
                "strategy_5m": strat_5m,
                "indicators": indicators_payload or None,
            }

            if include_prob:
                try:
                    ds = get_market_data()
                    candles_prob = await ds.get_candles(s, "1m", 50)
                    if candles_prob:
                        closes = [row[2] for row in candles_prob if isinstance(row, (list, tuple)) and len(row) >= 3]
                        if len(closes) >= 2:
                            price = float(closes[-1])
                            ema = sum(closes[-10:]) / min(10, len(closes))
                            ema_z = (price - ema) / (abs(ema) + 1e-9)
                            sc = SignalService().score(regime="trend", adx_value=20.0, ema_z_value=ema_z)
                            item["prob"] = {
                                "probabilities": {
                                    "buy": round(sc.probability / 100.0, 6),
                                    "sell": round(1.0 - (sc.probability / 100.0), 6),
                                },
                                "decision": (
                                    "buy"
                                    if sc.recommendation == "buy"
                                    else ("abstain" if sc.recommendation == "hold" else "sell")
                                ),
                                "ev": round(sc.probability / 100.0, 6),
                            }
                except Exception as pe:
                    item["prob_error"] = str(pe)[:120]

            results.append(item)

        self._cache[cache_key] = {"data": results, "timestamp": now}
        return results


_watchlist_service: WatchlistService | None = None


def get_watchlist_service() -> WatchlistService:
    global _watchlist_service
    if _watchlist_service is None:
        _watchlist_service = WatchlistService()
    return _watchlist_service
