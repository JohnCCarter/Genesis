"""
Trade Counter Service - begränsar antal trades per dag och cooldown.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Optional

from utils.logger import get_logger

from config.settings import Settings
from services.trading_window import TradingWindowService

try:
    from zoneinfo import ZoneInfo  # type: ignore
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

logger = get_logger(__name__)


@dataclass
class TradeCounterState:
    day: date
    count: int = 0
    last_trade_ts: datetime | None = None


class TradeCounterService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        has_zoneinfo = ZoneInfo is not None
        self.tz = ZoneInfo(self.settings.TIMEZONE) if has_zoneinfo else None
        self.state = TradeCounterState(day=self._today())
        # Per-symbol räknare (persistens)
        self.symbol_counts: dict[str, int] = {}
        # Läser dynamiska gränser (max trades/dag, cooldown) via TradingWindow
        self.trading_window = TradingWindowService(self.settings)
        self._load_state()

    def _now(self) -> datetime:
        return datetime.now(self.tz) if self.tz else datetime.utcnow()

    def _today(self) -> date:
        return self._now().date()

    def _reset_if_new_day(self):
        today = self._today()
        if today != self.state.day:
            self.state = TradeCounterState(day=today)
            self.symbol_counts = {}
            self._save_state()

    def can_execute(self) -> bool:
        self._reset_if_new_day()
        if self.state.count >= self._max_per_day_current():
            return False
        if self.state.last_trade_ts:
            elapsed = (self._now() - self.state.last_trade_ts).total_seconds()
            if elapsed < self._cooldown_seconds_current():
                return False
        return True

    def record_trade(self):
        self._reset_if_new_day()
        self.state.count += 1
        self.state.last_trade_ts = self._now()
        self._save_state()

    def record_trade_for_symbol(self, symbol: str):
        self._reset_if_new_day()
        key = (symbol or "").upper()
        self.symbol_counts[key] = self.symbol_counts.get(key, 0) + 1
        self.record_trade()

    def stats(self) -> dict:
        self._reset_if_new_day()
        return {
            "day": self.state.day.isoformat(),
            "count": self.state.count,
            "max_per_day": self._max_per_day_current(),
            "cooldown_seconds": self._cooldown_seconds_current(),
            "cooldown_active": (
                self.state.last_trade_ts is not None
                and ((self._now() - self.state.last_trade_ts).total_seconds() < self._cooldown_seconds_current())
            ),
            "per_symbol": self.symbol_counts.copy(),
        }

    # --- Persistens ---
    def _abs_counter_path(self) -> str:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        cfg_dir = os.path.join(base_dir, "config")
        os.makedirs(cfg_dir, exist_ok=True)
        fname = os.path.basename(self.settings.TRADE_COUNTER_FILE)
        return os.path.join(cfg_dir, fname)

    def _load_state(self) -> None:
        try:
            path = self._abs_counter_path()
            if not os.path.exists(path):
                return
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            day_str = data.get("day")
            if day_str:
                try:
                    y, m, d = (int(x) for x in day_str.split("-"))
                    self.state.day = date(y, m, d)
                except Exception:
                    self.state.day = self._today()
            self.state.count = int(data.get("count", 0))
            self.symbol_counts = {str(k).upper(): int(v) for k, v in (data.get("per_symbol", {}) or {}).items()}
        except Exception:
            # korrupt fil – börja om
            self.state = TradeCounterState(day=self._today())
            self.symbol_counts = {}

    def _save_state(self) -> None:
        try:
            path = self._abs_counter_path()
            payload = {
                "day": self.state.day.isoformat(),
                "count": self.state.count,
                "per_symbol": self.symbol_counts,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # --- Dynamiska gränser från TradingWindow ---
    def _max_per_day_current(self) -> int:
        """Returnera gällande max trades per dag, prioriterat från TradingWindow-regler."""
        try:
            limits = self.trading_window.get_limits()
            val = int((limits or {}).get("max_trades_per_day", 0) or 0)
            if val > 0:
                return val
        except Exception:
            pass
        return int(getattr(self.settings, "MAX_TRADES_PER_DAY", 0) or 0)

    def _cooldown_seconds_current(self) -> int:
        """Returnera gällande cooldown i sekunder, prioriterat från TradingWindow-regler om definierad."""
        try:
            limits = self.trading_window.get_limits()
            val = int((limits or {}).get("trade_cooldown_seconds", 0) or 0)
            if val > 0:
                return val
        except Exception:
            pass
        return int(getattr(self.settings, "TRADE_COOLDOWN_SECONDS", 0) or 0)
