"""
Scheduler Service - TradingBot Backend

Denna modul kör lätta, periodiska uppgifter i bakgrunden utan externa
beroenden. Fokus är stabilitet vid utveckling och enkelhet i drift.

Nuvarande jobb:
- Equity-snapshot (dagligen, idempotent) via PerformanceService
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime, timedelta, timezone
from typing import List, Optional

from config.settings import Settings
from utils.candle_cache import candle_cache
from utils.logger import get_logger

logger = get_logger(__name__)


class SchedulerService:
    """Enkel asynkron schemaläggare baserad på asyncio-sleep.

    - Använder en enda bakgrunds-Task som loopar och kör definierade jobb
      med ett minimumintervall.
    - Undviker tredjepartsbibliotek (t.ex. aioschedule) för att minska
      beroenden och underlätta testning.
    """

    def __init__(self, *, snapshot_interval_seconds: int = 60 * 15) -> None:
        # Kör snapshot var 15:e minut (idempotent – uppdaterar dagens rad)
        self.snapshot_interval_seconds = max(60, int(snapshot_interval_seconds))
        self._task: asyncio.Task | None = None
        self._running: bool = False
        self._last_snapshot_at: datetime | None = None
        self._last_retention_at: datetime | None = None
        self._last_prob_validate_at: datetime | None = None
        self._last_prob_retrain_at: datetime | None = None

    def start(self) -> None:
        """Starta bakgrundsloopen om den inte redan körs."""
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="scheduler-loop")
        logger.info("🗓️ Scheduler startad")

    async def stop(self) -> None:
        """Stoppa bakgrundsloopen och vänta på att Tasken avslutas."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("🛑 Scheduler stoppad")

    async def _run_loop(self) -> None:
        """Huvudloop för periodiska jobb."""
        # Första körning direkt vid start för att få en initial snapshot
        await self._safe_run_equity_snapshot(reason="startup")
        next_run_at = datetime.now(UTC)
        while self._running:
            try:
                now = datetime.now(UTC)
                if now >= next_run_at:
                    await self._safe_run_equity_snapshot(reason="interval")
                    next_run_at = now.replace(microsecond=0) + timedelta(
                        seconds=self.snapshot_interval_seconds
                    )
                # Kör cache-retention högst en gång per 6 timmar
                await self._maybe_enforce_cache_retention(now)
                # Kör probabilistisk validering enligt intervall
                await self._maybe_run_prob_validation(now)
                # Kör schemalagd retraining
                await self._maybe_run_prob_retraining(now)
                # Sov en kort stund för att inte spinna
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("%s", f"Scheduler-loop fel: {e}")
                await asyncio.sleep(5)

    async def run_prob_validation_once(self) -> None:
        """Kör probabilistisk validering en gång direkt (ignorerar intervall‑spärr).

        Används vid uppstart som "warm-up" när runtime‑flaggan är påslagen.
        """
        try:
            # Säkerställ att nästa körning inte blockeras av intervallet
            self._last_prob_validate_at = None
            now = datetime.now(UTC)
            await self._maybe_run_prob_validation(now)
        except Exception as e:
            logger.debug("%s", f"Warm-up prob validation fel: {e}")

    async def _safe_run_equity_snapshot(self, *, reason: str) -> None:
        """Kör equity-snapshot säkert och logga eventuella fel."""
        try:
            from services.performance import PerformanceService

            svc = PerformanceService()
            result = await svc.snapshot_equity()
            self._last_snapshot_at = datetime.now(UTC)
            logger.info(
                "💾 Equity-snapshot uppdaterad",
            )
            # Skicka valfri notis till UI (tyst misslyckande om WS ej initierat)
            try:
                from ws.manager import socket_app

                asyncio.create_task(
                    socket_app.emit(
                        "notification",
                        {
                            "type": "info",
                            "title": "Equity snapshot",
                            "payload": {"reason": reason, **result},
                        },
                    )
                )
            except Exception:
                pass
        except Exception as e:
            logger.warning("%s", f"Kunde inte ta equity-snapshot: {e}")

    async def _maybe_enforce_cache_retention(self, now: datetime) -> None:
        """Enforce TTL/retention på candle-cache med låg frekvens.

        Läser inställningar vid varje körning så ändringar i .env fångas.
        Kör endast om minst 6 timmar förflutit sedan senaste körning.
        """
        try:
            if self._last_retention_at and (now - self._last_retention_at) < timedelta(hours=6):
                return
            s = Settings()
            days = int(getattr(s, "CANDLE_CACHE_RETENTION_DAYS", 0) or 0)
            max_rows = int(getattr(s, "CANDLE_CACHE_MAX_ROWS_PER_PAIR", 0) or 0)
            if days <= 0 and max_rows <= 0:
                return
            removed = candle_cache.enforce_retention(days, max_rows)
            self._last_retention_at = now
            if removed:
                logger.info(f"🧹 Candle-cache retention: tog bort {removed} rader")
        except Exception as e:
            logger.warning("%s", f"Retention fel: {e}")

    async def _maybe_run_prob_validation(self, now: datetime) -> None:
        """Periodisk validering av sannolikhetsmodell (Brier/LogLoss).

        Läser symboler/timeframe och intervall från Settings.
        Uppdaterar metrics_store med senaste värden per symbol/tf samt aggregat.
        """
        try:
            from services.bitfinex_data import BitfinexDataService
            from services.metrics import metrics_store
            from services.prob_validation import validate_on_candles

            s = Settings()
            if not bool(getattr(s, "PROB_VALIDATE_ENABLED", True)):
                return
            interval_minutes = int(getattr(s, "PROB_VALIDATE_INTERVAL_MINUTES", 60) or 60)
            if self._last_prob_validate_at and (now - self._last_prob_validate_at) < timedelta(
                minutes=max(1, interval_minutes)
            ):
                return
            raw_syms = (getattr(s, "PROB_VALIDATE_SYMBOLS", None) or "").strip()
            if raw_syms:
                symbols = [x.strip() for x in raw_syms.split(",") if x.strip()]
            else:
                # fallback till WS_SUBSCRIBE_SYMBOLS eller standard BTCUSD
                env_syms = (getattr(s, "WS_SUBSCRIBE_SYMBOLS", None) or "").strip()
                symbols = [x.strip() for x in env_syms.split(",") if x.strip()]
                if not symbols:
                    symbols = [f"t{getattr(s, 'DEFAULT_TRADING_PAIR', 'BTCUSD')}"]
            tf = str(getattr(s, "PROB_VALIDATE_TIMEFRAME", "1m") or "1m")
            limit = int(getattr(s, "PROB_VALIDATE_LIMIT", 1200) or 1200)
            max_samples = int(getattr(s, "PROB_VALIDATE_MAX_SAMPLES", 500) or 500)

            data = BitfinexDataService()
            agg_brier_vals: list[float] = []
            agg_logloss_vals: list[float] = []
            for sym in symbols:
                try:
                    candles = await data.get_candles(sym, tf, limit)
                    if not candles:
                        continue
                    res = validate_on_candles(
                        candles,
                        horizon=int(getattr(s, "PROB_MODEL_TIME_HORIZON", 20) or 20),
                        tp=float(getattr(s, "PROB_MODEL_EV_THRESHOLD", 0.0005) or 0.0005),
                        sl=float(getattr(s, "PROB_MODEL_EV_THRESHOLD", 0.0005) or 0.0005),
                        max_samples=max_samples,
                    )
                    key = f"{sym}|{tf}"
                    pv = metrics_store.setdefault("prob_validation", {})
                    by = pv.setdefault("by", {})
                    by[key] = {
                        "brier": res.get("brier"),
                        "logloss": res.get("logloss"),
                        "ts": int(now.timestamp()),
                    }
                    if res.get("brier") is not None:
                        agg_brier_vals.append(float(res["brier"]))
                    if res.get("logloss") is not None:
                        agg_logloss_vals.append(float(res["logloss"]))
                except Exception as ie:
                    logger.debug(f"prob validation misslyckades för {sym}: {ie}")
            # aggregat (medel över symboler)
            if agg_brier_vals:
                metrics_store.setdefault("prob_validation", {})["brier"] = sum(
                    agg_brier_vals
                ) / max(1, len(agg_brier_vals))
            if agg_logloss_vals:
                metrics_store.setdefault("prob_validation", {})["logloss"] = sum(
                    agg_logloss_vals
                ) / max(1, len(agg_logloss_vals))
            # rolling windows
            try:
                windows_raw = getattr(s, "PROB_VALIDATE_WINDOWS_MINUTES", None) or ""
                if windows_raw:
                    from time import time as _now

                    now_ts = int(_now())
                    windows = [int(x) for x in windows_raw.split(",") if str(x).strip().isdigit()]
                    pv = metrics_store.setdefault("prob_validation", {})
                    roll = pv.setdefault("rolling", {})
                    # Lägg till punkt för varje fönster
                    for w in windows:
                        key = str(w)
                        arr = roll.setdefault(key, [])
                        arr.append(
                            {
                                "ts": now_ts,
                                "brier": pv.get("brier"),
                                "logloss": pv.get("logloss"),
                            }
                        )
                        # Retention grooming per fönster
                        max_pts = int(getattr(s, "PROB_VALIDATE_HISTORY_MAX_POINTS", 1000) or 1000)
                        if len(arr) > max_pts:
                            del arr[: len(arr) - max_pts]
            except Exception:
                pass
            self._last_prob_validate_at = now
            logger.info(
                "%s",
                f"📈 Prob validation uppdaterad för {len(symbols)} symboler (tf={tf})",
            )
        except Exception as e:
            logger.debug("%s", f"Prob validation fel: {e}")

    async def _maybe_run_prob_retraining(self, now: datetime) -> None:
        """Schemalagd batchträning och atomisk modelswap+reload.

        Enkel baseline: tränar per symbol/tf från REST candles och
        skriver JSON till models-katalog. Därefter reload i runtime.
        """
        try:
            import os

            from services.bitfinex_data import BitfinexDataService
            from services.metrics import metrics_store
            from services.prob_model import prob_model
            from services.prob_train import train_and_export

            s = Settings()
            if not bool(getattr(s, "PROB_RETRAIN_ENABLED", False)):
                return
            interval_hours = int(getattr(s, "PROB_RETRAIN_INTERVAL_HOURS", 24) or 24)
            if self._last_prob_retrain_at and (now - self._last_prob_retrain_at) < timedelta(
                hours=max(1, interval_hours)
            ):
                return
            raw_syms = (getattr(s, "PROB_RETRAIN_SYMBOLS", None) or "").strip()
            if raw_syms:
                symbols = [x.strip() for x in raw_syms.split(",") if x.strip()]
            else:
                env_syms = (getattr(s, "WS_SUBSCRIBE_SYMBOLS", None) or "").strip()
                symbols = [x.strip() for x in env_syms.split(",") if x.strip()]
                if not symbols:
                    symbols = [f"t{getattr(s, 'DEFAULT_TRADING_PAIR', 'BTCUSD')}"]
            tf = str(getattr(s, "PROB_RETRAIN_TIMEFRAME", "1m") or "1m")
            limit = int(getattr(s, "PROB_RETRAIN_LIMIT", 5000) or 5000)
            out_dir = str(getattr(s, "PROB_RETRAIN_OUTPUT_DIR", "config/models"))
            os.makedirs(out_dir, exist_ok=True)

            data = BitfinexDataService()
            from services.symbols import SymbolService

            sym_svc = SymbolService()
            await sym_svc.refresh()

            for sym in symbols:
                try:
                    eff = sym_svc.resolve(sym)
                    candles = await data.get_candles(sym, tf, limit)
                    if not candles:
                        continue
                    # använder horizon/tp/sl från settings (samma som inferens)
                    horizon = int(getattr(s, "PROB_MODEL_TIME_HORIZON", 20) or 20)
                    tp = float(getattr(s, "PROB_MODEL_EV_THRESHOLD", 0.0005) or 0.0005)
                    sl = tp
                    # skriv fil: SYMBOL_TIMEFRAME.json
                    clean = eff[1:] if eff.startswith("t") else eff
                    try:
                        clean = re.sub(r"[^A-Za-z0-9_]", "_", clean)
                    except Exception:
                        pass
                    fname = f"{clean}_{tf}.json"
                    out_path = os.path.join(out_dir, fname)
                    train_and_export(candles, horizon=horizon, tp=tp, sl=sl, out_path=out_path)
                    metrics_store.setdefault("prob_retrain", {})["events"] = (
                        int(metrics_store.get("prob_retrain", {}).get("events", 0)) + 1
                    )
                except Exception as ie:
                    metrics_store.setdefault("prob_retrain", {})["last_error"] = str(ie)
            # försök reload om PROB_MODEL_FILE pekar på en fil vi just skrev
            try:
                if prob_model.reload():
                    metrics_store.setdefault("prob_retrain", {})["last_success"] = int(
                        now.timestamp()
                    )
            except Exception:
                pass
            self._last_prob_retrain_at = now
        except Exception as e:
            logger.debug("%s", f"Prob retraining fel: {e}")


# En global instans som kan återanvändas av applikationen
scheduler = SchedulerService()
