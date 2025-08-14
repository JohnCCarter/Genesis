import pytest


def test_predict_proba_with_mocked_schema_and_calibration():
    from services.prob_model import ProbabilityModel

    pm = ProbabilityModel()
    pm.enabled = True
    pm._loaded = True  # noqa: SLF001 – test av intern flagga
    # Mocka en enkel modell där x1 driver buy positivt och sell negativt
    pm.model_meta = {
        "schema": ["x1", "x2"],
        "buy": {
            "w": [2.0, 0.0],
            "b": 0.0,
            "calib": {"a": 1.0, "b": 0.0},
        },
        "sell": {
            "w": [-2.0, 0.0],
            "b": 0.0,
            "calib": {"a": 1.0, "b": 0.0},
        },
    }

    out_pos = pm.predict_proba({"x1": 1.0, "x2": 0.0})
    out_neg = pm.predict_proba({"x1": -1.0, "x2": 0.0})

    # Normalisering och rimligt spann
    for out in (out_pos, out_neg):
        assert 0.0 <= out["buy"] <= 1.0
        assert 0.0 <= out["sell"] <= 1.0
        assert 0.0 <= out["hold"] <= 1.0
        s = out["buy"] + out["sell"] + out["hold"]
        assert pytest.approx(s, rel=1e-6) == 1.0

    # x1 positivt -> buy > sell, x1 negativt -> sell > buy
    assert out_pos["buy"] > out_pos["sell"]
    assert out_neg["sell"] > out_neg["buy"]
