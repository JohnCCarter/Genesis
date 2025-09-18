import os
import pytest


def test_prob_model_disabled_fallback():
    from services.prob_model import ProbabilityModel

    pm = ProbabilityModel()
    pm.enabled = False
    out = pm.predict_proba({"ema_diff": 0.0, "rsi_norm": 0.0, "atr_pct": 0.0})
    assert out["hold"] >= 0.99


@pytest.mark.asyncio
async def test_prob_predict_api_with_mocked_candles(monkeypatch):
    os.environ.setdefault("AUTH_REQUIRED", "False")
    from fastapi.testclient import TestClient
    from main import app

    # mocka candles
    async def fake_candles(self, symbol: str, timeframe: str, limit: int):
        base = 100.0
        return [[0, 0, base + i * 0.1, base + i * 0.2, base, 1] for i in range(60)]

    monkeypatch.setattr("services.bitfinex_data.BitfinexDataService.get_candles", fake_candles)

    client = TestClient(app)
    r = client.post("/api/v2/prob/predict", json={"symbol": "tBTCUSD", "timeframe": "1m"})
    assert r.status_code == 200
    data = r.json()
    assert "probabilities" in data and "decision" in data
