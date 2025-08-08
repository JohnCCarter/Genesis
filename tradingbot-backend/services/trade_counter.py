"""
Trade Counter Service - begränsar antal trades per dag och cooldown.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Optional

from config.settings import Settings
from utils.logger import get_logger

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

logger = get_logger(__name__)


@dataclass
class TradeCounterState:
    day: date
    count: int = 0
    last_trade_ts: Optional[datetime] = None


class TradeCounterService:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.tz = ZoneInfo(self.settings.TIMEZONE) if ZoneInfo else None
        self.state = TradeCounterState(day=self._today())

    def _now(self) -> datetime:
        return datetime.now(self.tz) if self.tz else datetime.utcnow()

    def _today(self) -> date:
        return self._now().date()

    def _reset_if_new_day(self):
        today = self._today()
        if today != self.state.day:
            self.state = TradeCounterState(day=today)

    def can_execute(self) -> bool:
        self._reset_if_new_day()
        if self.state.count >= self.settings.MAX_TRADES_PER_DAY:
            return False
        if self.state.last_trade_ts:
            elapsed = (self._now() - self.state.last_trade_ts).total_seconds()
            if elapsed < self.settings.TRADE_COOLDOWN_SECONDS:
                return False
        return True

    def record_trade(self):
        self._reset_if_new_day()
        self.state.count += 1
        self.state.last_trade_ts = self._now()

    def stats(self) -> dict:
        self._reset_if_new_day()
        return {
            "day": self.state.day.isoformat(),
            "count": self.state.count,
            "max_per_day": self.settings.MAX_TRADES_PER_DAY,
            "cooldown_seconds": self.settings.TRADE_COOLDOWN_SECONDS,
            "cooldown_active": (
                self.state.last_trade_ts is not None and
                (self._now() - self.state.last_trade_ts).total_seconds() < self.settings.TRADE_COOLDOWN_SECONDS
            )
        }


