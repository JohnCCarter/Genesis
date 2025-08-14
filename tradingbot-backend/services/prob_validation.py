"""
Validation helpers for the probability model.

Computes multi-class Brier score and LogLoss against labels built from
historical candles. Uses the same feature builder as training to ensure
alignment between train/infer.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from services.prob_features import build_dataset
from services.prob_model import prob_model

Label = str


def _one_hot(label: Label) -> tuple[float, float, float]:
    if label == "buy":
        return 1.0, 0.0, 0.0
    if label == "sell":
        return 0.0, 1.0, 0.0
    return 0.0, 0.0, 1.0


def _scores_for(probs: dict[str, float], label: Label, eps: float = 1e-12) -> tuple[float, float]:
    """
    Return (brier, logloss) for a single sample.
    - Brier (multi-class): sum_k (p_k - y_k)^2
    - LogLoss: -log(p_true)
    """
    p_buy = float(probs.get("buy", 0.0))
    p_sell = float(probs.get("sell", 0.0))
    p_hold = float(probs.get("hold", 0.0))
    yb, ys, yh = _one_hot(label)
    brier = (p_buy - yb) ** 2 + (p_sell - ys) ** 2 + (p_hold - yh) ** 2
    if label == "buy":
        p_true = max(p_buy, eps)
    elif label == "sell":
        p_true = max(p_sell, eps)
    else:
        p_true = max(p_hold, eps)
    logloss = -math.log(p_true)
    return brier, logloss


def validate_on_candles(
    candles: list[list[float]],
    horizon: int,
    tp: float,
    sl: float,
    max_samples: int | None = None,
) -> dict[str, Any]:
    """
    Build dataset from candles, run model inference per sample,
    compute metrics. Returns summary dict with overall Brier/LogLoss
    and per-label breakdown.
    """
    ds = build_dataset(candles, horizon=horizon, tp=tp, sl=sl)
    if not ds:
        return {
            "samples": 0,
            "brier": None,
            "logloss": None,
            "by_label": {},
            "source": ("model" if prob_model.enabled else "heuristic"),
            "schema": prob_model.model_meta.get("schema"),
        }

    if isinstance(max_samples, int) and max_samples > 0:
        ds = ds[-max_samples:]

    total_brier = 0.0
    total_logloss = 0.0
    n = 0

    by_label: dict[str, dict[str, Any]] = {
        "buy": {"n": 0, "brier": 0.0, "logloss": 0.0, "avg_p_true": 0.0},
        "sell": {"n": 0, "brier": 0.0, "logloss": 0.0, "avg_p_true": 0.0},
        "hold": {"n": 0, "brier": 0.0, "logloss": 0.0, "avg_p_true": 0.0},
    }

    for row in ds:
        feats = {
            "ema_diff": float(row.get("ema_diff", 0.0)),
            "rsi_norm": float(row.get("rsi_norm", 0.0)),
            "atr_pct": float(row.get("atr_pct", 0.0)),
        }
        label: Label = str(row.get("label", "hold"))
        probs = prob_model.predict_proba(feats)
        b, ll = _scores_for(probs, label)
        total_brier += float(b)
        total_logloss += float(ll)
        n += 1

        bucket = by_label[label]
        bucket["n"] += 1
        bucket["brier"] += float(b)
        bucket["logloss"] += float(ll)
        if label == "buy":
            bucket["avg_p_true"] += float(probs.get("buy", 0.0))
        elif label == "sell":
            bucket["avg_p_true"] += float(probs.get("sell", 0.0))
        else:
            bucket["avg_p_true"] += float(probs.get("hold", 0.0))

    if n == 0:
        return {
            "samples": 0,
            "brier": None,
            "logloss": None,
            "by_label": {},
            "source": ("model" if prob_model.enabled else "heuristic"),
            "schema": prob_model.model_meta.get("schema"),
        }

    # finalize averages
    summary_by_label: dict[str, dict[str, Any]] = {}
    for k, v in by_label.items():
        if v["n"] > 0:
            summary_by_label[k] = {
                "n": v["n"],
                "brier": v["brier"] / v["n"],
                "logloss": v["logloss"] / v["n"],
                "avg_p_true": v["avg_p_true"] / v["n"],
            }

    return {
        "samples": n,
        "brier": total_brier / n,
        "logloss": total_logloss / n,
        "by_label": summary_by_label,
        "source": ("model" if prob_model.enabled else "heuristic"),
        "schema": prob_model.model_meta.get("schema"),
    }
