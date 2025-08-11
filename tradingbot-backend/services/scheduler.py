"""
Scheduler Service - TradingBot Backend

Denna modul kör lätta, periodiska uppgifter i bakgrunden utan externa
beroenden. Fokus är stabilitet vid utveckling och enkelhet i drift.

Nuvarande jobb:
- Equity-snapshot (dagligen, idempotent) via PerformanceService
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

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
        self._task: Optional[asyncio.Task] = None
        self._running: bool = False
        self._last_snapshot_at: Optional[datetime] = None
        self._last_retention_at: Optional[datetime] = None

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
        next_run_at = datetime.now(timezone.utc)
        while self._running:
            try:
                now = datetime.now(timezone.utc)
                if now >= next_run_at:
                    await self._safe_run_equity_snapshot(reason="interval")
                    next_run_at = now.replace(microsecond=0) + timedelta(
                        seconds=self.snapshot_interval_seconds
                    )
                # Kör cache-retention högst en gång per 6 timmar
                await self._maybe_enforce_cache_retention(now)
                # Sov en kort stund för att inte spinna
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler-loop fel: {e}")
                await asyncio.sleep(5)

    async def _safe_run_equity_snapshot(self, *, reason: str) -> None:
        """Kör equity-snapshot säkert och logga eventuella fel."""
        try:
            from services.performance import PerformanceService

            svc = PerformanceService()
            result = await svc.snapshot_equity()
            self._last_snapshot_at = datetime.now(timezone.utc)
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
            logger.warning(f"Kunde inte ta equity-snapshot: {e}")

    async def _maybe_enforce_cache_retention(self, now: datetime) -> None:
        """Enforce TTL/retention på candle-cache med låg frekvens.

        Läser inställningar vid varje körning så ändringar i .env fångas.
        Kör endast om minst 6 timmar förflutit sedan senaste körning.
        """
        try:
            if self._last_retention_at and (now - self._last_retention_at) < timedelta(
                hours=6
            ):
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
            logger.warning(f"Retention fel: {e}")


# En global instans som kan återanvändas av applikationen
scheduler = SchedulerService()
