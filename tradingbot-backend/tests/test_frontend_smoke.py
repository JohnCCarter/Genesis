from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_get_ws_token():
    r = client.post(
        "/api/v2/auth/ws-token",
        json={"user_id": "frontend_user", "scope": "read", "expiry_hours": 1},
    )
    assert r.status_code in (200, 201)
    data = r.json()
    assert any(k in data for k in ("access_token", "token", "jwt"))


def test_wallets_requires_auth():
    r = client.get("/api/v2/wallets")
    assert r.status_code in (401, 403)


def test_wallets_with_token():
    t = client.post(
        "/api/v2/auth/ws-token",
        json={"user_id": "frontend_user", "scope": "read", "expiry_hours": 1},
    ).json()
    token = t.get("access_token") or t.get("token") or t.get("jwt")
    assert token
    r = client.get("/api/v2/wallets", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code in (200, 204)


