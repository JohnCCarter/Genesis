"""
Unified Circuit Breaker Service - Enhetlig circuit breaker-hantering för TradingBot.

Konsoliderar:
- Transport Circuit Breaker (REST/HTTP endpoints)
- Trading Circuit Breaker (trading-fel)
- Rate Limiter Circuit Breaker
- Custom Circuit Breakers

Löser problem med:
- Spridda circuit breaker-implementationer
- Inkonsistenta circuit breaker-logik
- Svår att debugga circuit breaker-problem
- Olika cooldown-strategier
"""

from __future__ import annotations

import time
from collections import deque
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from config.settings import settings
from services.metrics import metrics_store
from utils.logger import get_logger

logger = get_logger(__name__)


class CircuitBreakerState(Enum):
    """Circuit Breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, blocking requests
    HALF_OPEN = "half_open"  # Testing if service is recovered


class CircuitBreakerType(Enum):
    """Types of circuit breakers."""

    TRANSPORT = "transport"  # REST/HTTP endpoints
    TRADING = "trading"  # Trading operations
    RATE_LIMITER = "rate_limiter"  # Rate limiting
    CUSTOM = "custom"  # Custom circuit breakers


class CircuitBreakerConfig:
    """Configuration for a circuit breaker."""

    def __init__(
        self,
        name: str,
        cb_type: CircuitBreakerType,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
        failure_window: float = 300.0,  # 5 minutes
        exponential_backoff: bool = True,
        max_backoff: float = 300.0,  # 5 minutes max
    ):
        self.name = name
        self.cb_type = cb_type
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.failure_window = failure_window
        self.exponential_backoff = exponential_backoff
        self.max_backoff = max_backoff


class CircuitBreakerStatus:
    """Status of a circuit breaker."""

    def __init__(self):
        self.name = ""
        self.cb_type = CircuitBreakerType.CUSTOM
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: datetime | None = None
        self.last_success_time: datetime | None = None
        self.opened_at: datetime | None = None
        self.next_attempt_time: datetime | None = None
        self.half_open_calls = 0
        self.total_requests = 0
        self.total_failures = 0
        self.total_successes = 0


class UnifiedCircuitBreakerService:
    """
    Enhetlig service för all circuit breaker-hantering i systemet.

    Konsoliderar circuit breakers från:
    - Transport layer (REST/HTTP)
    - Trading operations
    - Rate limiting
    - Custom business logic
    """

    def __init__(self, settings_override: "Settings" | None = None):
        self.settings = settings_override or settings

        # Circuit breaker configurations
        self.configs: dict[str, CircuitBreakerConfig] = {}

        # Circuit breaker states
        self.states: dict[str, CircuitBreakerStatus] = {}

        # Failure events for sliding window
        self.failure_events: dict[str, deque[datetime]] = {}

        # Initialize default circuit breakers
        self._initialize_default_circuit_breakers()

        logger.info(
            "⚡ UnifiedCircuitBreakerService initialiserad - enhetlig circuit breaker-hantering"
        )

    def _initialize_default_circuit_breakers(self) -> None:
        """Initialisera standard circuit breakers."""

        # Transport Circuit Breaker
        self.configs["transport"] = CircuitBreakerConfig(
            name="transport",
            cb_type=CircuitBreakerType.TRANSPORT,
            failure_threshold=5,
            recovery_timeout=60.0,
            half_open_max_calls=3,
            failure_window=300.0,
            exponential_backoff=True,
            max_backoff=300.0,
        )

        # Trading Circuit Breaker
        self.configs["trading"] = CircuitBreakerConfig(
            name="trading",
            cb_type=CircuitBreakerType.TRADING,
            failure_threshold=3,
            recovery_timeout=300.0,  # 5 minutes
            half_open_max_calls=2,
            failure_window=600.0,  # 10 minutes
            exponential_backoff=True,
            max_backoff=1800.0,  # 30 minutes max
        )

        # Rate Limiter Circuit Breaker
        self.configs["rate_limiter"] = CircuitBreakerConfig(
            name="rate_limiter",
            cb_type=CircuitBreakerType.RATE_LIMITER,
            failure_threshold=10,
            recovery_timeout=30.0,
            half_open_max_calls=5,
            failure_window=60.0,  # 1 minute
            exponential_backoff=False,
            max_backoff=60.0,
        )

        # Initialize states
        for name, config in self.configs.items():
            self.states[name] = CircuitBreakerStatus()
            self.states[name].name = name
            self.states[name].cb_type = config.cb_type
            self.failure_events[name] = deque()

    def register_circuit_breaker(self, name: str, config: CircuitBreakerConfig) -> None:
        """Registrera en ny circuit breaker."""
        self.configs[name] = config
        self.states[name] = CircuitBreakerStatus()
        self.states[name].name = name
        self.states[name].cb_type = config.cb_type
        self.failure_events[name] = deque()
        logger.info(f"⚡ Circuit breaker registrerad: {name} ({config.cb_type.value})")

    def can_execute(self, name: str) -> bool:
        """Kontrollera om en operation kan utföras."""
        if name not in self.states:
            logger.warning(f"⚠️ Okänd circuit breaker: {name}")
            return True

        state = self.states[name]
        config = self.configs[name]

        # Uppdatera state baserat på tid
        self._update_state(name)

        # Kontrollera om circuit breaker är öppen
        if state.state == CircuitBreakerState.OPEN:
            if state.next_attempt_time and datetime.now() < state.next_attempt_time:
                return False
            else:
                # Gå till half-open state
                state.state = CircuitBreakerState.HALF_OPEN
                state.half_open_calls = 0
                logger.info(f"⚡ Circuit breaker {name} går till half-open state")

        # Kontrollera half-open state
        if state.state == CircuitBreakerState.HALF_OPEN:
            if state.half_open_calls >= config.half_open_max_calls:
                return False

        return True

    def record_success(self, name: str) -> None:
        """Registrera en lyckad operation."""
        if name not in self.states:
            return

        state = self.states[name]
        config = self.configs[name]

        state.success_count += 1
        state.total_successes += 1
        state.last_success_time = datetime.now()

        # Uppdatera metrics
        self._update_metrics(name, 0)  # 0 = closed

        if state.state == CircuitBreakerState.HALF_OPEN:
            # Om vi är i half-open och får success, gå tillbaka till closed
            state.state = CircuitBreakerState.CLOSED
            state.failure_count = 0
            state.half_open_calls = 0
            state.opened_at = None
            state.next_attempt_time = None
            logger.info(f"⚡ Circuit breaker {name} återställd till closed state")
        elif state.state == CircuitBreakerState.CLOSED:
            # Rensa gamla failure events
            self._cleanup_failure_events(name)

        logger.debug(
            f"⚡ Success registrerad för {name}: {state.success_count} successes"
        )

    def record_failure(self, name: str, error_type: str = "generic") -> None:
        """Registrera en misslyckad operation."""
        if name not in self.states:
            return

        state = self.states[name]
        config = self.configs[name]

        state.failure_count += 1
        state.total_failures += 1
        state.last_failure_time = datetime.now()

        # Lägg till failure event
        self.failure_events[name].append(datetime.now())

        # Uppdatera metrics
        self._update_metrics(name, 1)  # 1 = open

        # Kontrollera om circuit breaker ska öppnas
        if self._should_open_circuit(name):
            self._open_circuit(name, error_type)

        logger.warning(
            f"⚡ Failure registrerad för {name}: {state.failure_count} failures"
        )

    def on_event(
        self,
        *,
        source: str,
        endpoint: str | None = None,
        status_code: int | None = None,
        success: bool | None = None,
        retry_after: str | None = None,
    ) -> None:
        """Normaliserad event‑ingest från transport/rate‑limiter eller trading.

        Args:
            source: "transport" | "rate_limiter" | "trading" | <custom>
            endpoint: valfritt identifierare för endpoint
            status_code: HTTP status vid transport
            success: True/False
            retry_after: ev. Retry‑After header
        """
        _ = (endpoint, status_code, retry_after)
        name = "transport" if source in ("transport", "rate_limiter") else source
        try:
            if bool(success):
                self.record_success(name)
            else:
                self.record_failure(name)
        except Exception:
            pass

    def _update_state(self, name: str) -> None:
        """Uppdatera circuit breaker state baserat på tid."""
        if name not in self.states:
            return

        state = self.states[name]
        config = self.configs[name]

        if state.state == CircuitBreakerState.OPEN:
            if state.next_attempt_time and datetime.now() >= state.next_attempt_time:
                state.state = CircuitBreakerState.HALF_OPEN
                state.half_open_calls = 0
                logger.info(f"⚡ Circuit breaker {name} går till half-open state")

    def _should_open_circuit(self, name: str) -> bool:
        """Kontrollera om circuit breaker ska öppnas."""
        if name not in self.states:
            return False

        state = self.states[name]
        config = self.configs[name]

        # Kontrollera failure threshold
        if state.failure_count >= config.failure_threshold:
            return True

        # Kontrollera failure window
        now = datetime.now()
        cutoff_time = now - timedelta(seconds=config.failure_window)

        # Räkna failures inom fönstret
        recent_failures = sum(
            1 for event in self.failure_events[name] if event > cutoff_time
        )

        return recent_failures >= config.failure_threshold

    def _open_circuit(self, name: str, error_type: str) -> None:
        """Öppna circuit breaker."""
        if name not in self.states:
            return

        state = self.states[name]
        config = self.configs[name]

        state.state = CircuitBreakerState.OPEN
        state.opened_at = datetime.now()

        # Beräkna cooldown
        if config.exponential_backoff:
            backoff = min(
                config.recovery_timeout * (2 ** min(state.failure_count, 6)),
                config.max_backoff,
            )
        else:
            backoff = config.recovery_timeout

        state.next_attempt_time = datetime.now() + timedelta(seconds=backoff)

        # Uppdatera metrics
        self._update_metrics(name, 1)  # 1 = open

        logger.warning(
            f"⚡ Circuit breaker {name} öppnad: {error_type}, cooldown: {backoff}s"
        )

        # Skicka notifikation om aktiverat
        if hasattr(self.settings, "CB_NOTIFY") and self.settings.CB_NOTIFY:
            self._send_notification(name, error_type, backoff)

    def _cleanup_failure_events(self, name: str) -> None:
        """Rensa gamla failure events."""
        if name not in self.failure_events:
            return

        config = self.configs[name]
        cutoff_time = datetime.now() - timedelta(seconds=config.failure_window)

        # Ta bort gamla events
        while self.failure_events[name] and self.failure_events[name][0] < cutoff_time:
            self.failure_events[name].popleft()

    def _update_metrics(self, name: str, is_open: int) -> None:
        """Uppdatera metrics för circuit breaker."""
        try:
            # Uppdatera metrics store
            metrics_store[f"{name}_circuit_breaker_active"] = is_open

            # Bakåtkompatibilitet
            if name == "trading":
                metrics_store["circuit_breaker_active"] = is_open
                metrics_store["trading_circuit_breaker_active"] = is_open
            elif name == "transport":
                metrics_store["transport_circuit_breaker_active"] = is_open

            # Uppdatera counters
            counters = metrics_store.get("counters", {})
            labeled = counters.get("circuit_breaker_reasons_total", {})
            key = f'{{"name":"{name}","state":"{"open" if is_open else "closed"}"}}'
            labeled[key] = int(labeled.get(key, 0)) + 1
            counters["circuit_breaker_reasons_total"] = labeled
            metrics_store["counters"] = counters

        except Exception as e:
            logger.error(f"❌ Fel vid uppdatering av circuit breaker metrics: {e}")

    def _send_notification(self, name: str, error_type: str, cooldown: float) -> None:
        """Skicka notifikation om circuit breaker-aktivitet."""
        try:
            import asyncio
            from services.notifications import notification_service

            asyncio.create_task(
                notification_service.notify(
                    "warning",
                    f"Circuit Breaker {name} aktiverad",
                    {
                        "name": name,
                        "error_type": error_type,
                        "cooldown_seconds": cooldown,
                        "opened_at": datetime.now().isoformat(),
                    },
                )
            )
        except Exception as e:
            logger.error(f"❌ Fel vid skickande av circuit breaker notifikation: {e}")

    def get_status(self, name: str | None = None) -> dict[str, Any]:
        """Hämta status för en eller alla circuit breakers."""
        if name:
            if name not in self.states:
                return {"error": f"Okänd circuit breaker: {name}"}

            state = self.states[name]
            config = self.configs[name]

            return {
                "name": state.name,
                "type": state.cb_type.value,
                "state": state.state.value,
                "failure_count": state.failure_count,
                "success_count": state.success_count,
                "last_failure_time": (
                    state.last_failure_time.isoformat()
                    if state.last_failure_time
                    else None
                ),
                "last_success_time": (
                    state.last_success_time.isoformat()
                    if state.last_success_time
                    else None
                ),
                "opened_at": state.opened_at.isoformat() if state.opened_at else None,
                "next_attempt_time": (
                    state.next_attempt_time.isoformat()
                    if state.next_attempt_time
                    else None
                ),
                "half_open_calls": state.half_open_calls,
                "total_requests": state.total_requests,
                "total_failures": state.total_failures,
                "total_successes": state.total_successes,
                "config": {
                    "failure_threshold": config.failure_threshold,
                    "recovery_timeout": config.recovery_timeout,
                    "half_open_max_calls": config.half_open_max_calls,
                    "failure_window": config.failure_window,
                    "exponential_backoff": config.exponential_backoff,
                    "max_backoff": config.max_backoff,
                },
            }
        else:
            # Returnera status för alla circuit breakers
            return {
                "timestamp": datetime.now().isoformat(),
                "circuit_breakers": {
                    name: self.get_status(name) for name in self.states.keys()
                },
                "total_circuit_breakers": len(self.states),
                "open_circuit_breakers": sum(
                    1
                    for state in self.states.values()
                    if state.state == CircuitBreakerState.OPEN
                ),
            }

    def reset_circuit_breaker(self, name: str) -> bool:
        """Återställ en circuit breaker till closed state."""
        if name not in self.states:
            logger.error(f"❌ Okänd circuit breaker: {name}")
            return False

        state = self.states[name]
        state.state = CircuitBreakerState.CLOSED
        state.failure_count = 0
        state.half_open_calls = 0
        state.opened_at = None
        state.next_attempt_time = None

        # Rensa failure events
        self.failure_events[name].clear()

        # Uppdatera metrics
        self._update_metrics(name, 0)  # 0 = closed

        logger.info(f"⚡ Circuit breaker {name} återställd")
        return True

    def reset_all_circuit_breakers(self) -> bool:
        """Återställ alla circuit breakers."""
        try:
            for name in self.states:
                self.reset_circuit_breaker(name)
            logger.info("⚡ Alla circuit breakers återställda")
            return True
        except Exception as e:
            logger.error(f"❌ Fel vid återställning av alla circuit breakers: {e}")
            return False


# Global instans för enhetlig åtkomst
unified_circuit_breaker_service = UnifiedCircuitBreakerService()
