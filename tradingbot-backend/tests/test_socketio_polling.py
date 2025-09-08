import os
import httpx


def test_socketio_polling_handshake(monkeypatch):
    # Säkerställ ingen auth i test
    monkeypatch.setenv("AUTH_REQUIRED", "False")

    base = os.environ.get("API_BASE", "http://127.0.0.1:8000")
    url = f"{base}/ws/socket.io/?EIO=4&transport=polling"
    with httpx.Client(timeout=3.0) as client:
        r = client.get(url)
        assert r.status_code == 200, r.text
