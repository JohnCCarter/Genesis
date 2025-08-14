"""
Positions Service - TradingBot Backend

Denna modul hanterar positionsinformation från Bitfinex API.
Inkluderar funktioner för att hämta aktiva positioner och hantera positioner.
"""

from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel

from config.settings import Settings
from rest.auth import build_auth_headers
from utils.logger import get_logger

logger = get_logger(__name__)


class Position(BaseModel):
    """Modell för en position."""

    symbol: str
    status: str  # "ACTIVE", "CLOSED"
    amount: float
    base_price: float
    funding: float = 0.0
    funding_type: int = 0  # 0 för daily, 1 för term
    profit_loss: float | None = None
    profit_loss_percentage: float | None = None
    liquidation_price: float | None = None

    @property
    def is_long(self) -> bool:
        """Returnerar True om positionen är long."""
        return self.amount > 0

    @property
    def is_short(self) -> bool:
        """Returnerar True om positionen är short."""
        return self.amount < 0

    @classmethod
    def from_bitfinex_data(cls, data: list) -> "Position":
        """Skapar en Position från Bitfinex API-data."""
        if len(data) < 6:
            raise ValueError(f"Ogiltig positionsdata: {data}")

        return cls(
            symbol=data[0],
            status=data[1],
            amount=float(data[2]),
            base_price=float(data[3]),
            funding=float(data[4]) if len(data) > 4 else 0.0,
            funding_type=int(data[5]) if len(data) > 5 else 0,
            profit_loss=float(data[6]) if len(data) > 6 else None,
            profit_loss_percentage=float(data[7]) if len(data) > 7 else None,
            liquidation_price=float(data[8]) if len(data) > 8 else None,
        )


class PositionsService:
    """Service för att hämta och hantera positionsinformation från Bitfinex."""

    def __init__(self):
        self.settings = Settings()
        self.base_url = (
            getattr(self.settings, "BITFINEX_AUTH_API_URL", None) or self.settings.BITFINEX_API_URL
        )

    async def get_positions(self) -> list[Position]:
        """
        Hämtar alla aktiva positioner från Bitfinex.

        Returns:
            Lista med Position-objekt
        """
        try:
            endpoint = "auth/r/positions"
            headers = build_auth_headers(endpoint)

            async with httpx.AsyncClient() as client:
                logger.info(f"🌐 REST API: Hämtar positioner från {self.base_url}/{endpoint}")
                try:
                    response = await client.post(f"{self.base_url}/{endpoint}", headers=headers)
                    response.raise_for_status()
                    positions_data = response.json()
                except httpx.HTTPStatusError as e:
                    # Vid temporära serverfel – returnera tom lista istället för att krascha flöden
                    if e.response.status_code in (500, 502, 503, 504):
                        logger.error(
                            f"Serverfel vid positionshämtning ({e.response.status_code}), returnerar tom lista"
                        )
                        return []
                    raise

                logger.info(f"✅ REST API: Hämtade {len(positions_data)} positioner")
                positions = [Position.from_bitfinex_data(position) for position in positions_data]
                return positions

        except Exception as e:
            logger.error(f"Fel vid hämtning av positioner: {e}")
            raise

    async def get_position_by_symbol(self, symbol: str) -> Position | None:
        """
        Hämtar en specifik position baserat på symbol.

        Args:
            symbol: Handelssymbol (t.ex. "tBTCUSD")

        Returns:
            Position-objekt eller None om positionen inte hittas
        """
        positions = await self.get_positions()

        for position in positions:
            if position.symbol.lower() == symbol.lower():
                return position

        return None

    async def get_long_positions(self) -> list[Position]:
        """
        Hämtar alla long-positioner.

        Returns:
            Lista med Position-objekt för long-positioner
        """
        positions = await self.get_positions()
        return [position for position in positions if position.is_long]

    async def get_short_positions(self) -> list[Position]:
        """
        Hämtar alla short-positioner.

        Returns:
            Lista med Position-objekt för short-positioner
        """
        positions = await self.get_positions()
        return [position for position in positions if position.is_short]

    async def close_position(self, symbol: str) -> dict[str, Any]:
        """
        Stänger en margin-position genom att skicka en reduce-only market-order i motsatt riktning.
        """
        try:
            # Hämta aktuell position
            position = await self.get_position_by_symbol(symbol)
            if not position or not position.amount:
                raise ValueError(f"Ingen aktiv position med amount hittad för symbol: {symbol}")

            # Bestäm motsatt amount
            amount = float(position.amount)
            close_amount = -amount  # motsatt riktning

            # Bygg order (MARKET, margin)
            order_endpoint = "auth/w/order/submit"
            order_payload = {
                "type": "MARKET",  # margin
                "symbol": symbol,
                "amount": str(close_amount),
                "reduce_only": True,
            }
            headers = build_auth_headers(order_endpoint, order_payload)

            timeout = Settings().ORDER_HTTP_TIMEOUT
            retries = max(int(Settings().ORDER_MAX_RETRIES), 0)
            backoff_base = max(int(Settings().ORDER_BACKOFF_BASE_MS), 0) / 1000.0
            backoff_max = max(int(Settings().ORDER_BACKOFF_MAX_MS), 0) / 1000.0
            last_exc = None
            result = None
            for attempt in range(retries + 1):
                try:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        logger.info(
                            f"🌐 REST API: Stänger position via reduce-only MARKET för {symbol} ({close_amount})"
                        )
                        response = await client.post(
                            f"{self.base_url}/{order_endpoint}",
                            headers=headers,
                            json=order_payload,
                        )
                        if response.status_code in (429, 500, 502, 503, 504):
                            raise httpx.HTTPStatusError(
                                "server busy", request=None, response=response
                            )
                        response.raise_for_status()
                        result = response.json()
                        break
                except Exception as e:
                    last_exc = e
                    if attempt < retries:
                        import asyncio
                        import random

                        delay = min(backoff_max, backoff_base * (2**attempt)) + random.uniform(
                            0, 0.1
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise
                logger.info(f"✅ REST API: Reduce-only order skickad för {symbol}")
                return {
                    "success": True,
                    "message": "Reduce-only submit skickad",
                    "data": result,
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"Fel vid stängning av position (HTTP): {e}")
            raise
        except Exception as e:
            logger.error(f"Fel vid stängning av position: {e}")
            raise


# Skapa en global instans av PositionsService
positions_service = PositionsService()


# Exportera funktioner för enkel användning
async def get_positions() -> list[Position]:
    return await positions_service.get_positions()


async def get_position_by_symbol(symbol: str) -> Position | None:
    return await positions_service.get_position_by_symbol(symbol)


async def get_long_positions() -> list[Position]:
    return await positions_service.get_long_positions()


async def get_short_positions() -> list[Position]:
    return await positions_service.get_short_positions()


async def close_position(symbol: str) -> dict[str, Any]:
    return await positions_service.close_position(symbol)
