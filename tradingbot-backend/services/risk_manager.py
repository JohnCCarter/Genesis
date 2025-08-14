"""
Risk Manager - samlar riskkontroller: tidsfönster, daglig trade-limit, cooldown.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from config.settings import Settings
from services.metrics import metrics_store
from services.trade_counter import TradeCounterService
from services.trading_window import TradingWindowService
from utils.logger import get_logger

logger = get_logger(__name__)


_CB_ERROR_EVENTS = deque()
_CB_OPENED_AT: datetime | None = None


class RiskManager:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.trading_window = TradingWindowService(self.settings)
        self.trade_counter = TradeCounterService(self.settings)
        # Circuit breaker state (global per process)
        self._error_events = _CB_ERROR_EVENTS
        self._circuit_opened_at_ref = lambda: _CB_OPENED_AT

    def pre_trade_checks(self, *, symbol: str | None = None) -> tuple[bool, str | None]:
        if self.trading_window.is_paused():
            return False, "trading_paused"
        if not self.trading_window.is_open():
            return False, "outside_trading_window"
        # Per-symbol daglig gräns (pröva först för tydligare orsak)
        try:
            limits = self.trading_window.get_limits()
            # Föredra alltid reglernas värde även om det är 0 (0 = inaktiverad)
            limit_from_rules = int(limits.get("max_trades_per_symbol_per_day", 0) or 0)
            limit_from_settings = int(
                getattr(self.settings, "MAX_TRADES_PER_SYMBOL_PER_DAY", 0) or 0
            )
            active_limit = limit_from_rules if limit_from_rules >= 0 else limit_from_settings
            if symbol and active_limit > 0:
                per_symbol = self.trade_counter.stats().get("per_symbol", {})
                if per_symbol.get(symbol.upper(), 0) >= active_limit:
                    return False, "symbol_daily_trade_limit_reached"
        except Exception:
            pass
        # Generella kontroller (daglig limit, cooldown)
        if not self.trade_counter.can_execute():
            stats = self.trade_counter.stats()
            if stats.get("count", 0) >= stats.get("max_per_day", 0):
                return False, "daily_trade_limit_reached"
            if stats.get("cooldown_active", False):
                return False, "trade_cooldown_active"
            return False, "trade_blocked"
        return True, None

    def record_trade(self, *, symbol: str | None = None) -> None:
        if symbol:
            try:
                self.trade_counter.record_trade_for_symbol(symbol)
                return
            except Exception:
                pass
        self.trade_counter.record_trade()

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
            logger.warning("🚨 Circuit breaker aktiverad: pausar handel pga felspikar")
            try:
                metrics_store["circuit_breaker_active"] = 1
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
            logger.error(f"Kunde inte aktivera circuit breaker: {e}")

    def status(self) -> dict[str, Any]:
        now = datetime.utcnow()
        self._prune_errors(now)
        opened_at = _CB_OPENED_AT.isoformat() if _CB_OPENED_AT else None
        return {
            "open": self.trading_window.is_open(),
            "paused": self.trading_window.is_paused(),
            "limits": self.trading_window.get_limits(),
            "next_open": (
                self.trading_window.next_open().isoformat()
                if self.trading_window.next_open()
                else None
            ),
            "trades": self.trade_counter.stats(),
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
    def circuit_reset(
        self, *, resume: bool = True, clear_errors: bool = True, notify: bool = True
    ) -> dict[str, Any]:
        """Återställ circuit breaker: rensa fel och återuppta handel om så önskas."""
        try:
            if clear_errors:
                self._error_events.clear()
            global _CB_OPENED_AT
            _CB_OPENED_AT = None
            try:
                metrics_store["circuit_breaker_active"] = 0
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
