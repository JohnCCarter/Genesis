"""
Probabilistic Model - Feature extraction and labeling helpers

Builds simple, robust features and labels from Bitfinex candle data.

Bitfinex candle frame v2: [MTS, OPEN, CLOSE, HIGH, LOW, VOLUME]
"""

from __future__ import annotations

from typing import Any

from indicators.atr import calculate_atr
from indicators.ema import calculate_ema
from indicators.rsi import calculate_rsi


def _split_candles(
    candles: list[list[float]],
) -> tuple[list[float], list[float], list[float]]:
    closes: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    for row in candles:
        if not isinstance(row, (list, tuple)) or len(row) < 5:
            continue
        closes.append(float(row[2]))
        highs.append(float(row[3]))
        lows.append(float(row[4]))
    return closes, highs, lows


def compute_features_from_candles(candles: list[list[float]]) -> dict[str, float]:
    """
    Compute features for the last candle in the sequence.
    Returns a dict like {"ema_diff": x, "rsi_norm": y, "atr_pct": z}
    """
    closes, highs, lows = _split_candles(candles)
    if len(closes) < 5:
        # Returnera defensiva nollor men inkludera price för konsistent schema
        price_fallback = float(closes[-1]) if closes else 0.0
        return {
            "ema_diff": 0.0,
            "rsi_norm": 0.0,
            "atr_pct": 0.0,
            "price": price_fallback,
        }
    price = float(closes[-1])
    # EMA / RSI use simple defaults; production uses per-symbol settings
    ema = calculate_ema(closes, period=min(10, len(closes))) or price
    rsi = calculate_rsi(closes, period=min(14, len(closes))) or 50.0
    atr = calculate_atr(highs, lows, closes, period=min(14, len(closes))) or 0.0
    # Features
    ema_diff = (price - float(ema)) / (abs(float(ema)) + 1e-9)
    # RSI normalized to [-1, 1]: 50 -> 0, <30 positive, >70 negative preference can be learned
    rsi_norm = (50.0 - max(min(float(rsi), 100.0), 0.0)) / 50.0
    atr_pct = float(atr) / (abs(price) + 1e-9)
    return {
        "ema_diff": float(ema_diff),
        "rsi_norm": float(rsi_norm),
        "atr_pct": float(atr_pct),
        "price": price,
    }


def label_sequence(
    candles: list[list[float]], horizon: int, tp: float, sl: float
) -> list[str]:
    """
    Label each index i with buy/sell/hold based on future returns within horizon.
    - buy if max_future_return >= tp
    - sell if min_future_return <= -sl
    - else hold
    The last `horizon` samples cannot be labeled and are dropped.
    """
    closes, _highs, _lows = _split_candles(candles)
    n = len(closes)
    labels: list[str] = []
    if n <= horizon:
        return labels
    for i in range(0, n - horizon):
        p0 = float(closes[i])
        future = [float(x) for x in closes[i + 1 : i + 1 + horizon]]
        if not future:
            break
        max_ret = (max(future) - p0) / (abs(p0) + 1e-9)
        min_ret = (min(future) - p0) / (abs(p0) + 1e-9)
        if max_ret >= tp:
            labels.append("buy")
        elif min_ret <= -sl:
            labels.append("sell")
        else:
            labels.append("hold")
    return labels


def build_dataset(
    candles: list[list[float]], horizon: int, tp: float, sl: float
) -> list[dict[str, Any]]:
    """
    Build a small dataset of features + label aligned by dropping last horizon samples.
    Returns list of dicts: {ema_diff, rsi_norm, atr_pct, price, label}
    """
    labels = label_sequence(candles, horizon, tp, sl)
    if not labels:
        return []
    # Align features: compute per index using the same index into candles
    samples: list[dict[str, Any]] = []
    for i in range(0, len(labels)):
        feats = compute_features_from_candles(candles[: i + 1])
        row = {**feats, "label": labels[i]}
        samples.append(row)
    return samples
