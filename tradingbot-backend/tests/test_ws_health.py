import os

from fastapi.testclient import TestClient


def test_ws_health_and_metrics_endpoints():
    os.environ.setdefault("AUTH_REQUIRED", "False")
    from main import app

    client = TestClient(app)

    # WS pool status
    r = client.get("/api/v2/ws/pool/status")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)

    # Prometheus metrics root
    r2 = client.get("/metrics")
    assert r2.status_code in (200, 403, 401)  # kan vara skyddad i vissa miljöer

    # Metrics summary JSON
    r3 = client.get("/metrics/summary")
    assert r3.status_code == 200
    js = r3.json()
    assert "latency" in js and "errors" in js

    # Observability comprehensive
    r4 = client.get("/api/v2/observability/comprehensive")
    assert r4.status_code == 200
    comp = r4.json()
    assert isinstance(comp, dict)
