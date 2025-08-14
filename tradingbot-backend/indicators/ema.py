"""
EMA (Exponential Moving Average) Indicator - TradingBot Backend

Denna modul implementerar EMA-beräkningar för teknisk analys.
Inkluderar EMA-formel och olika perioder.
"""

from typing import List, Optional

import pandas as pd

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
