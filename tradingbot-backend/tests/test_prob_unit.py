import pytest


def test_prob_features_basic():
    from services.prob_features import compute_features_from_candles

    candles = [
        [0, 0, 100, 105, 95, 1],
        [0, 0, 101, 106, 96, 1],
        [0, 0, 102, 107, 97, 1],
        [0, 0, 103, 108, 98, 1],
        [0, 0, 104, 109, 99, 1],
    ]
    feats = compute_features_from_candles(candles)
    assert set(["ema_diff", "rsi_norm", "atr_pct", "price"]).issubset(feats.keys())


def test_prob_model_fallback():
    from services.prob_model import ProbabilityModel

    pm = ProbabilityModel()
    pm.enabled = False
    out = pm.predict_proba({"ema": 0.0, "rsi": 0.0})
    assert out["hold"] >= 0.99
