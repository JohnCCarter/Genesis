import pytest
from rest.routes import OrderRequest, place_order_endpoint
from services.metrics import metrics_store


@pytest.mark.asyncio
async def test_place_order_rate_limited(monkeypatch):
    # Aktivera rate-limit via settings-monkeypatch (återställs automatiskt)
    from rest import routes as routes_module

    monkeypatch.setattr(
        routes_module.settings, "ORDER_RATE_LIMIT_MAX", 1, raising=False
    )
    monkeypatch.setattr(
        routes_module.settings, "ORDER_RATE_LIMIT_WINDOW", 60, raising=False
    )

    # Stubba place_order så den inte anropas två gånger
    calls = {"count": 0}

    from rest import auth as rest_auth

    async def _fake_place_order(_):
        calls["count"] += 1
        return {"ok": True}

    monkeypatch.setattr(rest_auth, "place_order", _fake_place_order)

    req = OrderRequest(
        symbol="tTESTBTC:TESTUSD",
        amount="1",
        type="EXCHANGE MARKET",
        side="buy",
    )

    # Första ska passera
    resp1 = await place_order_endpoint(req, True)
    # Andra direkt efter ska rate-limita
    resp2 = await place_order_endpoint(req, True)

    assert resp1.success is True or resp1.error is None
    assert resp2.success is False and resp2.error == "rate_limited"


@pytest.mark.asyncio
async def test_place_order_error_monitored(monkeypatch):
    # Arrange: mock place_order to return error
    from rest import auth as rest_auth

    async def _fake_place_order(_):
        return {"error": "simulated"}

    monkeypatch.setattr(rest_auth, "place_order", _fake_place_order)
    # reset metrics
    metrics_store.clear()

    req = OrderRequest(
        symbol="tTESTBTC:TESTUSD", amount="1", type="EXCHANGE MARKET", side="buy"
    )

    # Act
    resp = await place_order_endpoint(req, True)

    # Assert
    assert resp.success is False
    assert "simulated" in (resp.error or "")


@pytest.mark.asyncio
async def test_place_order_success_counts(monkeypatch):
    # Arrange: mock place_order to return Bitfinex-like list response
    from rest import auth as rest_auth

    async def _fake_place_order(_):
        return [
            1754685881,
            "on-req",
            None,
            None,
            [
                [
                    214173110106,
                    None,
                    0,
                    "tTESTBTC:TESTUSD",
                    0,
                    0,
                    1,
                    1,
                    "EXCHANGE MARKET",
                    None,
                    None,
                    None,
                    0,
                    "ACTIVE",
                    None,
                    None,
                    100,
                    0,
                    0,
                    0,
                    None,
                    None,
                    None,
                    0,
                    0,
                    None,
                    None,
                    None,
                    "API>BFX",
                    None,
                    None,
                    {"source": "api"},
                ]
            ],
            None,
            "SUCCESS",
            "Submitting 1 orders.",
        ]

    monkeypatch.setattr(rest_auth, "place_order", _fake_place_order)
    metrics_store.clear()

    req = OrderRequest(
        symbol="tTESTBTC:TESTUSD",
        amount="1",
        type="EXCHANGE MARKET",
        side="buy",
        post_only=True,  # ska ignoreras för MARKET
        reduce_only=True,  # ska skickas vidare
    )

    # Act
    resp = await place_order_endpoint(req, True)

    # Assert
    assert resp.success is True
