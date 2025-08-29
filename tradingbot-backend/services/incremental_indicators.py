"""
Incremental Indicators - maintain per-symbol/timeframe state for EMA, RSI, ATR.

Optimized O(1) updates for live candles. Designed for use with WS-first data flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class EMAState:
    period: int
    value: float | None = None

    def update(self, price: float) -> float:
        alpha = 2.0 / (self.period + 1.0)
        if self.value is None:
            self.value = float(price)
        else:
            self.value = alpha * float(price) + (1.0 - alpha) * float(self.value)
        return float(self.value)


@dataclass
class RSIState:
    period: int
    avg_gain: float | None = None
    avg_loss: float | None = None
    prev_close: float | None = None

    def update(self, close: float) -> float:
        c = float(close)
        if self.prev_close is None:
            self.prev_close = c
            return 50.0
        delta = c - float(self.prev_close)
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        if self.avg_gain is None or self.avg_loss is None:
            # initialize with first observation
            self.avg_gain = gain
            self.avg_loss = loss
        else:
            self.avg_gain = (self.avg_gain * (self.period - 1) + gain) / self.period
            self.avg_loss = (self.avg_loss * (self.period - 1) + loss) / self.period
        self.prev_close = c
        if self.avg_loss == 0 or self.avg_loss is None:
            return 100.0
        rs = float(self.avg_gain or 0.0) / float(self.avg_loss)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return float(rsi)


@dataclass
class ATRState:
    period: int
    atr: float | None = None
    prev_close: float | None = None

    def update(self, high: float, low: float, close: float) -> float:
        h = float(high)
        l_ = float(low)
        c = float(close)
        if self.prev_close is None:
            tr = h - l_
            self.atr = tr if self.atr is None else (self.atr * (self.period - 1) + tr) / self.period
            self.prev_close = c
            return float(self.atr)
        tr = max(h - l_, abs(h - self.prev_close), abs(l_ - self.prev_close))
        if self.atr is None:
            self.atr = tr
        else:
            self.atr = (self.atr * (self.period - 1) + tr) / self.period
        self.prev_close = c
        return float(self.atr)
