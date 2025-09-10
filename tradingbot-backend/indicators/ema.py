"""
EMA (Exponential Moving Average) Indicator - TradingBot Backend

Denna modul implementerar EMA-beräkningar för teknisk analys.
Inkluderar EMA-formel och olika perioder.
"""

import pandas as pd
import numpy as np

from utils.logger import get_logger

logger = get_logger(__name__)


def calculate_ema(prices: list[float], period: int = 14) -> float | None:
    """
    Beräknar Exponential Moving Average (EMA).

    Args:
        prices: Lista med prisdata
        period: EMA-period (standard: 14)

    Returns:
        float: EMA-värde eller None om otillräcklig data
    """
    if len(prices) < period:
        logger.warning(f"Otillräcklig data för EMA-beräkning. Kräver {period}, fick {len(prices)}")
        return None

    series = pd.Series(prices)
    ema_value = series.ewm(span=period, adjust=False).mean().iloc[-1]

    logger.debug(f"EMA beräknad: {ema_value:.4f} (period: {period})")
    return round(ema_value, 4)


def ema_z(close: list[float], fast: int = 3, slow: int = 7, z_win: int = 200) -> list[float]:
    """
    Beräknar EMA Z-score för trendanalys.

    Args:
        close: Lista med stängningspriser
        fast: Snabb EMA-period (standard: 3)
        slow: Långsam EMA-period (standard: 7)
        z_win: Z-score fönster (standard: 200)

    Returns:
        list[float]: EMA Z-score värden
    """
    if not close:
        return []

    # Beräkna EMA för snabb och långsam period
    def ema(series: list[float], span: int) -> list[float]:
        if not series:
            return []
        span = max(2, int(span))
        alpha = 2.0 / (span + 1.0)
        out = [float(series[0])]
        for i in range(1, len(series)):
            out.append(alpha * float(series[i]) + (1 - alpha) * out[-1])
        return out

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

    logger.debug(f"EMA Z-score beräknad för {len(close)} datapunkter")
    return [float(x) for x in z]
