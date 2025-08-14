import pytest


def test_compute_features_short_history_returns_zeros():
    from services.prob_features import compute_features_from_candles

    candles = [
        [0, 0, 100, 105, 95, 1],
        [0, 0, 101, 106, 96, 1],
    ]
    feats = compute_features_from_candles(candles)
    assert feats["ema_diff"] == 0.0
    assert feats["rsi_norm"] == 0.0
    assert feats["atr_pct"] == 0.0


def test_label_sequence_tp_sl_hold():
    from services.prob_features import label_sequence

    # Konstruera candles så att tp uppnås först, sedan sl, sedan hold
    base = 100.0
    candles = []
    # stigande -> buy
    for i in range(5):
        px = base + i * 0.5
        candles.append([0, 0, px, px, px, 1])
    # fallande -> sell
    for i in range(5):
        px = base - i * 0.5
        candles.append([0, 0, px, px, px, 1])
    # platt -> hold
    for _ in range(5):
        candles.append([0, 0, base, base, base, 1])

    labs = label_sequence(candles, horizon=3, tp=0.01, sl=0.01)
    assert isinstance(labs, list)
    assert len(labs) > 0
    assert set(labs).issubset({"buy", "sell", "hold"})


def test_build_dataset_alignment():
    from services.prob_features import build_dataset

    candles = [[0, 0, 100 + i, 101 + i, 99 + i, 1] for i in range(20)]
    ds = build_dataset(candles, horizon=5, tp=0.01, sl=0.01)
    # dataset ska innehålla label per rad och featuresnycklar
    assert len(ds) > 0
    row = ds[0]
    for key in ("ema_diff", "rsi_norm", "atr_pct", "price", "label"):
        assert key in row
