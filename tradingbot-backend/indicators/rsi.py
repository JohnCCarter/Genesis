"""
RSI (Relative Strength Index) Indicator - TradingBot Backend

Denna modul implementerar RSI-beräkningar för teknisk analys.
Inkluderar RSI-formel och signalgenerering.
"""

from typing import List, Optional

import pandas as pd

from utils.logger import get_logger

logger = get_logger(__name__)


def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    """
    Beräknar Relative Strength Index (RSI).

    Args:
        prices: Lista med prisdata
        period: RSI-period (standard: 14)

    Returns:
        float: RSI-värde eller None om otillräcklig data
    """
    if len(prices) < period + 1:
        logger.warning(f"Otillräcklig data för RSI-beräkning. Kräver {period + 1}, fick {len(prices)}")
        return None

    series = pd.Series(prices)
    delta = series.diff().dropna()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window=period).mean().iloc[-1]
    avg_loss = loss.rolling(window=period).mean().iloc[-1]

    if avg_loss == 0:
        rsi_value = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi_value = 100 - (100 / (1 + rs))

    logger.debug(f"RSI beräknad: {rsi_value:.2f} (period: {period})")
    return round(rsi_value, 2)
