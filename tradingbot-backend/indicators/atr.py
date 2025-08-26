"""
ATR (Average True Range) Indicator - TradingBot Backend

Denna modul implementerar ATR-beräkningar för volatilitetsanalys.
Inkluderar ATR-formel och volatilitetsbaserade strategier.
"""

from typing import List, Optional

import pandas as pd

from utils.logger import get_logger

logger = get_logger(__name__)


def calculate_atr(
    highs: list[float], lows: list[float], closes: list[float], period: int = 14
) -> float | None:
    """
    Beräknar Average True Range (ATR).

    Args:
        highs: Lista med högsta priser
        lows: Lista med lägsta priser
        closes: Lista med slutpriser
        period: ATR-period (standard: 14)

    Returns:
        float: ATR-värde eller None om otillräcklig data
    """
    if len(highs) < period or len(lows) < period or len(closes) < period:
        logger.warning(
            f"Otillräcklig data för ATR-beräkning. Kräver {period}, fick: highs={len(highs)}, lows={len(lows)}, closes={len(closes)}"
        )
        return None

    df = pd.DataFrame({"high": highs, "low": lows, "close": closes})
    df["previous_close"] = df["close"].shift(1)

    # Beräkna True Range (vektoriserat för prestanda)
    df["tr"] = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - df["previous_close"]).abs(),
            (df["low"] - df["previous_close"]).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr_value = df["tr"].rolling(window=period).mean().iloc[-1]

    logger.debug(f"ATR beräknad: {atr_value:.4f} (period: {period})")
    return round(atr_value, 4)
