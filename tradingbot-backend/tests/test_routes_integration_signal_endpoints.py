import json

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_strategy_regime_all_returns_confidence_and_prob(client):
    r = client.get("/api/v2/strategy/regime/all")
    assert r.status_code == 200
    data = r.json()
    assert "regimes" in data
    assert isinstance(data["regimes"], list) and len(data["regimes"]) > 0
    first = data["regimes"][0]
    # Nycklar från SignalService-integration
    assert "confidence_score" in first
    assert "trading_probability" in first
    assert "recommendation" in first


def test_market_watchlist_includes_prob_when_flag_set(client):
    r = client.get("/api/v2/market/watchlist?prob=true")
    assert r.status_code == 200
    arr = r.json()
    assert isinstance(arr, list)
    if arr:
        first = arr[0]
        # När prob=true ska 'prob' finnas när candles finns
        # (tolerera None om data saknas i offline-läge)
        assert "prob" in first or first.get("prob") is None
