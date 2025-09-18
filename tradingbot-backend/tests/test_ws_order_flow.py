"""
Tester för WS-orderflöde (via REST wrappers och ren WS 'on') och dry-run.
"""

import os
import pytest
import httpx


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_order_rest_endpoint_returns_error_in_pytest() -> None:
    os.environ.setdefault("AUTH_REQUIRED", "False")
    os.environ.setdefault("DRY_RUN_ENABLED", "True")
    from main import app  # type: ignore

    async with httpx.AsyncClient(app=app, base_url="http://test") as c:
        payload = {
            "symbol": "tADAUSD",
            "amount": "50",
            "type": "EXCHANGE MARKET",
            "side": "buy",
        }
        r = await c.post("/api/v2/order", json=payload, headers={"Authorization": "Bearer dev"})
        assert r.status_code == 200
        js = r.json()
        # I pytest: dry-run och WS-fallback är avstängda → förväntat felutfall
        assert js.get("success") is False
        assert isinstance(js.get("error"), str) and len(js.get("error")) > 0


@pytest.mark.anyio
async def test_ws_wrappers_subscribe_unsubscribe() -> None:
    os.environ.setdefault("AUTH_REQUIRED", "False")
    from main import app  # type: ignore

    async with httpx.AsyncClient(app=app, base_url="http://test") as c:
        # Subscribe ticker
        r1 = await c.post(
            "/api/v2/ws/subscribe",
            json={"channel": "ticker", "symbol": "tBTCUSD"},
            headers={"Authorization": "Bearer dev"},
        )
        assert r1.status_code == 200
        assert r1.json().get("success") is True

        # Unsubscribe ticker
        r2 = await c.post(
            "/api/v2/ws/unsubscribe",
            json={"channel": "ticker", "symbol": "tBTCUSD"},
            headers={"Authorization": "Bearer dev"},
        )
        assert r2.status_code == 200
        assert r2.json().get("success") is True


@pytest.mark.anyio
async def test_ws_order_on_dry_run() -> None:
    # Slå på dry run via toggle och lägg WS order (ska returnera dry_run)
    os.environ.setdefault("AUTH_REQUIRED", "False")
    from main import app  # type: ignore

    async with httpx.AsyncClient(app=app, base_url="http://test") as c:
        # enable dry-run
        r_toggle = await c.post(
            "/api/v2/mode/dry-run",
            json={"enabled": True},
            headers={"Authorization": "Bearer dev"},
        )
        assert r_toggle.status_code == 200
        # WS order (on)
        ws_payload = {
            "type": "EXCHANGE MARKET",
            "symbol": "tBTCUSD",
            "amount": "1",
            "side": "buy",
        }
        r_on = await c.post(
            "/api/v2/ws/order",
            json=ws_payload,
            headers={"Authorization": "Bearer dev"},
        )
        assert r_on.status_code == 200
        js = r_on.json()
        assert js.get("success") is True
        assert js.get("data", {}).get("dry_run") is True


@pytest.mark.anyio
async def test_pure_ws_order_symbol_resolution(monkeypatch) -> None:
    # Verifiera att order_on resolverar TEST-symboler till giltig tPAIR utan riktig WS
    os.environ.setdefault("AUTH_REQUIRED", "False")
    from services.bitfinex_websocket import bitfinex_ws  # type: ignore

    sent_messages = []

    async def fake_auth():
        return True

    async def fake_send(msg):
        sent_messages.append(msg)

    monkeypatch.setattr(bitfinex_ws, "ensure_authenticated", fake_auth)
    monkeypatch.setattr(bitfinex_ws, "send", fake_send)

    payload = {
        "type": "EXCHANGE LIMIT",
        "symbol": "tTESTADA:TESTUSD",
        "amount": "1",
        "side": "buy",
        "price": "0.1",
    }
    res = await bitfinex_ws.order_on(payload)
    assert res.get("success") is True
    assert sent_messages, "No WS message captured"
    # WS-protokollet: [0, 'on', None, body]
    body = sent_messages[-1][3]
    assert isinstance(body, dict)
    assert str(body.get("symbol", "")).startswith("tADA")
