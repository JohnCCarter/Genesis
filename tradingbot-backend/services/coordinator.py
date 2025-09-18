# AI Change: Add CoordinatorService to own business logic for scheduled jobs (Agent: Codex, Date: 2025-09-11)
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


class CoordinatorService:
    """Äger affärslogik för schemalagda jobb.

    Scheduler anropar endast dessa metoder; ingen affärslogik i scheduler.
    """

    async def equity_snapshot(self, *, reason: str) -> dict[str, Any]:
        from services.performance import PerformanceService

        svc = PerformanceService()
        result = await svc.snapshot_equity()
        # Minimalt svar för /metrics och notiser
        return {
            "ok": True,
            **(result or {}),
            "reason": reason,
            "ts": datetime.now(UTC).isoformat(),
        }

    async def enforce_candle_cache_retention(self) -> dict[str, Any]:
        from utils.candle_cache import candle_cache

        s = settings
        days = int(getattr(s, "CANDLE_CACHE_RETENTION_DAYS", 0) or 0)
        max_rows = int(getattr(s, "CANDLE_CACHE_MAX_ROWS_PER_PAIR", 0) or 0)
        if days <= 0 and max_rows <= 0:
            return {"ok": True, "removed": 0}
        removed = candle_cache.enforce_retention(days, max_rows)
        return {"ok": True, "removed": int(removed)}

    async def prob_validation(self) -> dict[str, Any]:
        from services.market_data_facade import get_market_data
        from services.metrics import metrics_store
        from services.prob_validation import validate_on_candles

        s = settings
        if not bool(getattr(s, "PROB_VALIDATE_ENABLED", True)):
            return {"ok": False, "disabled": True}
        raw_syms = (getattr(s, "PROB_VALIDATE_SYMBOLS", None) or "").strip()
        symbols = [x.strip() for x in raw_syms.split(",") if x.strip()] if raw_syms else []
        if not symbols:
            env_syms = (getattr(s, "WS_SUBSCRIBE_SYMBOLS", None) or "").strip()
            symbols = [x.strip() for x in env_syms.split(",") if x.strip()] or [
                f"t{getattr(s, 'DEFAULT_TRADING_PAIR', 'BTCUSD')}"
            ]
        tf = str(getattr(s, "PROB_VALIDATE_TIMEFRAME", "1m") or "1m")
        limit = int(getattr(s, "PROB_VALIDATE_LIMIT", 1200) or 1200)
        horizon = int(getattr(s, "PROB_MODEL_TIME_HORIZON", 20) or 20)
        tp = float(getattr(s, "PROB_MODEL_EV_THRESHOLD", 0.0005) or 0.0005)
        sl = float(getattr(s, "PROB_MODEL_EV_THRESHOLD", 0.0005) or 0.0005)

        data = get_market_data()
        agg_brier: list[float] = []
        agg_logloss: list[float] = []
        for sym in symbols:
            candles = await data.get_candles(sym, tf, limit)
            if not candles:
                continue
            res = validate_on_candles(
                candles,
                horizon=horizon,
                tp=tp,
                sl=sl,
                max_samples=int(getattr(s, "PROB_VALIDATE_MAX_SAMPLES", 500) or 500),
                symbol=sym,
                timeframe=tf,
            )
            key = f"{sym}|{tf}"
            pv = metrics_store.setdefault("prob_validation", {})
            by = pv.setdefault("by", {})
            by[key] = {
                "brier": res.get("brier"),
                "logloss": res.get("logloss"),
                "ts": int(datetime.now(UTC).timestamp()),
            }
            if res.get("brier") is not None:
                agg_brier.append(float(res["brier"]))
            if res.get("logloss") is not None:
                agg_logloss.append(float(res["logloss"]))
        if agg_brier:
            metrics_store.setdefault("prob_validation", {})["brier"] = sum(agg_brier) / max(1, len(agg_brier))
        if agg_logloss:
            metrics_store.setdefault("prob_validation", {})["logloss"] = sum(agg_logloss) / max(1, len(agg_logloss))
        return {"ok": True, "symbols": len(symbols)}

    async def prob_retrain(self) -> dict[str, Any]:
        from services.market_data_facade import get_market_data
        from services.metrics import metrics_store
        from services.prob_model import prob_model
        from services.prob_train import train_and_export
        from services.symbols import SymbolService
        import os
        import re

        s = settings
        if not bool(getattr(s, "PROB_RETRAIN_ENABLED", False)):
            return {"ok": False, "disabled": True}
        raw_syms = (getattr(s, "PROB_RETRAIN_SYMBOLS", None) or "").strip()
        symbols = [x.strip() for x in raw_syms.split(",") if x.strip()] if raw_syms else []
        if not symbols:
            env_syms = (getattr(s, "WS_SUBSCRIBE_SYMBOLS", None) or "").strip()
            symbols = [x.strip() for x in env_syms.split(",") if x.strip()] or [
                f"t{getattr(s, 'DEFAULT_TRADING_PAIR', 'BTCUSD')}"
            ]
        tf = str(getattr(s, "PROB_RETRAIN_TIMEFRAME", "1m") or "1m")
        limit = int(getattr(s, "PROB_RETRAIN_LIMIT", 5000) or 5000)
        out_dir = str(getattr(s, "PROB_RETRAIN_OUTPUT_DIR", "config/models"))
        os.makedirs(out_dir, exist_ok=True)

        data = get_market_data()
        sym_svc = SymbolService()
        await sym_svc.refresh()

        events = 0
        for sym in symbols:
            eff = sym_svc.resolve(sym)
            candles = await data.get_candles(sym, tf, limit)
            if not candles:
                continue
            horizon = int(getattr(s, "PROB_MODEL_TIME_HORIZON", 20) or 20)
            tp = float(getattr(s, "PROB_MODEL_EV_THRESHOLD", 0.0005) or 0.0005)
            sl = tp
            clean = eff[1:] if eff.startswith("t") else eff
            clean = re.sub(r"[^A-Za-z0-9_]", "_", clean)
            fname = f"{clean}_{tf}.json"
            out_path = os.path.join(out_dir, fname)
            train_and_export(candles, horizon=horizon, tp=tp, sl=sl, out_path=out_path)
            events += 1
        try:
            if prob_model.reload():
                metrics_store.setdefault("prob_retrain", {})["last_success"] = int(datetime.now(UTC).timestamp())
        except Exception:
            pass
        metrics_store.setdefault("prob_retrain", {})["events"] = (
            int(metrics_store.get("prob_retrain", {}).get("events", 0)) + events
        )
        return {"ok": True, "events": events}

    async def update_regime(self) -> dict[str, Any]:
        from services.strategy import update_settings_from_regime_batch

        s = settings
        raw_syms = (getattr(s, "WS_SUBSCRIBE_SYMBOLS", None) or "").strip()
        symbols = [x.strip() for x in raw_syms.split(",") if x.strip()] if raw_syms else []
        if not symbols:
            symbols = [f"t{getattr(s, 'DEFAULT_TRADING_PAIR', 'BTCUSD')}"]
        try:
            res = update_settings_from_regime_batch(symbols=symbols)
            return {"ok": True, "updated": len(res or {})}
        except Exception as e:
            logger.debug(f"update_regime fel: {e}")
            return {"ok": False, "updated": 0}


_coordinator_singleton: CoordinatorService | None = None


def get_coordinator() -> CoordinatorService:
    global _coordinator_singleton
    if _coordinator_singleton is None:
        _coordinator_singleton = CoordinatorService()
    return _coordinator_singleton
