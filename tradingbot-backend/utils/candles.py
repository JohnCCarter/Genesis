from __future__ import annotations

from typing import Dict, List


def parse_candles_to_strategy_data(candles: list[list]) -> dict[str, list[float]]:
    """
    Konverterar Bitfinex candle-listor till strategi-format.

    Bitfinex candle format: [MTS, OPEN, CLOSE, HIGH, LOW, VOLUME]
    Returnerar dict med keys: closes, highs, lows
    """
    if not candles:
        return {"closes": [], "highs": [], "lows": []}

    closes: list[float] = []
    highs: list[float] = []
    lows: list[float] = []

    for candle in candles:
        if isinstance(candle, list) and len(candle) >= 5:
            try:
                closes.append(float(candle[2]))
                highs.append(float(candle[3]))
                lows.append(float(candle[4]))
            except (ValueError, TypeError, IndexError):
                continue

    return {"closes": closes, "highs": highs, "lows": lows}
