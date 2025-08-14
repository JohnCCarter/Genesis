import os
import pytest


@pytest.mark.asyncio
async def test_prob_config_get_and_post(monkeypatch):
    os.environ.setdefault("AUTH_REQUIRED", "False")
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)

    # GET current config
    r = client.get("/api/v2/prob/config")
    assert r.status_code == 200
    data = r.json()
    for key in (
        "model_enabled",
        "model_file",
        "ev_threshold",
        "confidence_min",
        "autotrade_enabled",
        "size_max_risk_pct",
        "size_kelly_cap",
        "size_conf_weight",
        "position_size_fallback_quote",
        "loaded",
    ):
        assert key in data

    # POST update some values
    r2 = client.post(
        "/api/v2/prob/config",
        json={
            "confidence_min": 0.2,
            "autotrade_enabled": True,
            "size_max_risk_pct": 1.5,
        },
    )
    assert r2.status_code == 200
    updated = r2.json()
    assert float(updated.get("confidence_min", 0)) == 0.2
    assert bool(updated.get("autotrade_enabled")) is True
    assert float(updated.get("size_max_risk_pct", 0)) == 1.5
