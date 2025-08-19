"""
ADX indicator helper.

If TA-Lib is available, use true ADX. Otherwise fall back to a simple rolling
proxy so utvecklingsflöden inte kraschar. Proxyn är inte likvärdig ADX.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np

# Optional dependency: talib importeras lazily i funktionen nedan


def _safe_to_array(x: Iterable[float]) -> np.ndarray:
    try:
        return np.asarray(list(x), dtype=float)
    except (TypeError, ValueError):
        return np.array([], dtype=float)


def adx(
    high: Iterable[float],
    low: Iterable[float],
    close: Iterable[float],
    period: int = 14,
) -> list[float]:
    """Compute ADX if TA-Lib exists, else return a rough proxy series.

    Args:
        high, low, close: price iterables
        period: ADX period (default 14)
    Returns:
        list of floats (same length as inputs when possible)
    """
    # Lazy import TA-Lib (optional dependency)
    try:
        import talib as ta
    except ImportError:
        ta = None

    if ta is not None:
        h = _safe_to_array(high)
        low_arr = _safe_to_array(low)
        c = _safe_to_array(close)
        if h.size == 0 or low_arr.size == 0 or c.size == 0:
            return []
        out = ta.ADX(h, low_arr, c, timeperiod=max(2, int(period)))
        return [float(x) if x is not None else float("nan") for x in out]

    # Fallback proxy: scaled absolute EMA slope (very rough)
    c = _safe_to_array(close)
    if c.size == 0:
        return []
    p = max(2, int(period))
    alpha = 2.0 / (p + 1.0)
    ema = np.zeros_like(c, dtype=float)
    ema[0] = c[0]
    for i in range(1, c.size):
        ema[i] = alpha * c[i] + (1 - alpha) * ema[i - 1]
    slope = np.abs(np.diff(ema, prepend=ema[0]))
    # Scale to 0..50 range to roughly mimic ADX magnitude
    scaled = np.clip((slope / (np.mean(np.abs(c)) + 1e-9)) * 1000.0, 0.0, 50.0)
    return [float(x) for x in scaled]
