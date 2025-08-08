"""
Positions Service - TradingBot Backend

Denna modul hanterar positionsinformation från Bitfinex API.
Inkluderar funktioner för att hämta aktiva positioner och hantera positioner.
"""

import json
import httpx
from typing import Dict, List, Optional, Any
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
    profit_loss: Optional[float] = None
    profit_loss_percentage: Optional[float] = None
    liquidation_price: Optional[float] = None
    
    @property
    def is_long(self) -> bool:
        """Returnerar True om positionen är long."""
        return self.amount > 0
    
    @property
    def is_short(self) -> bool:
        """Returnerar True om positionen är short."""
        return self.amount < 0
    
    @classmethod
    def from_bitfinex_data(cls, data: List) -> 'Position':
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
            liquidation_price=float(data[8]) if len(data) > 8 else None
        )

class PositionsService:
    """Service för att hämta och hantera positionsinformation från Bitfinex."""
    
    def __init__(self):
        self.settings = Settings()
        self.base_url = self.settings.BITFINEX_API_URL
    
    async def get_positions(self) -> List[Position]:
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
                response = await client.post(
                    f"{self.base_url}/{endpoint}",
                    headers=headers
                )
                response.raise_for_status()
                
                positions_data = response.json()
                logger.info(f"✅ REST API: Hämtade {len(positions_data)} positioner")
                
                positions = [Position.from_bitfinex_data(position) for position in positions_data]
                return positions
                
        except Exception as e:
            logger.error(f"Fel vid hämtning av positioner: {e}")
            raise
    
    async def get_position_by_symbol(self, symbol: str) -> Optional[Position]:
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
    
    async def get_long_positions(self) -> List[Position]:
        """
        Hämtar alla long-positioner.
        
        Returns:
            Lista med Position-objekt för long-positioner
        """
        positions = await self.get_positions()
        return [position for position in positions if position.is_long]
    
    async def get_short_positions(self) -> List[Position]:
        """
        Hämtar alla short-positioner.
        
        Returns:
            Lista med Position-objekt för short-positioner
        """
        positions = await self.get_positions()
        return [position for position in positions if position.is_short]
    
    async def close_position(self, symbol: str) -> Dict[str, Any]:
        """
        Stänger en position genom att skicka en motsatt order via Bitfinex API.
        
        Args:
            symbol: Handelssymbol för positionen som ska stängas
            
        Returns:
            Svar från API:et
        """
        try:
            # Hämta positionen först för att veta hur mycket vi behöver stänga
            position = await self.get_position_by_symbol(symbol)
            if not position:
                raise ValueError(f"Ingen aktiv position hittad för symbol: {symbol}")
            
            # Använd Bitfinex API för att stänga positionen
            endpoint = "auth/w/position/close"
            payload = {"position_id": symbol}
            headers = build_auth_headers(endpoint, payload)
            
            async with httpx.AsyncClient() as client:
                logger.info(f"🌐 REST API: Stänger position för {symbol}")
                response = await client.post(
                    f"{self.base_url}/{endpoint}",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"✅ REST API: Position för {symbol} stängd framgångsrikt")
                
                return {
                    "success": True,
                    "message": f"Position för {symbol} stängd",
                    "data": result
                }
                
        except Exception as e:
            logger.error(f"Fel vid stängning av position: {e}")
            raise

# Skapa en global instans av PositionsService
positions_service = PositionsService()

# Exportera funktioner för enkel användning
async def get_positions() -> List[Position]:
    return await positions_service.get_positions()

async def get_position_by_symbol(symbol: str) -> Optional[Position]:
    return await positions_service.get_position_by_symbol(symbol)

async def get_long_positions() -> List[Position]:
    return await positions_service.get_long_positions()

async def get_short_positions() -> List[Position]:
    return await positions_service.get_short_positions()

async def close_position(symbol: str) -> Dict[str, Any]:
    return await positions_service.close_position(symbol)
