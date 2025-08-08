"""
Risk Manager - samlar riskkontroller: tidsfönster, daglig trade-limit, cooldown.
"""

from __future__ import annotations

from typing import Tuple, Optional, Dict, Any

from config.settings import Settings
from utils.logger import get_logger
from services.trading_window import TradingWindowService
from services.trade_counter import TradeCounterService

logger = get_logger(__name__)


class RiskManager:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.trading_window = TradingWindowService(self.settings)
        self.trade_counter = TradeCounterService(self.settings)

    def pre_trade_checks(self) -> Tuple[bool, Optional[str]]:
        if self.trading_window.is_paused():
            return False, "trading_paused"
        if not self.trading_window.is_open():
            return False, "outside_trading_window"
        if not self.trade_counter.can_execute():
            # skilj på daglig limit vs cooldown
            stats = self.trade_counter.stats()
            if stats.get("count", 0) >= stats.get("max_per_day", 0):
                return False, "daily_trade_limit_reached"
            if stats.get("cooldown_active", False):
                return False, "trade_cooldown_active"
            return False, "trade_blocked"
        return True, None

    def record_trade(self) -> None:
        self.trade_counter.record_trade()

    def status(self) -> Dict[str, Any]:
        return {
            "open": self.trading_window.is_open(),
            "paused": self.trading_window.is_paused(),
            "limits": self.trading_window.get_limits(),
            "next_open": (
                self.trading_window.next_open().isoformat() if self.trading_window.next_open() else None
            ),
            "trades": self.trade_counter.stats(),
        }


