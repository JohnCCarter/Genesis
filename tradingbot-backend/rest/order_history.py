"""
Order History Service - TradingBot Backend

Denna modul hanterar historiska orderdata från Bitfinex API.
Inkluderar funktioner för att hämta orderhistorik, trades och ledger.
"""

import json
import httpx
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from datetime import datetime

from config.settings import Settings
from rest.auth import build_auth_headers
from utils.logger import get_logger

logger = get_logger(__name__)

class OrderHistoryItem(BaseModel):
    """Modell för en historisk order."""
    id: int
    symbol: str
    status: str  # "EXECUTED", "CANCELED", etc.
    type: str
    amount: float
    original_amount: float
    price: float
    avg_execution_price: Optional[float] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_cancelled: bool = False
    is_hidden: bool = False
    
    @classmethod
    def from_bitfinex_data(cls, data: List) -> 'OrderHistoryItem':
        """Skapar en OrderHistoryItem från Bitfinex API-data."""
        if len(data) < 12:
            raise ValueError(f"Ogiltig orderhistorikdata: {data}")
        
        return cls(
            id=int(data[0]),
            symbol=data[1],
            status=data[2],
            type=data[3],
            amount=float(data[4]),
            original_amount=float(data[5]),
            price=float(data[6]),
            avg_execution_price=float(data[7]) if data[7] is not None else None,
            created_at=datetime.fromtimestamp(data[8] / 1000) if data[8] else datetime.now(),
            updated_at=datetime.fromtimestamp(data[9] / 1000) if data[9] else None,
            is_cancelled=bool(data[10]),
            is_hidden=bool(data[11])
        )

class TradeItem(BaseModel):
    """Modell för en trade."""
    id: int
    symbol: str
    order_id: int
    execution_id: Optional[str] = None
    amount: float
    price: float
    fee: float
    fee_currency: str
    executed_at: datetime
    
    @classmethod
    def from_bitfinex_data(cls, data: List) -> 'TradeItem':
        """Skapar en TradeItem från Bitfinex API-data."""
        if len(data) < 9:
            raise ValueError(f"Ogiltig tradedata: {data}")
        
        return cls(
            id=int(data[0]),
            symbol=data[1],
            order_id=int(data[2]),
            execution_id=data[3] if data[3] else None,
            amount=float(data[4]),
            price=float(data[5]),
            fee=float(data[6]),
            fee_currency=data[7],
            executed_at=datetime.fromtimestamp(data[8] / 1000) if data[8] else datetime.now()
        )

class LedgerEntry(BaseModel):
    """Modell för en ledger-post."""
    id: int
    currency: str
    amount: float
    balance: float
    description: str
    created_at: datetime
    wallet_type: str
    
    @classmethod
    def from_bitfinex_data(cls, data: List) -> 'LedgerEntry':
        """Skapar en LedgerEntry från Bitfinex API-data."""
        if len(data) < 7:
            raise ValueError(f"Ogiltig ledgerdata: {data}")
        
        return cls(
            id=int(data[0]),
            currency=data[1],
            amount=float(data[2]),
            balance=float(data[3]),
            description=data[4],
            created_at=datetime.fromtimestamp(data[5] / 1000) if data[5] else datetime.now(),
            wallet_type=data[6]
        )

class OrderHistoryService:
    """Service för att hämta och hantera orderhistorik från Bitfinex."""
    
    def __init__(self):
        self.settings = Settings()
        self.base_url = self.settings.BITFINEX_API_URL
    
    async def get_orders_history(self, limit: int = 25, start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[OrderHistoryItem]:
        """
        Hämtar orderhistorik från Bitfinex.
        
        Args:
            limit: Maximalt antal ordrar att hämta
            start_time: Starttid i millisekunder sedan epoch
            end_time: Sluttid i millisekunder sedan epoch
            
        Returns:
            Lista med OrderHistoryItem-objekt
        """
        try:
            endpoint = "auth/r/orders/hist"
            
            # Skapa payload med filter
            payload = {}
            if limit:
                payload["limit"] = limit
            if start_time:
                payload["start"] = start_time
            if end_time:
                payload["end"] = end_time
                
            headers = build_auth_headers(endpoint, payload)
            
            async with httpx.AsyncClient() as client:
                logger.info(f"🌐 REST API: Hämtar orderhistorik från {self.base_url}/{endpoint}")
                response = await client.post(
                    f"{self.base_url}/{endpoint}",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                orders_data = response.json()
                logger.info(f"✅ REST API: Hämtade {len(orders_data)} historiska ordrar")
                
                orders = [OrderHistoryItem.from_bitfinex_data(order) for order in orders_data]
                return orders
                
        except Exception as e:
            logger.error(f"Fel vid hämtning av orderhistorik: {e}")
            raise
    
    async def get_order_trades(self, order_id: int) -> List[TradeItem]:
        """
        Hämtar alla trades för en specifik order.
        
        Args:
            order_id: ID för ordern
            
        Returns:
            Lista med TradeItem-objekt
        """
        try:
            endpoint = f"auth/r/order/{order_id}/trades"
            headers = build_auth_headers(endpoint)
            
            async with httpx.AsyncClient() as client:
                logger.info(f"🌐 REST API: Hämtar trades för order {order_id}")
                response = await client.post(
                    f"{self.base_url}/{endpoint}",
                    headers=headers
                )
                response.raise_for_status()
                
                trades_data = response.json()
                logger.info(f"✅ REST API: Hämtade {len(trades_data)} trades för order {order_id}")
                
                trades = [TradeItem.from_bitfinex_data(trade) for trade in trades_data]
                return trades
                
        except Exception as e:
            logger.error(f"Fel vid hämtning av trades för order {order_id}: {e}")
            raise
    
    async def get_trades_history(self, symbol: Optional[str] = None, limit: int = 25) -> List[TradeItem]:
        """
        Hämtar handelshistorik från Bitfinex.
        
        Args:
            symbol: Handelssymbol (t.ex. "tBTCUSD") eller None för alla symboler
            limit: Maximalt antal trades att hämta
            
        Returns:
            Lista med TradeItem-objekt
        """
        try:
            endpoint = "auth/r/trades/hist"
            if symbol:
                endpoint = f"auth/r/trades/{symbol}/hist"
                
            payload = {"limit": limit} if limit else {}
            headers = build_auth_headers(endpoint, payload)
            
            async with httpx.AsyncClient() as client:
                logger.info(f"🌐 REST API: Hämtar handelshistorik från {self.base_url}/{endpoint}")
                response = await client.post(
                    f"{self.base_url}/{endpoint}",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                trades_data = response.json()
                logger.info(f"✅ REST API: Hämtade {len(trades_data)} historiska trades")
                
                trades = [TradeItem.from_bitfinex_data(trade) for trade in trades_data]
                return trades
                
        except Exception as e:
            logger.error(f"Fel vid hämtning av handelshistorik: {e}")
            raise
    
    async def get_ledgers(self, currency: Optional[str] = None, limit: int = 25) -> List[LedgerEntry]:
        """
        Hämtar ledger-poster från Bitfinex.
        
        Args:
            currency: Valutakod (t.ex. "BTC", "USD") eller None för alla valutor
            limit: Maximalt antal poster att hämta
            
        Returns:
            Lista med LedgerEntry-objekt
        """
        try:
            endpoint = "auth/r/ledgers/hist"
            if currency:
                endpoint = f"auth/r/ledgers/{currency}/hist"
                
            payload = {"limit": limit} if limit else {}
            headers = build_auth_headers(endpoint, payload)
            
            async with httpx.AsyncClient() as client:
                logger.info(f"🌐 REST API: Hämtar ledger från {self.base_url}/{endpoint}")
                response = await client.post(
                    f"{self.base_url}/{endpoint}",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                ledgers_data = response.json()
                logger.info(f"✅ REST API: Hämtade {len(ledgers_data)} ledger-poster")
                
                ledgers = [LedgerEntry.from_bitfinex_data(ledger) for ledger in ledgers_data]
                return ledgers
                
        except Exception as e:
            logger.error(f"Fel vid hämtning av ledger: {e}")
            raise

# Skapa en global instans av OrderHistoryService
order_history_service = OrderHistoryService()

# Exportera funktioner för enkel användning
async def get_orders_history(limit: int = 25, start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[OrderHistoryItem]:
    return await order_history_service.get_orders_history(limit, start_time, end_time)

async def get_order_trades(order_id: int) -> List[TradeItem]:
    return await order_history_service.get_order_trades(order_id)

async def get_trades_history(symbol: Optional[str] = None, limit: int = 25) -> List[TradeItem]:
    return await order_history_service.get_trades_history(symbol, limit)

async def get_ledgers(currency: Optional[str] = None, limit: int = 25) -> List[LedgerEntry]:
    return await order_history_service.get_ledgers(currency, limit)

# Exempel på användning
if __name__ == "__main__":
    import asyncio
    
    async def main():
        try:
            # Hämta senaste 10 ordrar
            orders = await get_orders_history(10)
            print(f"Senaste {len(orders)} ordrar:")
            for order in orders:
                print(f"  {order.id}: {order.symbol} {order.type} {order.amount} @ {order.price} ({order.status})")
            
            # Om det finns ordrar, hämta trades för den första
            if orders:
                trades = await get_order_trades(orders[0].id)
                print(f"\nTrades för order {orders[0].id}:")
                for trade in trades:
                    print(f"  {trade.id}: {trade.amount} @ {trade.price} (Fee: {trade.fee} {trade.fee_currency})")
            
            # Hämta senaste 5 ledger-poster för USD
            ledgers = await get_ledgers("USD", 5)
            print(f"\nSenaste {len(ledgers)} ledger-poster för USD:")
            for ledger in ledgers:
                print(f"  {ledger.id}: {ledger.amount} {ledger.currency} - {ledger.description}")
                
        except Exception as e:
            print(f"Fel: {e}")
    
    asyncio.run(main())
