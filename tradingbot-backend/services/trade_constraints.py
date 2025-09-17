"""
Trade Constraints Service - centraliserar tidsfönster, dagliga limits och cooldown.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config.settings import settings, Settings
from services.trade_counter import TradeCounterService
from services.trading_window import TradingWindowService
from services.metrics import inc, inc_labeled


@dataclass
class ConstraintResult:
    allowed: bool
    reason: str | None = None
    details: dict[str, Any] | None = None


class TradeConstraintsService:
    def __init__(self, settings_override: Settings | None = None) -> None:
        self.settings = settings_override or settings
        self.trading_window = TradingWindowService(self.settings)
        self.trade_counter = TradeCounterService(self.settings)

    def check(self, *, symbol: str | None = None) -> ConstraintResult:
        # Global paus eller stängt fönster
        if self.trading_window.is_paused():
            try:
                inc_labeled(
                    "trade_constraints_blocked_total", {"reason": "trading_paused"}
                )
            except Exception:
                pass
            return ConstraintResult(False, "trading_paused")
        if not self.trading_window.is_open():
            try:
                inc_labeled(
                    "trade_constraints_blocked_total",
                    {"reason": "outside_trading_window"},
                )
            except Exception:
                pass
            return ConstraintResult(False, "outside_trading_window")

        # Per-symbol daglig limit
        try:
            limits = self.trading_window.get_limits()
            limit_sym = int((limits or {}).get("max_trades_per_symbol_per_day", 0) or 0)
            if symbol and limit_sym > 0:
                per_symbol = self.trade_counter.stats().get("per_symbol", {})
                if per_symbol.get(symbol.upper(), 0) >= limit_sym:
                    try:
                        inc_labeled(
                            "trade_constraints_blocked_total",
                            {"reason": "symbol_daily_trade_limit_reached"},
                        )
                    except Exception:
                        pass
                    return ConstraintResult(False, "symbol_daily_trade_limit_reached")
        except Exception:
            pass

        # Övergripande counter (per dag + cooldown)
        if not self.trade_counter.can_execute():
            stats = self.trade_counter.stats()
            if stats.get("count", 0) >= stats.get("max_per_day", 0):
                try:
                    inc_labeled(
                        "trade_constraints_blocked_total",
                        {"reason": "daily_trade_limit_reached"},
                    )
                except Exception:
                    pass
                return ConstraintResult(False, "daily_trade_limit_reached", stats)
            if stats.get("cooldown_active", False):
                try:
                    inc_labeled(
                        "trade_constraints_blocked_total",
                        {"reason": "trade_cooldown_active"},
                    )
                except Exception:
                    pass
                return ConstraintResult(False, "trade_cooldown_active", stats)
            try:
                inc_labeled(
                    "trade_constraints_blocked_total", {"reason": "trade_blocked"}
                )
            except Exception:
                pass
            return ConstraintResult(False, "trade_blocked", stats)

        try:
            inc("trade_constraints_allowed_total")
        except Exception:
            pass
        return ConstraintResult(True)

    def record_trade(self, *, symbol: str | None = None) -> None:
        if symbol:
            try:
                self.trade_counter.record_trade_for_symbol(symbol)
                return
            except Exception:
                pass
        self.trade_counter.record_trade()

    def limits(self) -> dict[str, Any]:
        d = self.trading_window.get_limits()
        d.update(self.trade_counter.stats())
        return d

    def status(self) -> dict[str, Any]:
        return {
            "paused": self.trading_window.is_paused(),
            "open": self.trading_window.is_open(),
            "next_open": (
                self.trading_window.next_open().isoformat()
                if self.trading_window.next_open()
                else None
            ),
            "limits": self.trading_window.get_limits(),
            "trades": self.trade_counter.stats(),
        }
