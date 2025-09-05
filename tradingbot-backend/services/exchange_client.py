"""
Exchange Client - centraliserar signering/nonce för Bitfinex REST och WS.

Syfte:
- En enda källa för signering (REST v1/v2) och WS-auth payload
- Undvik duplicerad logik mellan `rest.auth` och `ws.auth`
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any

from config.settings import Settings
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ExchangeClient:
    settings: Settings

    def build_rest_headers(
        self,
        *,
        endpoint: str,
        payload: dict | None = None,
        v1: bool = False,
        payload_str: str | None = None,
    ) -> dict:
        """Bygg signerade headers för Bitfinex REST (v1/v2).

        endpoint: ex "auth/r/orders"
        payload: body-dict (serialiseras deterministiskt om payload_str saknas)
        v1: True => v1-signering, annars v2
        payload_str: exakt JSON-sträng som skickas (prioriteras om angiven)
        """
        api_key = self.settings.BITFINEX_API_KEY
        api_secret = self.settings.BITFINEX_API_SECRET
        # Nonce per API-nyckel för strikt ökande nonces
        import utils.nonce_manager

        nonce = utils.nonce_manager.get_nonce(api_key)  # mikrosekunder

        api_version = "v1" if v1 else "v2"
        if payload_str is None and payload is not None:
            payload_str = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

        message = f"/api/{api_version}/{endpoint}{nonce!s}"
        if payload_str is not None:
            message += payload_str

        signature = hmac.new(key=api_secret.encode(), msg=message.encode(), digestmod=hashlib.sha384).hexdigest()

        return {
            "bfx-apikey": api_key,
            "bfx-nonce": str(nonce),
            "bfx-signature": signature,
            "Content-Type": "application/json",
        }

    def build_ws_auth_payload(self) -> str:
        """Skapar WS v2 auth-meddelande (JSON-sträng)."""
        # WebSocket använder millisekunder, men vår nonce_manager levererar mikrosekunder -> konvertera
        import utils.nonce_manager

        ws_api_key = self.settings.BITFINEX_WS_API_KEY or self.settings.BITFINEX_API_KEY
        ws_api_secret = self.settings.BITFINEX_WS_API_SECRET or self.settings.BITFINEX_API_SECRET

        ws_nonce_us = utils.nonce_manager.get_nonce(ws_api_key)
        nonce_ms = str(int(int(ws_nonce_us) / 1000))

        payload = f"AUTH{nonce_ms}"
        signature = hmac.new(
            key=(ws_api_secret or "").encode(),
            msg=payload.encode(),
            digestmod=hashlib.sha384,
        ).hexdigest()

        message = {
            "event": "auth",
            "apiKey": ws_api_key,
            "authNonce": nonce_ms,
            "authPayload": payload,
            "authSig": signature,
        }
        return json.dumps(message)


_client_singleton: ExchangeClient | None = None


def get_exchange_client() -> ExchangeClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = ExchangeClient(settings=Settings())
    return _client_singleton
