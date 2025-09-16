# AI Change: Add circuit breaker recovery service (Agent: Codex, Date: 2025-01-27)
"""
Circuit Breaker Recovery Service - Återställer öppna circuit breakers.

Denna service hanterar automatisk recovery från circuit breaker-fel och
förhindrar att systemet fastnar i öppna circuit breaker-tillstånd.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, UTC
from typing import Any, Dict, List

from config.settings import settings, Settings
from utils.logger import get_logger

logger = get_logger(__name__)


class CircuitBreakerRecoveryService:
    """Service för att återställa öppna circuit breakers."""

    def __init__(self, settings_override: Settings | None = None):
        self.settings = settings_override or settings
        self.is_running = False
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

        # Recovery-intervall
        self.recovery_check_interval = 30  # Kontrollera var 30:e sekund
        self.auto_recovery_enabled = True
        self.max_recovery_attempts = 3

        logger.info("🔄 CircuitBreakerRecoveryService initialiserad")

    async def start(self) -> None:
        """Starta recovery-servicen."""
        if self.is_running:
            logger.warning("CircuitBreakerRecoveryService redan igång")
            return

        self.is_running = True
        self._stop_event.clear()

        # Starta recovery-loop
        self._task = asyncio.create_task(self._recovery_loop(), name="circuit-breaker-recovery")

        logger.info("🚀 CircuitBreakerRecoveryService startad")

    async def stop(self) -> None:
        """Stoppa recovery-servicen."""
        if not self.is_running:
            return

        logger.info("🛑 Stoppar CircuitBreakerRecoveryService...")
        self._stop_event.set()

        # Vänta på att recovery-loopen avslutas
        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=10.0)
            except TimeoutError:
                logger.warning("Timeout vid stopp av recovery-loop")
                self._task.cancel()

        self.is_running = False
        logger.info("✅ CircuitBreakerRecoveryService stoppad")

    async def _recovery_loop(self) -> None:
        """Huvudloop för circuit breaker recovery."""
        while not self._stop_event.is_set():
            try:
                await self._check_and_recover_circuit_breakers()
                await asyncio.sleep(self.recovery_check_interval)
            except Exception as e:
                logger.error(f"❌ Recovery loop fel: {e}")
                await asyncio.sleep(5)  # Vänta lite vid fel

    async def _check_and_recover_circuit_breakers(self) -> None:
        """Kontrollera och återställ öppna circuit breakers."""
        try:
            # Kontrollera UnifiedCircuitBreakerService
            await self._recover_unified_circuit_breakers()

            # Kontrollera TransportCircuitBreaker
            await self._recover_transport_circuit_breakers()

            # Kontrollera RiskManager circuit breaker
            await self._recover_risk_circuit_breakers()

        except Exception as e:
            logger.error(f"❌ Fel vid circuit breaker recovery: {e}")

    async def _recover_unified_circuit_breakers(self) -> None:
        """Återställ UnifiedCircuitBreakerService circuit breakers."""
        try:
            from services.unified_circuit_breaker_service import (
                unified_circuit_breaker_service,
            )

            status = unified_circuit_breaker_service.get_status()
            open_circuit_breakers = status.get("open_circuit_breakers", 0)

            if open_circuit_breakers > 0:
                logger.warning(f"⚠️ {open_circuit_breakers} circuit breakers är öppna")

                # Försök återställa alla öppna circuit breakers
                circuit_breakers = status.get("circuit_breakers", {})
                for name, cb_status in circuit_breakers.items():
                    if cb_status.get("state") == "open":
                        # Kontrollera om cooldown-perioden har gått
                        opened_at = cb_status.get("opened_at")
                        if opened_at:
                            try:
                                opened_time = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
                                cooldown_seconds = cb_status.get("cooldown_seconds", 60)

                                if datetime.now(UTC) - opened_time > timedelta(seconds=cooldown_seconds):
                                    logger.info(f"🔄 Återställer circuit breaker: {name}")
                                    unified_circuit_breaker_service.reset_circuit_breaker(name)
                            except Exception as e:
                                logger.warning(f"Kunde inte återställa circuit breaker {name}: {e}")

        except Exception as e:
            logger.error(f"❌ Fel vid unified circuit breaker recovery: {e}")

    async def _recover_transport_circuit_breakers(self) -> None:
        """Återställ TransportCircuitBreaker circuit breakers."""
        try:
            from utils.advanced_rate_limiter import get_advanced_rate_limiter

            rate_limiter = get_advanced_rate_limiter()

            # Kontrollera alla circuit breaker-states
            for endpoint, cb_state in rate_limiter._cb_state.items():
                if cb_state.get("open_until", 0) > 0:
                    # Kontrollera om cooldown-perioden har gått
                    current_time = datetime.now().timestamp()
                    if current_time >= cb_state["open_until"]:
                        logger.info(f"🔄 Återställer transport circuit breaker: {endpoint}")
                        # Återställ circuit breaker-state
                        cb_state["fail_count"] = 0
                        cb_state["open_until"] = 0.0
                        cb_state["last_failure"] = 0.0

        except Exception as e:
            logger.error(f"❌ Fel vid transport circuit breaker recovery: {e}")

    async def _recover_risk_circuit_breakers(self) -> None:
        """Återställ RiskManager circuit breakers."""
        try:
            from services.unified_risk_service import unified_risk_service

            # Kontrollera om circuit breaker är öppen
            if unified_risk_service._is_circuit_breaker_open():
                # Kontrollera om timeout har gått
                opened_at = unified_risk_service.circuit_breaker.opened_at
                if opened_at:
                    timeout_minutes = unified_risk_service.circuit_breaker.timeout_minutes
                    if datetime.now() - opened_at > timedelta(minutes=timeout_minutes):
                        logger.info("🔄 Återställer risk circuit breaker")
                        unified_risk_service.circuit_breaker.opened_at = None

        except Exception as e:
            logger.error(f"❌ Fel vid risk circuit breaker recovery: {e}")

    def force_recovery_all(self) -> bool:
        """Tvinga återställning av alla circuit breakers."""
        try:
            logger.info("🔄 Tvingar återställning av alla circuit breakers...")

            # Återställ UnifiedCircuitBreakerService
            try:
                from services.unified_circuit_breaker_service import (
                    unified_circuit_breaker_service,
                )

                unified_circuit_breaker_service.reset_all_circuit_breakers()
            except Exception as e:
                logger.warning(f"Kunde inte återställa unified circuit breakers: {e}")

            # Återställ TransportCircuitBreaker
            try:
                from utils.advanced_rate_limiter import get_advanced_rate_limiter

                rate_limiter = get_advanced_rate_limiter()
                rate_limiter._cb_state.clear()
            except Exception as e:
                logger.warning(f"Kunde inte återställa transport circuit breakers: {e}")

            # Återställ RiskManager circuit breaker
            try:
                from services.unified_risk_service import unified_risk_service

                unified_risk_service.circuit_breaker.opened_at = None
                unified_risk_service.circuit_breaker.error_events.clear()
            except Exception as e:
                logger.warning(f"Kunde inte återställa risk circuit breaker: {e}")

            logger.info("✅ Alla circuit breakers återställda")
            return True

        except Exception as e:
            logger.error(f"❌ Fel vid tvingad återställning: {e}")
            return False

    def get_recovery_status(self) -> dict[str, Any]:
        """Hämta status för circuit breaker recovery."""
        try:
            from services.unified_circuit_breaker_service import (
                unified_circuit_breaker_service,
            )

            status = unified_circuit_breaker_service.get_status()

            return {
                "is_running": self.is_running,
                "auto_recovery_enabled": self.auto_recovery_enabled,
                "recovery_check_interval": self.recovery_check_interval,
                "total_circuit_breakers": status.get("total_circuit_breakers", 0),
                "open_circuit_breakers": status.get("open_circuit_breakers", 0),
                "circuit_breakers": status.get("circuit_breakers", {}),
                "last_check": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            logger.error(f"❌ Fel vid hämtning av recovery status: {e}")
            return {
                "is_running": self.is_running,
                "error": str(e),
            }


# Global instans
_circuit_breaker_recovery: CircuitBreakerRecoveryService | None = None


def get_circuit_breaker_recovery() -> CircuitBreakerRecoveryService:
    """Hämta global instans av CircuitBreakerRecoveryService."""
    global _circuit_breaker_recovery
    if _circuit_breaker_recovery is None:
        _circuit_breaker_recovery = CircuitBreakerRecoveryService()
    return _circuit_breaker_recovery
