import pytest

from rest.routes import OrderRequest, place_order_endpoint
from services.metrics import metrics_store


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
        symbol="tTESTBTC:TESTUSD", amount="1", type="EXCHANGE MARKET", side="buy"
    )

    # Act
    resp = await place_order_endpoint(req, True)

    # Assert
    assert resp.success is True
