import os

from fastapi.testclient import TestClient


def _client():
    os.environ.setdefault("AUTH_REQUIRED", "False")
    from main import app

    return TestClient(app)


def test_contract_risk_unified_status():
    c = _client()
    r = c.get("/api/v2/risk/unified/status")
    assert r.status_code == 200
    js = r.json()
    for key in (
        "current_equity",
        "daily_loss_percentage",
        "drawdown_percentage",
        "guards_full",
    ):
        assert key in js


def test_contract_validation_v2_endpoints():
    c = _client()
    body = {"symbol": "tBTCUSD", "timeframe": "1m", "limit": 100}
    r1 = c.post("/api/v2/validation/probability", json={**body, "max_samples": 10})
    assert r1.status_code == 200
    r2 = c.post("/api/v2/validation/strategy", json={**body, "strategy_params": {}})
    assert r2.status_code == 200
    r3 = c.post(
        "/api/v2/validation/backtest",
        json={**body, "initial_capital": 10000.0, "strategy_params": {}},
    )
    assert r3.status_code == 200
    r4 = c.get("/api/v2/validation/history")
    assert r4.status_code == 200
    hist = r4.json()
    assert "validation_history" in hist


def test_contract_circuit_breaker_endpoints():
    c = _client()
    # status all
    rs = c.get("/api/v2/circuit-breaker/status")
    assert rs.status_code == 200
    # record failure/success + reset for trading
    rf = c.post(
        "/api/v2/circuit-breaker/record-failure",
        json={"name": "trading", "error_type": "test"},
    )
    assert rf.status_code == 200
    rr = c.post("/api/v2/circuit-breaker/reset", json={"name": "trading"})
    assert rr.status_code == 200


def test_contract_market_endpoints():
    c = _client()
    # platform status
    r0 = c.get("/api/v2/platform/status")
    assert r0.status_code == 200
    # symbols
    r1 = c.get("/api/v2/market/symbols")
    assert r1.status_code == 200
    # candles (smal limit)
    r2 = c.get("/api/v2/market/candles/tBTCUSD", params={"timeframe": "1m", "limit": 5})
    assert r2.status_code == 200
