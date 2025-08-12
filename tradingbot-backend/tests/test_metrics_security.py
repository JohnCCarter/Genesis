import base64

from fastapi.testclient import TestClient


def _get_client():
    # Importera app sent så att env-ändringar hinner slå igenom
    from main import app

    return TestClient(app)


def test_metrics_public_when_no_security(monkeypatch):
    # Rensa alla säkerhetsrelaterade envs
    for key in [
        "METRICS_ACCESS_TOKEN",
        "METRICS_BASIC_AUTH_USER",
        "METRICS_BASIC_AUTH_PASS",
        "METRICS_IP_ALLOWLIST",
    ]:
        monkeypatch.delenv(key, raising=False)

    client = _get_client()
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "tradingbot_orders_total" in resp.text


def test_metrics_token_protected_ok(monkeypatch):
    monkeypatch.setenv("METRICS_ACCESS_TOKEN", "secret123")
    monkeypatch.delenv("METRICS_BASIC_AUTH_USER", raising=False)
    monkeypatch.delenv("METRICS_BASIC_AUTH_PASS", raising=False)
    monkeypatch.delenv("METRICS_IP_ALLOWLIST", raising=False)

    client = _get_client()
    resp = client.get("/metrics?token=secret123")
    assert resp.status_code == 200


def test_metrics_token_protected_forbidden(monkeypatch):
    monkeypatch.setenv("METRICS_ACCESS_TOKEN", "secret123")
    monkeypatch.delenv("METRICS_BASIC_AUTH_USER", raising=False)
    monkeypatch.delenv("METRICS_BASIC_AUTH_PASS", raising=False)
    monkeypatch.delenv("METRICS_IP_ALLOWLIST", raising=False)

    client = _get_client()
    resp = client.get("/metrics?token=wrong")
    assert resp.status_code == 403


def test_metrics_basic_auth_ok(monkeypatch):
    monkeypatch.delenv("METRICS_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("METRICS_BASIC_AUTH_USER", "metrics")
    monkeypatch.setenv("METRICS_BASIC_AUTH_PASS", "changeme")
    monkeypatch.delenv("METRICS_IP_ALLOWLIST", raising=False)

    client = _get_client()
    token = base64.b64encode(b"metrics:changeme").decode("ascii")
    resp = client.get("/metrics", headers={"Authorization": f"Basic {token}"})
    assert resp.status_code == 200


def test_metrics_basic_auth_unauthorized(monkeypatch):
    monkeypatch.delenv("METRICS_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("METRICS_BASIC_AUTH_USER", "metrics")
    monkeypatch.setenv("METRICS_BASIC_AUTH_PASS", "changeme")
    monkeypatch.delenv("METRICS_IP_ALLOWLIST", raising=False)

    client = _get_client()
    bad = base64.b64encode(b"metrics:wrong").decode("ascii")
    resp = client.get("/metrics", headers={"Authorization": f"Basic {bad}"})
    assert resp.status_code == 401
