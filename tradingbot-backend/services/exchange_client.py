"""
# AI Change: Använd get_async_client() istället för module-level klient (Agent: Cursor, Date: 2025-09-16)
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

import httpx
from services.http import get_async_client

from config.settings import settings
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

        signature = hmac.new(
            key=api_secret.encode(), msg=message.encode(), digestmod=hashlib.sha384
        ).hexdigest()

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
        ws_api_secret = (
            self.settings.BITFINEX_WS_API_SECRET or self.settings.BITFINEX_API_SECRET
        )

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

    async def signed_request(
        self,
        *,
        method: str,
        endpoint: str,
        body: dict[str, Any] | None = None,
        timeout: float | None = None,
        v1: bool = False,
    ) -> httpx.Response:
        """Centraliserad signerad REST-anropare med nonce‑bump och enkel retry.

        - Signerar exakt JSON som skickas
        - Respekterar rate limiter/circuit breaker via anroparen (call site)
        - Hanterar nonce‑fel: bump och engångs‑retry
        """
        body = body or {}
        body_json = json.dumps(body, separators=(",", ":"), ensure_ascii=False)

        headers = self.build_rest_headers(
            endpoint=endpoint, payload_str=body_json, v1=v1
        )
        base_url = (
            getattr(self.settings, "BITFINEX_AUTH_API_URL", None)
            or self.settings.BITFINEX_API_URL
        )
        if v1:
            base_url = "https://api.bitfinex.com/v1"

        # Notera: timeout hanteras av delad klient; hämta per-event-loop klient
        client = get_async_client()
        req = getattr(client, method.lower())
        response = await req(
            f"{base_url}/{endpoint}",
            content=body_json.encode("utf-8"),
            headers=headers,
        )

        # Nonce‑fel (Bitfinex returnerar 500 med feltextlista där index 2 brukar innehålla meddelandet)
        if response.status_code == 500:
            try:
                data = response.json()
                if (
                    isinstance(data, list)
                    and len(data) >= 3
                    and "nonce" in str(data[2]).lower()
                ):
                    from utils.nonce_manager import bump_nonce

                    api_key = self.settings.BITFINEX_API_KEY or "default_key"
                    bump_nonce(api_key)
                    # Bygg om headers och försök en gång till
                    headers = self.build_rest_headers(
                        endpoint=endpoint, payload_str=body_json
                    )
                    response = await req(
                        f"{base_url}/{endpoint}",
                        content=body_json.encode("utf-8"),
                        headers=headers,
                    )
            except Exception:
                pass

        return response


_client_singleton: ExchangeClient | None = None


def get_exchange_client() -> ExchangeClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = ExchangeClient(settings=settings)
    return _client_singleton
