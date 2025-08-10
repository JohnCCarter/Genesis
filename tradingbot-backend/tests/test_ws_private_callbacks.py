import asyncio

import pytest


@pytest.mark.asyncio
async def test_ws_private_callbacks_fire(monkeypatch):
    # Importera WS-manager och injicera fejk callbacks
    from services.bitfinex_websocket import BitfinexWebSocketService

    svc = BitfinexWebSocketService()

    events = {"os": 0, "on": 0, "ou": 0, "oc": 0, "te": 0, "tu": 0}

    async def mk_cb(code):
        async def _cb(msg):
            events[code] += 1

        return _cb

    # Registrera callbacks
    for code in list(events.keys()):
        svc.register_handler(code, await mk_cb(code))

    # Skicka in privata meddelanden via intern hanterare
    async def feed(msg):
        await svc._handle_channel_message(msg)  # type: ignore[attr-defined]

    # Format: [0, 'EVENT_CODE', payload]
    await feed([0, "os", []])
    await feed([0, "on", [1]])
    await feed([0, "ou", [1]])
    await feed([0, "oc", [1]])
    await feed([0, "te", [0, "tBTCUSD", 0, 42, 0.1, 50000]])
    await feed([0, "tu", [0, "tBTCUSD", 0, 42, 0.1, 50000]])

    assert events["os"] == 1
    assert events["on"] == 1
    assert events["ou"] == 1
    assert events["oc"] == 1
    assert events["te"] == 1
    assert events["tu"] == 1
