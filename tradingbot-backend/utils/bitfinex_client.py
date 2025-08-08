"""
Bitfinex Client Utility - TradingBot Backend

Denna modul demonstrerar hur Bitfinex-autentisering används
för REST och WebSocket-anrop.
"""

import httpx
import asyncio
from typing import Dict, Any, Optional

from rest.auth import build_auth_headers
from ws.auth import build_ws_auth_payload
from utils.logger import get_logger

logger = get_logger(__name__)

class BitfinexClient:
    """Hjälpklass för Bitfinex API-anrop med autentisering."""
    
    def __init__(self):
        self.rest_url = "https://api-pub.bitfinex.com"
        self.ws_url = "wss://api-pub.bitfinex.com/ws/2"
    
    async def get_active_orders(self) -> Dict[str, Any]:
        """
        Hämtar aktiva ordrar med autentiserade headers.
        
        Returns:
            Dict med aktiva ordrar
        """
        endpoint = "auth/r/orders/active"
        headers = build_auth_headers(endpoint)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.rest_url}/v2/{endpoint}",
                headers=headers
            )
            return response.json()
    
    def get_ws_auth_message(self) -> str:
        """
        Skapar autentiseringsmeddelande för WebSocket.
        
        Returns:
            JSON-formaterat auth-meddelande
        """
        return build_ws_auth_payload()

# Exempel på användning
async def example_usage():
    """Demonstrerar hur autentiseringen används."""
    client = BitfinexClient()
    
    # REST API exempel
    try:
        orders = await client.get_active_orders()
        logger.info(f"Hämtade {len(orders)} aktiva ordrar")
    except Exception as e:
        logger.error(f"Fel vid hämtning av ordrar: {e}")
    
    # WebSocket auth exempel
    auth_message = client.get_ws_auth_message()
    logger.info("WebSocket auth message generated (content redacted)")

# TODO: Implementera fullständig Bitfinex API-integration 