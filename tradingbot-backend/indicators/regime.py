from __future__ import annotations

from typing import Literal

import numpy as np

from indicators.adx import adx as adx_series

Regime = Literal["trend", "range", "balanced"]


def ema(series: list[float], span: int) -> list[float]:
    if not series:
        return []
    span = max(2, int(span))
    alpha = 2.0 / (span + 1.0)
    out = [float(series[0])]
    for i in range(1, len(series)):
        out.append(alpha * float(series[i]) + (1 - alpha) * out[-1])
    return out


def ema_z(close: list[float], fast: int = 3, slow: int = 7, z_win: int = 200) -> list[float]:
    if not close:
        return []
    ef = np.array(ema(close, fast), dtype=float)
    es = np.array(ema(close, slow), dtype=float)
    slope = ef - es
    z = np.zeros_like(slope)
    win = max(10, int(z_win))
    for i in range(len(slope)):
        lo = max(0, i - win + 1)
        seg = slope[lo : i + 1]
        mu = float(seg.mean())
        sd = float(seg.std())
        z[i] = (slope[i] - mu) / (sd + 1e-9)
    return [float(x) for x in z]


def detect_regime(high: list[float], low: list[float], close: list[float], cfg: dict) -> Regime:
    if not close or not high or not low:
        return "balanced"
    adx_vals = adx_series(high, low, close, period=int(cfg.get("ADX_PERIOD", 14)))
    a = float(adx_vals[-1]) if adx_vals else 0.0
    ez_vals = ema_z(
        close,
        int(cfg.get("EMA_FAST", 3)),
        int(cfg.get("EMA_SLOW", 7)),
        int(cfg.get("Z_WIN", 200)),
    )
    ez = float(ez_vals[-1]) if ez_vals else 0.0
    ez_abs = abs(ez)

    # Trend: hög ADX eller stark EMA-slope
    if a >= float(cfg.get("ADX_HIGH", 30.0)) or ez_abs >= float(cfg.get("SLOPE_Z_HIGH", 1.0)):
        return "trend"
    # Range: låg ADX och svag EMA-slope
    if a <= float(cfg.get("ADX_LOW", 15.0)) and ez_abs <= float(cfg.get("SLOPE_Z_LOW", 0.5)):
        return "range"
    # Balanced: mellanliggande värden
    return "balanced"
