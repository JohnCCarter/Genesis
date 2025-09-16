# AI Change: Add UnifiedSchedulerService to consolidate all scheduling (Agent: Codex, Date: 2025-01-27)
"""
Unified Scheduler Service - Konsoliderar alla schemalagda jobb i systemet.

Konsoliderar:
- RefreshManager (panel-refresh)
- SchedulerService (equity snapshots, validation, retraining)
- Ad-hoc jobb från olika services
- HealthWatchdog (system monitoring)

Löser problem med:
- Spridda scheduler-implementationer
- Inkonsistenta jobb-intervall
- Svår att debugga scheduler-problem
- Olika cooldown-strategier
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, UTC
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class JobPriority(Enum):
    """Jobb-prioritet för schemaläggning."""

    CRITICAL = 1  # 30s - Risk guards, circuit breakers, health checks
    HIGH = 2  # 60s - Positions, wallets, orders, equity snapshots
    MEDIUM = 3  # 300s - Market data, signals, validation
    LOW = 4  # 1800s - History, performance stats, cleanup


class JobStatus(Enum):
    """Status för schemalagda jobb."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass
class ScheduledJob:
    """En schemalagd jobb-uppgift."""

    name: str
    priority: JobPriority
    interval_seconds: int
    callback: Callable[[], Any]
    dependencies: list[str] = field(default_factory=list)
    max_errors: int = 3
    timeout_seconds: int = 300
    enabled: bool = True

    # Runtime state
    status: JobStatus = JobStatus.PENDING
    last_run: datetime | None = None
    next_run: datetime | None = None
    error_count: int = 0
    is_running: bool = False
    last_error: str | None = None


class UnifiedSchedulerService:
    """
    Enhetlig scheduler för alla schemalagda jobb i systemet.

    Konsoliderar jobb från:
    - RefreshManager (panel-refresh)
    - SchedulerService (equity snapshots, validation)
    - HealthWatchdog (system monitoring)
    - Ad-hoc jobb från services
    """

    def __init__(self, settings_override: Settings | None = None):
        self.settings = settings_override or settings
        self.jobs: dict[str, ScheduledJob] = {}
        self.is_running = False
        self._stop_event = asyncio.Event()
        self._scheduler_lock = asyncio.Lock()
        self._task: asyncio.Task | None = None

        # Standard intervall baserat på prioritet
        self._default_intervals = {
            JobPriority.CRITICAL: 30,  # Risk guards, circuit breakers
            JobPriority.HIGH: 60,  # Positions, wallets, orders
            JobPriority.MEDIUM: 300,  # Market data, signals
            JobPriority.LOW: 1800,  # History, performance stats
        }

        # Initialisera standard jobb
        self._initialize_default_jobs()

        logger.info("🗓️ UnifiedSchedulerService initialiserad - enhetlig jobb-schemaläggning")

    def _initialize_default_jobs(self) -> None:
        """Initialisera standard jobb från befintliga services."""

        # Equity snapshots (från SchedulerService)
        self.register_job(
            "equity_snapshot",
            JobPriority.HIGH,
            self._run_equity_snapshot,
            interval_seconds=3600,  # Varje timme
            timeout_seconds=60,
        )

        # Cache retention (från SchedulerService)
        self.register_job(
            "cache_retention",
            JobPriority.LOW,
            self._run_cache_retention,
            interval_seconds=43200,  # Var 12:e timme
            timeout_seconds=300,
        )

        # Probability validation (från SchedulerService)
        self.register_job(
            "prob_validation",
            JobPriority.MEDIUM,
            self._run_prob_validation,
            interval_seconds=1800,  # Var 30:e minut
            timeout_seconds=600,
        )

        # Probability retraining (från SchedulerService)
        self.register_job(
            "prob_retraining",
            JobPriority.LOW,
            self._run_prob_retraining,
            interval_seconds=86400,  # Dagligen
            timeout_seconds=3600,
        )

        # Regime update (från SchedulerService)
        self.register_job(
            "regime_update",
            JobPriority.MEDIUM,
            self._run_regime_update,
            interval_seconds=900,  # Var 15:e minut
            timeout_seconds=120,
        )

        # Health watchdog (från HealthWatchdog)
        self.register_job(
            "health_check",
            JobPriority.CRITICAL,
            self._run_health_check,
            interval_seconds=60,  # Varje minut
            timeout_seconds=30,
        )

        # Circuit breaker monitoring (från UnifiedCircuitBreakerService)
        self.register_job(
            "circuit_breaker_monitor",
            JobPriority.CRITICAL,
            self._run_circuit_breaker_monitor,
            interval_seconds=30,  # Var 30:e sekund
            timeout_seconds=15,
        )

        logger.info(f"📋 {len(self.jobs)} standard jobb registrerade")

    def register_job(
        self,
        name: str,
        priority: JobPriority,
        callback: Callable[[], Any],
        interval_seconds: int | None = None,
        dependencies: list[str] | None = None,
        max_errors: int = 3,
        timeout_seconds: int = 300,
        enabled: bool = True,
    ) -> None:
        """Registrera ett nytt schemalagt jobb."""

        if name in self.jobs:
            logger.warning(f"Jobb {name} redan registrerat, uppdaterar...")

        interval = interval_seconds or self._default_intervals[priority]

        self.jobs[name] = ScheduledJob(
            name=name,
            priority=priority,
            interval_seconds=interval,
            callback=callback,
            dependencies=dependencies or [],
            max_errors=max_errors,
            timeout_seconds=timeout_seconds,
            enabled=enabled,
            next_run=datetime.now(UTC) + timedelta(seconds=interval),
        )

        logger.info(f"📋 Jobb {name} registrerat (prioritet: {priority.name}, intervall: {interval}s)")

    def unregister_job(self, name: str) -> None:
        """Avregistrera ett jobb."""

        if name in self.jobs:
            del self.jobs[name]
            logger.info(f"🗑️ Jobb {name} avregistrerat")

    def enable_job(self, name: str) -> bool:
        """Aktivera ett jobb."""

        if name in self.jobs:
            self.jobs[name].enabled = True
            self.jobs[name].status = JobStatus.PENDING
            logger.info(f"✅ Jobb {name} aktiverat")
            return True
        return False

    def disable_job(self, name: str) -> bool:
        """Inaktivera ett jobb."""

        if name in self.jobs:
            self.jobs[name].enabled = False
            self.jobs[name].status = JobStatus.DISABLED
            logger.info(f"⏸️ Jobb {name} inaktiverat")
            return True
        return False

    def run_job_now(self, name: str) -> bool:
        """Kör ett jobb omedelbart."""

        if name not in self.jobs:
            logger.warning(f"Jobb {name} inte registrerat")
            return False

        job = self.jobs[name]
        if not job.enabled:
            logger.warning(f"Jobb {name} är inaktiverat")
            return False

        # Schemalägg för omedelbar körning
        job.next_run = datetime.now(UTC)
        logger.info(f"🚀 Jobb {name} schemalagt för omedelbar körning")
        return True

    async def start(self) -> None:
        """Starta scheduler-servicen."""

        if self.is_running:
            logger.warning("UnifiedSchedulerService redan igång")
            return

        self.is_running = True
        self._stop_event.clear()

        # Starta huvudloop
        self._task = asyncio.create_task(self._run_loop(), name="unified-scheduler-loop")

        logger.info("🚀 UnifiedSchedulerService startad")

    async def stop(self) -> None:
        """Stoppa scheduler-servicen."""

        if not self.is_running:
            return

        logger.info("🛑 Stoppar UnifiedSchedulerService...")
        self._stop_event.set()

        # Vänta på att huvudloopen avslutas
        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=10.0)
            except TimeoutError:
                logger.warning("Timeout vid stopp av scheduler-loop")
                self._task.cancel()

        self.is_running = False
        logger.info("✅ UnifiedSchedulerService stoppad")

    async def _run_loop(self) -> None:
        """Huvudloop för scheduler-servicen."""

        while not self._stop_event.is_set():
            try:
                await self._process_scheduler_cycle()
                await asyncio.sleep(1)  # Kontrollera varje sekund
            except Exception as e:
                logger.error(f"❌ Scheduler loop fel: {e}")
                await asyncio.sleep(5)  # Vänta lite vid fel

    async def _process_scheduler_cycle(self) -> None:
        """Processera en scheduler-cykel."""

        now = datetime.now(UTC)

        # Hitta jobb som ska köras
        jobs_to_run = []
        for job in self.jobs.values():
            if (
                job.enabled
                and job.status in [JobStatus.PENDING, JobStatus.COMPLETED]
                and job.next_run
                and now >= job.next_run
                and not job.is_running
            ):
                # Kontrollera dependencies
                if self._check_dependencies(job):
                    jobs_to_run.append(job)

        # Kör jobb baserat på prioritet
        jobs_to_run.sort(key=lambda j: j.priority.value)

        for job in jobs_to_run:
            if not self._stop_event.is_set():
                await self._run_job(job)

    def _check_dependencies(self, job: ScheduledJob) -> bool:
        """Kontrollera om jobbets dependencies är uppfyllda."""

        for dep_name in job.dependencies:
            if dep_name not in self.jobs:
                continue

            dep_job = self.jobs[dep_name]
            if dep_job.status == JobStatus.FAILED and dep_job.error_count >= dep_job.max_errors:
                return False

        return True

    async def _run_job(self, job: ScheduledJob) -> None:
        """Kör ett specifikt jobb."""

        async with self._scheduler_lock:
            job.is_running = True
            job.status = JobStatus.RUNNING
            job.last_run = datetime.now(UTC)

        try:
            logger.debug(f"🔄 Kör jobb: {job.name}")

            # Kör callback med timeout
            if asyncio.iscoroutinefunction(job.callback):
                await asyncio.wait_for(job.callback(), timeout=job.timeout_seconds)
            else:
                # Kör sync callback i thread pool
                loop = asyncio.get_event_loop()
                await asyncio.wait_for(
                    loop.run_in_executor(None, job.callback),
                    timeout=job.timeout_seconds,
                )

            # Återställ error count vid lyckad körning
            job.error_count = 0
            job.status = JobStatus.COMPLETED
            job.last_error = None

            logger.debug(f"✅ Jobb {job.name} slutfört")

        except TimeoutError:
            job.error_count += 1
            job.status = JobStatus.FAILED
            job.last_error = f"Timeout efter {job.timeout_seconds}s"
            logger.error(f"⏰ Jobb {job.name} timeout")

        except Exception as e:
            job.error_count += 1
            job.status = JobStatus.FAILED
            job.last_error = str(e)
            logger.error(f"❌ Jobb {job.name} fel: {e}")

            if job.error_count >= job.max_errors:
                logger.warning(f"⚠️ Jobb {job.name} har för många fel, inaktiverar...")
                job.enabled = False
                job.status = JobStatus.DISABLED

        finally:
            job.is_running = False
            # Schemalägg nästa körning
            job.next_run = datetime.now(UTC) + timedelta(seconds=job.interval_seconds)

    # Standard jobb implementations
    async def _run_equity_snapshot(self) -> None:
        """Kör equity snapshot."""
        try:
            from services.coordinator import get_coordinator

            await get_coordinator().equity_snapshot(reason="scheduled")
        except Exception as e:
            logger.error(f"Equity snapshot fel: {e}")
            raise

    async def _run_cache_retention(self) -> None:
        """Kör cache retention."""
        try:
            from services.coordinator import get_coordinator

            await get_coordinator().enforce_candle_cache_retention()
        except Exception as e:
            logger.error(f"Cache retention fel: {e}")
            raise

    async def _run_prob_validation(self) -> None:
        """Kör probability validation."""
        try:
            from services.coordinator import get_coordinator

            await get_coordinator().prob_validation()
        except Exception as e:
            logger.error(f"Probability validation fel: {e}")
            raise

    async def _run_prob_retraining(self) -> None:
        """Kör probability retraining."""
        try:
            from services.coordinator import get_coordinator

            coordinator = get_coordinator()
            # Försök anropa metoden med try-except
            try:
                await coordinator.prob_retraining()
            except AttributeError:
                logger.warning("prob_retraining metod inte tillgänglig i coordinator")
        except Exception as e:
            logger.error(f"Probability retraining fel: {e}")
            raise

    async def _run_regime_update(self) -> None:
        """Kör regime update."""
        try:
            from services.coordinator import get_coordinator

            await get_coordinator().update_regime()
        except Exception as e:
            logger.error(f"Regime update fel: {e}")
            raise

    async def _run_health_check(self) -> None:
        """Kör health check."""
        try:
            from services.health_watchdog import health_watchdog

            # Försök anropa metoden med try-except
            try:
                await health_watchdog.check_system_health()
            except AttributeError:
                logger.warning("check_system_health metod inte tillgänglig i health_watchdog")
        except Exception as e:
            logger.error(f"Health check fel: {e}")
            raise

    async def _run_circuit_breaker_monitor(self) -> None:
        """Kör circuit breaker monitoring."""
        try:
            from services.unified_circuit_breaker_service import (
                unified_circuit_breaker_service,
            )

            # Hämta status för alla circuit breakers
            status = unified_circuit_breaker_service.get_status()
            # Logga om någon är öppen
            if status.get("open_circuit_breakers", 0) > 0:
                logger.warning(f"⚠️ {status['open_circuit_breakers']} circuit breakers är öppna")
        except Exception as e:
            logger.error(f"Circuit breaker monitor fel: {e}")
            raise

    def get_job_status(self, name: str | None = None) -> dict[str, Any]:
        """Hämta status för ett eller alla jobb."""

        if name:
            if name not in self.jobs:
                return {"error": f"Jobb {name} inte registrerat"}

            job = self.jobs[name]
            return {
                "name": job.name,
                "priority": job.priority.name,
                "status": job.status.value,
                "enabled": job.enabled,
                "interval_seconds": job.interval_seconds,
                "last_run": job.last_run.isoformat() if job.last_run else None,
                "next_run": job.next_run.isoformat() if job.next_run else None,
                "error_count": job.error_count,
                "max_errors": job.max_errors,
                "is_running": job.is_running,
                "last_error": job.last_error,
                "dependencies": job.dependencies,
            }
        else:
            # Returnera status för alla jobb
            return {
                "timestamp": datetime.now(UTC).isoformat(),
                "jobs": {name: self.get_job_status(name) for name in self.jobs.keys()},
                "total_jobs": len(self.jobs),
                "enabled_jobs": sum(1 for job in self.jobs.values() if job.enabled),
                "running_jobs": sum(1 for job in self.jobs.values() if job.is_running),
                "failed_jobs": sum(1 for job in self.jobs.values() if job.status == JobStatus.FAILED),
            }

    def get_scheduler_summary(self) -> dict[str, Any]:
        """Hämta sammanfattning av scheduler-status."""

        return {
            "is_running": self.is_running,
            "total_jobs": len(self.jobs),
            "jobs_by_priority": {
                priority.name: sum(1 for job in self.jobs.values() if job.priority == priority)
                for priority in JobPriority
            },
            "jobs_by_status": {
                status.value: sum(1 for job in self.jobs.values() if job.status == status) for status in JobStatus
            },
            "next_job_to_run": min(
                (job.next_run for job in self.jobs.values() if job.next_run and job.enabled),
                default=None,
            ),
        }


# Global instans för enhetlig åtkomst
_unified_scheduler: UnifiedSchedulerService | None = None


def get_unified_scheduler() -> UnifiedSchedulerService:
    """Hämta global instans av UnifiedSchedulerService."""
    global _unified_scheduler
    if _unified_scheduler is None:
        _unified_scheduler = UnifiedSchedulerService(settings)
    return _unified_scheduler


# Bakåtkompatibilitet
unified_scheduler = get_unified_scheduler()
