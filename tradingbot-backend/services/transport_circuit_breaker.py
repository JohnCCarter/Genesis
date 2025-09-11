"""
Transport Circuit Breaker

Namngiven wrapper runt AdvancedRateLimiter:s inbyggda circuit breaker för
transportnivå (REST/HTTP) – öppnas per endpoint vid 429/5xx och stänger
automatiskt efter cooldown.
"""

from __future__ import annotations

from typing import Optional

from utils.advanced_rate_limiter import get_advanced_rate_limiter
from utils.logger import get_logger
from services.unified_circuit_breaker_service import UnifiedCircuitBreakerService

logger = get_logger(__name__)


class TransportCircuitBreaker:
    def __init__(self) -> None:
        self._limiter = get_advanced_rate_limiter()
        try:
            self._ucb = UnifiedCircuitBreakerService()
        except Exception:
            self._ucb = None

    def can_request(self, endpoint: str) -> bool:
        return self._limiter.can_request(endpoint)

    def time_until_open(self, endpoint: str) -> float:
        return self._limiter.time_until_open(endpoint)

    def note_success(self, endpoint: str) -> None:
        try:
            self._limiter.note_success(endpoint)
            # Toggle metric till 0 när vi lyckas
            try:
                from services.metrics import metrics_store

                metrics_store["transport_circuit_breaker_active"] = 0
            except Exception:
                pass
            # Signalera till unified CB
            try:
                if self._ucb:
                    self._ucb.on_event(source="transport", endpoint=endpoint, success=True)
            except Exception:
                pass
        except Exception:
            pass

    def note_failure(self, endpoint: str, status_code: int, retry_after: str | None = None) -> float:
        cooldown = self._limiter.note_failure(endpoint, status_code, retry_after)
        # Toggle metric till 1 när CB öppnas
        try:
            from services.metrics import metrics_store

            metrics_store["transport_circuit_breaker_active"] = 1
        except Exception:
            pass
        # Signalera till unified CB
        try:
            if self._ucb:
                self._ucb.on_event(
                    source="transport",
                    endpoint=endpoint,
                    status_code=status_code,
                    success=False,
                    retry_after=retry_after,
                )
        except Exception:
            pass
        return cooldown


_cb_singleton: TransportCircuitBreaker | None = None


def get_transport_circuit_breaker() -> TransportCircuitBreaker:
    global _cb_singleton
    if _cb_singleton is None:
        _cb_singleton = TransportCircuitBreaker()
    return _cb_singleton
