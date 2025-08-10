import pytest


class FakeWSService:
    def __init__(self):
        self.handlers = {}
        self.enable_called = False
        self.enable_timeout = None

    def register_handler(self, code, cb):
        self.handlers[code] = cb

    async def enable_dead_man_switch(self, timeout_ms: int = 60000):
        self.enable_called = True
        self.enable_timeout = timeout_ms


@pytest.mark.asyncio
async def test_registers_private_handlers():
    from ws.manager import WebSocketManager

    fake = FakeWSService()
    mgr = WebSocketManager(fake)
    # Registrera privata strömmar utan att starta externa anslutningar
    mgr._register_private_streams()

    for code in ("os", "on", "ou", "oc", "te", "tu", "auth"):
        assert code in fake.handlers, f"saknar handler för {code}"


@pytest.mark.asyncio
async def test_dms_enabled_on_auth():
    from ws.manager import WebSocketManager

    fake = FakeWSService()
    mgr = WebSocketManager(fake)
    mgr._register_private_streams()

    # Simulera auth-event
    assert "auth" in fake.handlers
    await fake.handlers["auth"]({"event": "auth", "status": "OK"})

    assert fake.enable_called is True
    assert fake.enable_timeout == 60000
