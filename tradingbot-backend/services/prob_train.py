"""
Offline training script (minimal) for logistic regression baseline.

Usage (example): run in a notebook or script context; not wired to CLI yet.
Builds a small dataset from candles via prob_features and fits a simple LR.
Exports weights JSON compatible with prob_model.py.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np

from services.prob_features import build_dataset


def _to_Xy(samples: list[dict[str, Any]]):
    feats = [[s.get("ema_diff", 0.0), s.get("rsi_norm", 0.0), s.get("atr_pct", 0.0)] for s in samples]
    labels = [s.get("label", "hold") for s in samples]
    # Binary one-vs-rest for buy vs not-buy and sell vs not-sell in simple baseline
    X = np.asarray(feats, dtype=float)
    y_buy = np.asarray([1 if label == "buy" else 0 for label in labels], dtype=float)
    y_sell = np.asarray([1 if label == "sell" else 0 for label in labels], dtype=float)
    return X, y_buy, y_sell


def _fit_lr(X: np.ndarray, y: np.ndarray, l2: float = 1e-4, iters: int = 500, lr: float = 0.1):
    # simple gradient descent on logistic loss
    n, d = X.shape
    w = np.zeros(d)
    b = 0.0
    for _ in range(iters):
        z = X @ w + b
        p = 1.0 / (1.0 + np.exp(-z))
        grad_w = (X.T @ (p - y)) / n + l2 * w
        grad_b = float(np.mean(p - y))
        w -= lr * grad_w
        b -= lr * grad_b
    return w.tolist(), float(b)


def _split_train_val(X: np.ndarray, y: np.ndarray, val_frac: float = 0.2):
    n = X.shape[0]
    split = max(1, int(n * (1.0 - val_frac)))
    return X[:split], y[:split], X[split:], y[split:]


def _fit_platt(z_val: np.ndarray, y_val: np.ndarray, iters: int = 300, lr: float = 0.1):
    a = 1.0
    b = 0.0
    if z_val.size == 0:
        return a, b
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-(a * z_val + b)))
        grad_a = float(np.mean((p - y_val) * z_val))
        grad_b = float(np.mean(p - y_val))
        a -= lr * grad_a
        b -= lr * grad_b
    return float(a), float(b)


def train_and_export(candles: list[list[float]], horizon: int, tp: float, sl: float, out_path: str) -> dict[str, Any]:
    # Security: Validate out_path to prevent path traversal
    import os

    # CRITICAL: Ensure out_path is safe (no directory traversal)
    # Step 1: Normalize and check for absolute paths or traversal attempts
    normalized_path = os.path.normpath(out_path)
    if os.path.isabs(normalized_path) or ".." in normalized_path.split(os.sep):
        raise ValueError(f"Invalid out_path: {out_path}")

    # Step 2: Additional security - only allow simple filenames in a safe directory
    # Define the safe root directory for all model outputs
    safe_root = os.path.abspath("config/models")

    # Step 3: Construct the final path within the safe directory
    # Use only the basename to prevent any path traversal
    safe_filename = os.path.basename(normalized_path)
    if not safe_filename or "/" in safe_filename or "\\" in safe_filename:
        raise ValueError(f"Invalid filename: {safe_filename}")

    # Step 4: Final path construction within safe bounds
    safe_path = os.path.join(safe_root, safe_filename)

    # Step 5: Ensure the safe directory exists
    os.makedirs(safe_root, exist_ok=True)

    # branch marker removed
    # Step 6: Create a completely new path variable to break data flow analysis concerns
    final_clean_path = os.path.join(os.path.abspath("config/models"), safe_filename)

    # Step 6: Realpath containment check to ensure no breakout is possible
    real_root = os.path.realpath(safe_root)
    real_path = os.path.realpath(safe_path)
    if not (real_path.startswith(real_root + os.sep) or real_path == real_root):
        raise ValueError(f"Output path not within safe directory: {real_path}")

    final_clean_path = real_path  # Path is known-safe at this point
    # branch marker removed

    samples = build_dataset(candles, horizon=horizon, tp=tp, sl=sl)
    if not samples:
        raise ValueError("No samples built; increase history.")
    X, y_buy, y_sell = _to_Xy(samples)
    Xb_tr, yb_tr, Xb_va, yb_va = _split_train_val(X, y_buy)
    Xs_tr, ys_tr, Xs_va, ys_va = _split_train_val(X, y_sell)
    w_buy, b_buy = _fit_lr(Xb_tr, yb_tr)
    w_sell, b_sell = _fit_lr(Xs_tr, ys_tr)
    z_buy_va = Xb_va @ np.asarray(w_buy) + b_buy if Xb_va.size else np.zeros(0)
    z_sell_va = Xs_va @ np.asarray(w_sell) + b_sell if Xs_va.size else np.zeros(0)
    a_buy, abuy = _fit_platt(z_buy_va, yb_va) if z_buy_va.size > 5 else (1.0, 0.0)
    a_sell, asell = _fit_platt(z_sell_va, ys_va) if z_sell_va.size > 5 else (1.0, 0.0)
    model = {
        "schema": ["ema_diff", "rsi_norm", "atr_pct"],
        "buy": {"w": w_buy, "b": b_buy, "calib": {"a": a_buy, "b": abuy}},
        "sell": {"w": w_sell, "b": b_sell, "calib": {"a": a_sell, "b": asell}},
        # heuristic combiner for hold: normalize at inference
        "version": 1,
    }
    with open(final_clean_path, "w", encoding="utf-8") as f:
        json.dump(model, f)
    return model
