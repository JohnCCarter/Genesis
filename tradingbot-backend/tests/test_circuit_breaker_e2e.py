import os

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_circuit_breaker_open_and_reset(monkeypatch):
    # Stäng av auth för test
    monkeypatch.setenv("AUTH_REQUIRED", "False")

    from main import app

    client = TestClient(app)

    # Säkerställa initial status (kan sakna name-param och returnera alla)
    r0 = client.get("/api/v2/circuit-breaker/status")
    assert r0.status_code == 200

    # 1) Registrera 3 failures för trading (threshold=3 i default-config)
    for _ in range(3):
        r = client.post(
            "/api/v2/circuit-breaker/record-failure",
            json={"name": "trading", "error_type": "test"},
        )
        assert r.status_code == 200, r.text

    # 2) Hämta status för just trading och verifiera OPEN
    r_status = client.get("/api/v2/circuit-breaker/status", params={"name": "trading"})
    assert r_status.status_code == 200, r_status.text
    data = r_status.json()
    assert data.get("name") == "trading"
    assert data.get("state") in ("open", "half_open", "closed")
    # Vid korrekt öppning ska den vara open; tolerera half_open om cooldown passerat snabbt
    assert data.get("state") in ("open", "half_open")

    # 3) Reset specifik CB och verifiera closed
    r_reset = client.post("/api/v2/circuit-breaker/reset", json={"name": "trading"})
    assert r_reset.status_code == 200, r_reset.text
    r_status2 = client.get("/api/v2/circuit-breaker/status", params={"name": "trading"})
    assert r_status2.status_code == 200, r_status2.text
    data2 = r_status2.json()
    assert data2.get("name") == "trading"
    assert data2.get("state") == "closed"

    # 4) Extra: verifiera att metrics flaggor stängts (best‑effort)
    r_metrics = client.get("/metrics/summary")
    assert r_metrics.status_code == 200
