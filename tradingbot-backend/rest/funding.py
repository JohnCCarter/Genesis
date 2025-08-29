"""
Funding/Transfer/Movements - TradingBot Backend

REST‑autentiserade operationer för att flytta medel mellan wallets
och läsa ut movements (insättningar/uttag/överföringar).
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from utils.logger import get_logger

from config.settings import Settings
from rest.auth import build_auth_headers

logger = get_logger(__name__)


class FundingService:
    def __init__(self) -> None:
        self.settings = Settings()
        self.base_url = getattr(self.settings, "BITFINEX_AUTH_API_URL", None) or self.settings.BITFINEX_API_URL

    async def transfer(
        self,
        from_wallet: str,
        to_wallet: str,
        currency: str,
        amount: str | float,
    ) -> dict[str, Any]:
        """
        Flytta medel mellan wallets. Ex: exchange -> margin.

        Args:
            from_wallet: "exchange" | "margin" | "funding"
            to_wallet: "exchange" | "margin" | "funding"
            currency: "USD", "UST", "BTC", ...
            amount: belopp som str/float
        """
        endpoint = "auth/w/transfer"
        payload = {
            "from": str(from_wallet).lower(),
            "to": str(to_wallet).lower(),
            "currency": str(currency).upper(),
            "amount": str(amount),
        }
        body_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        headers = build_auth_headers(endpoint, payload_str=body_json)
        url = f"{self.base_url}/{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=self.settings.ORDER_HTTP_TIMEOUT) as client:
                logger.info(
                    "🌐 REST API: Transfer %s → %s %s %s",
                    from_wallet,
                    to_wallet,
                    amount,
                    currency,
                )
                resp = await client.post(url, content=body_json.encode("utf-8"), headers=headers)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error("Transfer error: %s", e)
            # Läck inte intern feltext externt
            return {"error": "transfer_failed"}

    async def movements(
        self,
        currency: str | None = None,
        start: int | None = None,
        end: int | None = None,
        limit: int | None = None,
    ) -> list[Any] | dict[str, Any]:
        """
        Hämtar movements (insättningar/uttag/överföringar).

        Args:
            currency: t.ex. "USD"/"BTC" (valfritt)
            start: ms timestamp (valfritt)
            end: ms timestamp (valfritt)
            limit: antal rader (valfritt)
        """
        endpoint = "auth/r/movements"
        payload: dict[str, Any] = {}
        if currency:
            payload["currency"] = str(currency).upper()
        if start is not None:
            payload["start"] = int(start)
        if end is not None:
            payload["end"] = int(end)
        if limit is not None:
            payload["limit"] = int(limit)
        # Bitfinex v2 kräver ofta tom JSON {} även utan filter
        body_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        headers = build_auth_headers(endpoint, payload_str=body_json)
        url = f"{self.base_url}/{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=self.settings.ORDER_HTTP_TIMEOUT) as client:
                logger.info("🌐 REST API: Movements fetch (%s)", currency or "all")
                resp = await client.post(url, content=body_json.encode("utf-8"), headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return data if isinstance(data, list) else (data or [])
        except Exception as e:
            logger.error("Movements error: %s", e)
            # Läck inte intern feltext externt
            return {"error": "movements_failed"}
