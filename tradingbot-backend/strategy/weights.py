from __future__ import annotations

import numpy as np

PRESETS: dict[str, dict] = {
    "trend": {
        "w_ema": 0.5,
        "w_rsi": 0.1,
        "w_atr": 0.4,
        "params": {"ema_fast": 12, "ema_slow": 55, "rsi_period": 14, "atr_mult": 2.0},
    },
    "range": {
        "w_ema": 0.3,
        "w_rsi": 0.6,
        "w_atr": 0.1,
        "params": {"ema_fast": 9, "ema_slow": 21, "rsi_period": 14, "atr_mult": 1.2},
    },
    "balanced": {
        "w_ema": 0.4,
        "w_rsi": 0.4,
        "w_atr": 0.2,
        "params": {"ema_fast": 12, "ema_slow": 34, "rsi_period": 14, "atr_mult": 1.6},
    },
}


def clamp_simplex(weights: dict[str, float], bounds=(0.1, 0.7)) -> dict[str, float]:
    keys = list(weights.keys())
    v = np.array([float(weights[k]) for k in keys], dtype=float)
    lo, hi = float(bounds[0]), float(bounds[1])
    v = np.clip(v, lo, hi)
    s = float(v.sum())
    if s <= 0:
        v = np.array([1.0 / max(1, len(v))] * len(v))
    else:
        v = v / s
    return {k: float(v[i]) for i, k in enumerate(keys)}
