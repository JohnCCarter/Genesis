import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("AUTH_REQUIRED", "False")


@pytest.mark.asyncio
def test_prob_predict_endpoint():
    from main import app

    client = TestClient(app)
    resp = client.post("/api/v2/prob/predict", json={"symbol": "tBTCUSD", "timeframe": "1m"})
    assert resp.status_code == 200
    data = resp.json()
    assert "probabilities" in data
    assert "decision" in data


@pytest.mark.asyncio
def test_prob_validate_endpoint():
    from main import app

    client = TestClient(app)
    resp = client.post(
        "/api/v2/prob/validate",
        json={"symbol": "tBTCUSD", "timeframe": "1m", "limit": 50},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "brier" in data
    assert "logloss" in data
    # Additional sanity: source/schema present with correct fallback logic
    assert "source" in data
    assert data["source"] in ("model", "heuristic")
    if data["source"] == "model":
        assert data.get("schema") is not None
    else:
        # Heuristic fallback should not report a model schema
        assert data.get("schema") is None
