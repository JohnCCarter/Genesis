"""
Refresh Manager - Centraliserad hantering av panel-refresh för dashboard.

Löser problem med:
- Race conditions mellan paneler
- Onödiga API-anrop
- Inkonsistenta refresh-intervall
- Svår att debugga refresh-problem
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from utils.logger import get_logger

logger = get_logger(__name__)


class RefreshPriority(Enum):
    """Refresh prioritet för olika typer av data."""

    CRITICAL = 1  # 30s - Risk guards, circuit breakers
    HIGH = 2  # 60s - Positions, wallets, orders
    MEDIUM = 3  # 120s - Market data, signals
    LOW = 4  # 300s - History, performance stats


@dataclass
class RefreshTask:
    """En refresh-uppgift för en specifik panel."""

    panel_id: str
    priority: RefreshPriority
    interval_seconds: int
    callback: Callable[[], Any]
    last_run: datetime | None = None
    next_run: datetime | None = None
    is_running: bool = False
    error_count: int = 0
    max_errors: int = 3
    dependencies: set[str] = field(default_factory=set)

    def __post_init__(self):
        """Beräkna nästa körning vid initiering."""
        self.next_run = datetime.utcnow() + timedelta(seconds=self.interval_seconds)


@dataclass
class SharedData:
    """Delad data mellan paneler för att minska API-anrop."""

    timestamp: datetime
    health_status: dict[str, Any] | None = None
    circuit_breaker_status: dict[str, Any] | None = None
    risk_status: dict[str, Any] | None = None
    market_data: dict[str, Any] | None = None
    performance_stats: dict[str, Any] | None = None


class RefreshManager:
    """Centraliserad refresh-hantering för dashboard paneler."""

    def __init__(self):
        self.tasks: dict[str, RefreshTask] = {}
        self.shared_data = SharedData(timestamp=datetime.utcnow())
        self.is_running = False
        self._stop_event = asyncio.Event()
        self._refresh_lock = asyncio.Lock()

        # Standard refresh-intervall baserat på prioritet
        self._default_intervals = {
            RefreshPriority.CRITICAL: 30,  # Risk guards, circuit breakers
            RefreshPriority.HIGH: 60,  # Positions, wallets, orders
            RefreshPriority.MEDIUM: 120,  # Market data, signals
            RefreshPriority.LOW: 300,  # History, performance stats
        }

        logger.info("🔄 RefreshManager initialiserad")

    def register_panel(
        self,
        panel_id: str,
        priority: RefreshPriority,
        callback: Callable[[], Any],
        interval_seconds: int | None = None,
        dependencies: set[str] | None = None,
    ) -> None:
        """Registrera en panel för automatisk refresh."""
        if panel_id in self.tasks:
            logger.warning(f"Panel {panel_id} redan registrerad, uppdaterar...")

        interval = interval_seconds or self._default_intervals[priority]

        self.tasks[panel_id] = RefreshTask(
            panel_id=panel_id,
            priority=priority,
            interval_seconds=interval,
            callback=callback,
            dependencies=dependencies or set(),
        )

        logger.info(f"📋 Panel {panel_id} registrerad (prioritet: {priority.name}, intervall: {interval}s)")

    def unregister_panel(self, panel_id: str) -> None:
        """Avregistrera en panel."""
        if panel_id in self.tasks:
            del self.tasks[panel_id]
            logger.info(f"🗑️ Panel {panel_id} avregistrerad")

    def update_shared_data(self, data_type: str, data: Any) -> None:
        """Uppdatera delad data."""
        self.shared_data.timestamp = datetime.utcnow()

        if data_type == "health_status":
            self.shared_data.health_status = data
        elif data_type == "circuit_breaker_status":
            self.shared_data.circuit_breaker_status = data
        elif data_type == "risk_status":
            self.shared_data.risk_status = data
        elif data_type == "market_data":
            self.shared_data.market_data = data
        elif data_type == "performance_stats":
            self.shared_data.performance_stats = data

        logger.debug(f"📊 Shared data uppdaterad: {data_type}")

    def get_shared_data(self) -> SharedData:
        """Hämta aktuell delad data."""
        return self.shared_data

    def get_panel_status(self) -> dict[str, Any]:
        """Hämta status för alla registrerade paneler."""
        status = {
            "total_panels": len(self.tasks),
            "running": self.is_running,
            "panels": {},
        }

        for panel_id, task in self.tasks.items():
            status["panels"][panel_id] = {
                "priority": task.priority.name,
                "interval_seconds": task.interval_seconds,
                "last_run": task.last_run.isoformat() if task.last_run else None,
                "next_run": task.next_run.isoformat() if task.next_run else None,
                "is_running": task.is_running,
                "error_count": task.error_count,
                "dependencies": list(task.dependencies),
            }

        return status

    async def start(self) -> None:
        """Starta refresh-managern."""
        if self.is_running:
            logger.warning("RefreshManager redan igång")
            return

        self.is_running = True
        self._stop_event.clear()

        logger.info("🚀 RefreshManager startad")

        # Starta huvudloop
        try:
            await self._refresh_loop()
        except Exception as e:
            logger.error(f"❌ RefreshManager fel: {e}")
        finally:
            self.is_running = False

    async def stop(self) -> None:
        """Stoppa refresh-managern."""
        if not self.is_running:
            return

        logger.info("🛑 Stoppar RefreshManager...")
        self._stop_event.set()

        # Vänta på att alla pågående refresh-operationer slutförs
        await asyncio.sleep(1)

        self.is_running = False
        logger.info("✅ RefreshManager stoppad")

    async def force_refresh(self, panel_id: str | None = None) -> None:
        """Tvinga refresh för en specifik panel eller alla."""
        async with self._refresh_lock:
            if panel_id:
                if panel_id in self.tasks:
                    await self._run_panel_refresh(self.tasks[panel_id])
                else:
                    logger.warning(f"Panel {panel_id} inte registrerad")
            else:
                # Refresh alla paneler
                for task in self.tasks.values():
                    await self._run_panel_refresh(task)

    async def _refresh_loop(self) -> None:
        """Huvudloop för refresh-hantering."""
        while not self._stop_event.is_set():
            try:
                await self._process_refresh_cycle()
                await asyncio.sleep(1)  # Kontrollera varje sekund
            except Exception as e:
                logger.error(f"❌ Refresh loop fel: {e}")
                await asyncio.sleep(5)  # Vänta lite vid fel

    async def _process_refresh_cycle(self) -> None:
        """Processera en refresh-cykel."""
        now = datetime.utcnow()
        tasks_to_run = []

        # Hitta paneler som behöver refresh
        for task in self.tasks.values():
            if task.next_run and task.next_run <= now and not task.is_running and task.error_count < task.max_errors:

                # Kontrollera dependencies
                if self._check_dependencies(task):
                    tasks_to_run.append(task)

        # Kör refresh för alla berättigade paneler
        if tasks_to_run:
            await asyncio.gather(
                *[self._run_panel_refresh(task) for task in tasks_to_run],
                return_exceptions=True,
            )

    def _check_dependencies(self, task: RefreshTask) -> bool:
        """Kontrollera om alla dependencies är uppfyllda."""
        for dep in task.dependencies:
            if dep not in self.tasks:
                continue

            dep_task = self.tasks[dep]
            if dep_task.is_running or dep_task.error_count >= dep_task.max_errors:
                return False

        return True

    async def _run_panel_refresh(self, task: RefreshTask) -> None:
        """Kör refresh för en specifik panel."""
        task.is_running = True
        task.last_run = datetime.utcnow()

        try:
            logger.debug(f"🔄 Refreshar panel: {task.panel_id}")

            # Kör callback
            if asyncio.iscoroutinefunction(task.callback):
                await task.callback()
            else:
                task.callback()

            # Återställ error count vid lyckad refresh
            task.error_count = 0

            logger.debug(f"✅ Panel {task.panel_id} refreshad")

        except Exception as e:
            task.error_count += 1
            logger.error(f"❌ Panel {task.panel_id} refresh fel: {e}")

            if task.error_count >= task.max_errors:
                logger.warning(f"⚠️ Panel {task.panel_id} har för många fel, pausar...")

        finally:
            task.is_running = False
            # Beräkna nästa körning
            task.next_run = datetime.utcnow() + timedelta(seconds=task.interval_seconds)

    def get_refresh_intervals_summary(self) -> dict[str, int]:
        """Hämta sammanfattning av refresh-intervall."""
        summary = {}
        for task in self.tasks.values():
            summary[task.panel_id] = task.interval_seconds
        return summary


# Global instans
_refresh_manager: RefreshManager | None = None


def get_refresh_manager() -> RefreshManager:
    """Hämta global RefreshManager instans."""
    global _refresh_manager
    if _refresh_manager is None:
        _refresh_manager = RefreshManager()
    return _refresh_manager


async def start_refresh_manager() -> None:
    """Starta global RefreshManager."""
    manager = get_refresh_manager()
    await manager.start()


async def stop_refresh_manager() -> None:
    """Stoppa global RefreshManager."""
    manager = get_refresh_manager()
    await manager.stop()
