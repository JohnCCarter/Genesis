import os
import pytest


@pytest.mark.asyncio
async def test_prob_preview_and_trade_block_reasons(monkeypatch):
    os.environ.setdefault("AUTH_REQUIRED", "False")
    from fastapi.testclient import TestClient
    from main import app

    # mocka size till > 0 så att trade kommer vidare till riskkontroll
    async def fake_position_size(req, _=True):
        return {
            "size": 0.001,
            "quote_alloc": 10.0,
            "quote_currency": "USD",
            "price": 100.0,
            "atr_sl": 99.0,
            "atr_tp": 101.0,
        }

    monkeypatch.setattr("rest.routes.calculate_position_size", fake_position_size)

    client = TestClient(app)
    pv = client.post("/api/v2/prob/preview", json={"symbol": "tBTCUSD", "timeframe": "1m"})
    assert pv.status_code == 200
    # trade kan blockeras av risk; verifiera ok flagga eller error nyckel
    tr = client.post("/api/v2/prob/trade", json={"symbol": "tBTCUSD", "timeframe": "1m"})
    assert tr.status_code == 200
    data = tr.json()
    assert "ok" in data
