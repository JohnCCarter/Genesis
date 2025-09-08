from fastapi.testclient import TestClient

import main


def test_runtime_config_get_and_set():
    c = TestClient(main.app)
    # get
    r = c.get("/api/v2/runtime/config")
    assert r.status_code == 200
    assert isinstance(r.json().get("overrides"), dict)

    # set
    payload = {"values": {"WS_TICKER_STALE_SECS": 5, "CANDLE_STALE_SECS": 120}}
    r2 = c.post("/api/v2/runtime/config", json=payload)
    assert r2.status_code == 200
    ov = r2.json().get("overrides")
    assert ov.get("WS_TICKER_STALE_SECS") == 5
    assert ov.get("CANDLE_STALE_SECS") == 120
