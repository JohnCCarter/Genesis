"""
Risk Manager - samlar riskkontroller: tidsfönster, daglig trade-limit, cooldown.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from typing import Any

from utils.logger import get_logger

from config.settings import Settings
from services.metrics import metrics_store
from services.risk_guards import risk_guards
from services.risk_policy_engine import RiskPolicyEngine

logger = get_logger(__name__)


_CB_ERROR_EVENTS = deque()
_CB_OPENED_AT: datetime | None = None


class RiskManager:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.policy = RiskPolicyEngine(self.settings)
        # Backwards-compat: exponera underliggande services så gamla tester fungerar
        self.trading_window = self.policy.constraints.trading_window
        self.trade_counter = self.policy.constraints.trade_counter
        # Circuit breaker state (global per process)
        self._error_events = _CB_ERROR_EVENTS
        self._circuit_opened_at_ref = lambda: _CB_OPENED_AT

    def pre_trade_checks(
        self, *, symbol: str | None = None, amount: float = None, price: float = None
    ) -> tuple[bool, str | None]:
        # Kontrollera globala riskvakter först
        blocked, reason = risk_guards.check_all_guards(symbol, amount, price)
        if blocked:
            return False, f"risk_guard_blocked:{reason}"

        decision = self.policy.evaluate(symbol=symbol, amount=amount, price=price)
        if not decision.allowed:
            return False, decision.reason
        return True, None

    def record_trade(self, *, symbol: str | None = None) -> None:
        self.policy.record_trade(symbol=symbol)

    # --- Circuit Breaker ---
    def record_error(self) -> None:
        """Registrera ett fel för circuit breaker-spårning."""
        if not self.settings.CB_ENABLED:
            return
        now = datetime.utcnow()
        self._error_events.append(now)
        self._prune_errors(now)
        if self._should_open_circuit(now):
            self._open_circuit()

    def _prune_errors(self, now: datetime) -> None:
        window = timedelta(seconds=self.settings.CB_ERROR_WINDOW_SECONDS)
        while self._error_events and (now - self._error_events[0]) > window:
            self._error_events.popleft()

    def _should_open_circuit(self, now: datetime) -> bool:  # noqa: ARG002
        return (
            self.settings.CB_ENABLED
            and len(self._error_events) >= self.settings.CB_MAX_ERRORS_PER_WINDOW
            and not self.trading_window.is_paused()
        )

    def _open_circuit(self) -> None:
        try:
            self.trading_window.set_paused(True)
            global _CB_OPENED_AT
            _CB_OPENED_AT = datetime.utcnow()
            logger.warning("🚨 TradingCircuitBreaker aktiverad: pausar handel pga felspikar")
            try:
                # Behåll bakåtkompatibel nyckel + ny namngiven nyckel
                metrics_store["circuit_breaker_active"] = 1
                metrics_store["trading_circuit_breaker_active"] = 1
            except Exception:
                pass
            if self.settings.CB_NOTIFY:
                try:
                    import asyncio as _asyncio

                    from services.notifications import notification_service

                    _asyncio.create_task(
                        notification_service.notify(
                            "warning",
                            "Circuit breaker aktiverad",
                            {
                                "since": (_CB_OPENED_AT.isoformat() if _CB_OPENED_AT else None),
                                "errors_in_window": len(self._error_events),
                                "window_seconds": self.settings.CB_ERROR_WINDOW_SECONDS,
                            },
                        )
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Kunde inte aktivera TradingCircuitBreaker: {e}")

    def status(self) -> dict[str, Any]:
        now = datetime.utcnow()
        self._prune_errors(now)
        opened_at = _CB_OPENED_AT.isoformat() if _CB_OPENED_AT else None
        ps = self.policy.status()
        return {
            "open": ps.get("open"),
            "paused": ps.get("paused"),
            "limits": ps.get("limits"),
            "next_open": ps.get("next_open"),
            "trades": ps.get("trades"),
            "circuit": {
                "enabled": bool(self.settings.CB_ENABLED),
                "errors_in_window": len(self._error_events),
                "window_seconds": int(self.settings.CB_ERROR_WINDOW_SECONDS),
                "max_errors_per_window": int(self.settings.CB_MAX_ERRORS_PER_WINDOW),
                "opened_at": opened_at,
                "notify": bool(getattr(self.settings, "CB_NOTIFY", True)),
            },
        }

    # --- Circuit Breaker controls ---
    def circuit_reset(self, *, resume: bool = True, clear_errors: bool = True, notify: bool = True) -> dict[str, Any]:
        """Återställ circuit breaker: rensa fel och återuppta handel om så önskas."""
        try:
            if clear_errors:
                self._error_events.clear()
            global _CB_OPENED_AT
            _CB_OPENED_AT = None
            try:
                metrics_store["circuit_breaker_active"] = 0
                metrics_store["trading_circuit_breaker_active"] = 0
            except Exception:
                pass
            if resume:
                try:
                    self.trading_window.set_paused(False)
                except Exception:
                    pass
            if notify and getattr(self.settings, "CB_NOTIFY", True):
                try:
                    from ws.manager import socket_app

                    asyncio_create_task = __import__("asyncio").create_task
                    asyncio_create_task(
                        socket_app.emit(
                            "notification",
                            {
                                "type": "info",
                                "title": "Circuit breaker återställd",
                                "payload": {"resumed": bool(resume)},
                            },
                        )
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Fel vid circuit reset: {e}")
        return self.status()

    def update_circuit_config(
        self,
        *,
        enabled: bool | None = None,
        window_seconds: int | None = None,
        max_errors_per_window: int | None = None,
        notify: bool | None = None,
    ) -> dict[str, Any]:
        """Uppdatera runtime-konfiguration för circuit breaker (påverkar nya instanser via os.environ)."""
        import os

        if enabled is not None:
            self.settings.CB_ENABLED = bool(enabled)
            os.environ["CB_ENABLED"] = "True" if enabled else "False"
        if window_seconds is not None and window_seconds > 0:
            self.settings.CB_ERROR_WINDOW_SECONDS = int(window_seconds)
            os.environ["CB_ERROR_WINDOW_SECONDS"] = str(int(window_seconds))
        if max_errors_per_window is not None and max_errors_per_window > 0:
            self.settings.CB_MAX_ERRORS_PER_WINDOW = int(max_errors_per_window)
            os.environ["CB_MAX_ERRORS_PER_WINDOW"] = str(int(max_errors_per_window))
        if notify is not None:
            self.settings.CB_NOTIFY = bool(notify)
            os.environ["CB_NOTIFY"] = "True" if notify else "False"
        return self.status()
