"""
Positions History Service - TradingBot Backend

Denna modul hanterar historiska positioner från Bitfinex API.
Inkluderar funktioner för att hämta positionshistorik och hantera positionsdata.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from config.settings import Settings
from pydantic import BaseModel
from rest.auth import build_auth_headers
from utils.logger import get_logger

logger = get_logger(__name__)


class PositionHistory(BaseModel):
    """Modell för en historisk position."""

    id: Optional[int] = None
    symbol: str
    status: str  # "ACTIVE", "CLOSED"
    amount: float
    base_price: float
    funding: float = 0.0
    funding_type: int = 0  # 0 för daily, 1 för term
    profit_loss: Optional[float] = None
    profit_loss_percentage: Optional[float] = None
    liquidation_price: Optional[float] = None
    created_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    @property
    def is_long(self) -> bool:
        """Returnerar True om positionen är long."""
        return self.amount > 0

    @property
    def is_short(self) -> bool:
        """Returnerar True om positionen är short."""
        return self.amount < 0

    @classmethod
    def from_bitfinex_data(cls, data: List) -> "PositionHistory":
        """Skapar en PositionHistory från Bitfinex API-data."""
        if len(data) < 6:
            raise ValueError(f"Ogiltig positionsdata: {data}")

        # Skapa en grundläggande position
        position = cls(
            symbol=data[0],
            status=data[1],
            amount=float(data[2]) if data[2] is not None else 0.0,
            base_price=float(data[3]) if data[3] is not None else 0.0,
            funding=float(data[4]) if len(data) > 4 and data[4] is not None else 0.0,
            funding_type=int(data[5]) if len(data) > 5 and data[5] is not None else 0,
        )

        # Lägg till ytterligare fält om de finns
        if len(data) > 6 and data[6] is not None:
            position.profit_loss = float(data[6])
        if len(data) > 7 and data[7] is not None:
            position.profit_loss_percentage = float(data[7])
        if len(data) > 8 and data[8] is not None:
            position.liquidation_price = float(data[8])
        if len(data) > 9 and data[9] is not None:
            position.created_at = datetime.fromtimestamp(data[9] / 1000)
        if len(data) > 10 and data[10] is not None:
            position.closed_at = datetime.fromtimestamp(data[10] / 1000)
        if len(data) > 11 and data[11] is not None:
            position.id = int(data[11])

        return position


class PositionsHistoryService:
    """Service för att hämta och hantera positionshistorik från Bitfinex."""

    def __init__(self):
        self.settings = Settings()
        self.base_url = (
            getattr(self.settings, "BITFINEX_AUTH_API_URL", None)
            or self.settings.BITFINEX_API_URL
        )

    async def get_positions_history(
        self, start: Optional[int] = None, end: Optional[int] = None, limit: int = 50
    ) -> List[PositionHistory]:
        """
        Hämtar positionshistorik från Bitfinex.

        Args:
            start: Starttid i millisekunder sedan epoch (valfritt)
            end: Sluttid i millisekunder sedan epoch (valfritt)
            limit: Maximalt antal positioner att hämta (standard: 50)

        Returns:
            Lista med PositionHistory-objekt
        """
        try:
            endpoint = "auth/r/positions/hist"

            # Skapa payload med filter
            payload = {}
            if start:
                payload["start"] = start
            if end:
                payload["end"] = end
            if limit:
                payload["limit"] = limit

            headers = build_auth_headers(endpoint, payload)

            async with httpx.AsyncClient() as client:
                logger.info(
                    f"🌐 REST API: Hämtar positionshistorik från {self.base_url}/{endpoint}"
                )
                response = await client.post(
                    f"{self.base_url}/{endpoint}", headers=headers, json=payload
                )
                response.raise_for_status()

                positions_data = response.json()
                logger.info(
                    f"✅ REST API: Hämtade {len(positions_data)} historiska positioner"
                )

                positions = [
                    PositionHistory.from_bitfinex_data(position)
                    for position in positions_data
                ]
                return positions

        except Exception as e:
            logger.error(f"Fel vid hämtning av positionshistorik: {e}")
            raise

    async def get_positions_snapshot(self) -> List[PositionHistory]:
        """
        Hämtar en ögonblicksbild av positioner från Bitfinex.

        Returns:
            Lista med PositionHistory-objekt
        """
        try:
            endpoint = "auth/r/positions/snap"
            headers = build_auth_headers(endpoint)

            async with httpx.AsyncClient() as client:
                logger.info(
                    f"🌐 REST API: Hämtar positionsögonblicksbild från {self.base_url}/{endpoint}"
                )
                response = await client.post(
                    f"{self.base_url}/{endpoint}", headers=headers
                )
                response.raise_for_status()

                positions_data = response.json()
                logger.info(
                    f"✅ REST API: Hämtade {len(positions_data)} positioner i ögonblicksbilden"
                )

                positions = [
                    PositionHistory.from_bitfinex_data(position)
                    for position in positions_data
                ]
                return positions

        except Exception as e:
            logger.error(f"Fel vid hämtning av positionsögonblicksbild: {e}")
            raise

    async def get_positions_audit(
        self,
        symbol: str,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: int = 50,
    ) -> List[PositionHistory]:
        """
        Hämtar positionsrevision från Bitfinex.

        Args:
            symbol: Handelssymbol (t.ex. "tBTCUSD")
            start: Starttid i millisekunder sedan epoch (valfritt)
            end: Sluttid i millisekunder sedan epoch (valfritt)
            limit: Maximalt antal positioner att hämta (standard: 50)

        Returns:
            Lista med PositionHistory-objekt
        """
        try:
            endpoint = "auth/r/positions/audit"

            # Skapa payload med filter
            payload = {"id": symbol}
            if start:
                payload["start"] = start
            if end:
                payload["end"] = end
            if limit:
                payload["limit"] = limit

            headers = build_auth_headers(endpoint, payload)

            async with httpx.AsyncClient() as client:
                logger.info(
                    f"🌐 REST API: Hämtar positionsrevision för {symbol} från {self.base_url}/{endpoint}"
                )
                response = await client.post(
                    f"{self.base_url}/{endpoint}", headers=headers, json=payload
                )
                response.raise_for_status()

                positions_data = response.json()
                logger.info(
                    f"✅ REST API: Hämtade {len(positions_data)} positionsrevisioner"
                )

                positions = [
                    PositionHistory.from_bitfinex_data(position)
                    for position in positions_data
                ]
                return positions

        except Exception as e:
            logger.error(f"Fel vid hämtning av positionsrevision: {e}")
            raise

    async def claim_position(self, position_id: str) -> Dict[str, Any]:
        """
        Gör anspråk på en position.

        Args:
            position_id: ID för positionen som ska göras anspråk på

        Returns:
            Svar från API:et
        """
        try:
            endpoint = "auth/w/position/claim"
            payload = {"id": position_id}
            headers = build_auth_headers(endpoint, payload)

            async with httpx.AsyncClient() as client:
                logger.info(f"🌐 REST API: Gör anspråk på position {position_id}")
                response = await client.post(
                    f"{self.base_url}/{endpoint}", headers=headers, json=payload
                )
                response.raise_for_status()

                result = response.json()
                logger.info(
                    f"✅ REST API: Anspråk på position {position_id} framgångsrikt"
                )

                return result

        except Exception as e:
            logger.error(f"Fel vid anspråk på position: {e}")
            raise

    async def update_position_funding_type(
        self, symbol: str, funding_type: int
    ) -> Dict[str, Any]:
        """
        Uppdaterar finansieringstypen för en position.

        Args:
            symbol: Handelssymbol (t.ex. "tBTCUSD")
            funding_type: Finansieringstyp (0 för daily, 1 för term)

        Returns:
            Svar från API:et
        """
        try:
            endpoint = "auth/w/position/funding/type"
            payload = {"id": symbol, "type": funding_type}
            headers = build_auth_headers(endpoint, payload)

            async with httpx.AsyncClient() as client:
                logger.info(
                    f"🌐 REST API: Uppdaterar finansieringstyp för position {symbol} till {funding_type}"
                )
                response = await client.post(
                    f"{self.base_url}/{endpoint}", headers=headers, json=payload
                )
                response.raise_for_status()

                result = response.json()
                logger.info(
                    f"✅ REST API: Finansieringstyp för position {symbol} uppdaterad framgångsrikt"
                )

                return result

        except Exception as e:
            logger.error(f"Fel vid uppdatering av finansieringstyp: {e}")
            raise


# Skapa en global instans av PositionsHistoryService
positions_history_service = PositionsHistoryService()


# Exportera funktioner för enkel användning
async def get_positions_history(
    start: Optional[int] = None, end: Optional[int] = None, limit: int = 50
) -> List[PositionHistory]:
    return await positions_history_service.get_positions_history(start, end, limit)


async def get_positions_snapshot() -> List[PositionHistory]:
    return await positions_history_service.get_positions_snapshot()


async def get_positions_audit(
    symbol: str, start: Optional[int] = None, end: Optional[int] = None, limit: int = 50
) -> List[PositionHistory]:
    return await positions_history_service.get_positions_audit(
        symbol, start, end, limit
    )


async def claim_position(position_id: str) -> Dict[str, Any]:
    return await positions_history_service.claim_position(position_id)


async def update_position_funding_type(
    symbol: str, funding_type: int
) -> Dict[str, Any]:
    return await positions_history_service.update_position_funding_type(
        symbol, funding_type
    )
