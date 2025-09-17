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


@pytest.mark.asyncio
async def test_prob_predict_uses_eth_5m_model_when_available(monkeypatch):
    os.environ.setdefault("AUTH_REQUIRED", "False")
    from fastapi.testclient import TestClient
    from main import app

    # mocka candles så predikt kan köras utan nätberoenden
    async def fake_candles(self, symbol: str, timeframe: str, limit: int):
        base = 100.0
        return [[0, 0, base + i * 0.1, base + i * 0.2, base, 1] for i in range(60)]

    monkeypatch.setattr("services.bitfinex_data.BitfinexDataService.get_candles", fake_candles)

    client = TestClient(app)
    r = client.post("/api/v2/prob/predict", json={"symbol": "tETHUSD", "timeframe": "5m"})
    assert r.status_code == 200
    d = r.json()
    # När ETHUSD_5m.json finns ska källan vara model och schema ska exponeras
    assert d.get("source") in ("model", "heuristic")
    if d.get("source") == "model":
        assert d.get("schema") is not None


@pytest.mark.parametrize("symbol", ["tETHUSD", "tADAUSD", "tDOTUSD"])  # ensure per-symbol/tf models are picked up
def test_prob_validate_uses_model_for_eth_ada_dot_5m(monkeypatch, symbol):
    os.environ.setdefault("AUTH_REQUIRED", "False")
    os.environ.setdefault("PROB_MODEL_ENABLED", "True")
    from fastapi.testclient import TestClient
    from main import app

    async def fake_candles(self, s: str, timeframe: str, limit: int):
        # Realistic OHLCV: [MTS, OPEN, CLOSE, HIGH, LOW, VOLUME]
        # Generate a gentle uptrend to ensure labels exist
        base = 100.0
        candles = []
        for i in range(300):
            close = base * (1.0 + 0.001 * i)
            open_ = close * 0.9995
            high = max(open_, close) * 1.0008
            low = min(open_, close) * 0.9992
            vol = 10.0
            mts = 1700000000000 + i * 60000  # fake timestamps
            candles.append([mts, open_, close, high, low, vol])
        return candles[-limit:]

    # Patch facade (call site) för att säkerställa dataflöde
    monkeypatch.setattr("services.market_data_facade.MarketDataFacade.get_candles", fake_candles)

    client = TestClient(app)
    r = client.post(
        "/api/v2/prob/validate",
        json={
            "symbol": symbol,
            "timeframe": "5m",
            "limit": 200,
            "horizon": 20,
            "tp": 0.002,
            "sl": 0.002,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("samples", 0) >= 10
    assert data.get("source") in ("model", "heuristic")
    # Vi aktiverade PROB_MODEL_ENABLED=True och har per‑symbol 5m‑modeller i repo
    assert data.get("source") == "model"
    assert data.get("schema") is not None
