import json
from types import SimpleNamespace

import httpx
import pytest

from services.exchange_client import ExchangeClient
from config.settings import Settings


class _Resp:
    def __init__(self, status_code: int, body):
        self.status_code = status_code
        self._body = body
        self.headers = {}

    def json(self):
        return self._body

    @property
    def text(self):
        try:
            return json.dumps(self._body)
        except Exception:
            return str(self._body)


class _ReqMock:
    def __init__(self):
        self.calls = 0

    async def __call__(self, url, content, headers):  # noqa: D401
        self.calls += 1
        # Första svaret simulerar nonce-fel (500 med "nonce")
        if self.calls == 1:
            return _Resp(500, [None, None, "nonce: small"])
        # Andra svaret OK
        return _Resp(200, {"ok": True})


@pytest.mark.asyncio
async def test_exchange_client_retries_on_nonce_error(monkeypatch):
    s = Settings()
    client = ExchangeClient(settings=s)

    class _Client:
        def __init__(self, timeout):  # noqa: D401
            self.timeout = timeout
            self.post = _ReqMock()
            self.get = _ReqMock()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    # Patch httpx.AsyncClient to our async context manager stub
    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    resp = await client.signed_request(method="post", endpoint="auth/r/ledgers/hist", body={}, timeout=5.0)
    assert resp.status_code == 200
