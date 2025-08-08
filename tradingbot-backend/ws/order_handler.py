"""
WebSocket Order Handler - TradingBot Backend

Denna modul hanterar orderoperationer via Bitfinex WebSocket API.
"""

import json
import hmac
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

from ws.auth import build_ws_auth_payload
from rest.order_validator import order_validator
from utils.logger import get_logger

logger = get_logger(__name__)


class WSOrderHandler:
    """
    Hanterar orderoperationer via Bitfinex WebSocket API.
    """
    
    def __init__(self, websocket=None):
        """
        Initialiserar WSOrderHandler.
        
        Args:
            websocket: WebSocket-anslutning (om redan etablerad)
        """
        self.websocket = websocket
        self.authenticated = False
        self.order_validator = order_validator
    
    async def set_websocket(self, websocket):
        """
        Sätter WebSocket-anslutningen.
        
        Args:
            websocket: WebSocket-anslutning
        """
        self.websocket = websocket
        self.authenticated = False
    
    async def authenticate(self) -> bool:
        """
        Autentiserar mot Bitfinex WebSocket API.
        
        Returns:
            bool: True om autentiseringen lyckades
        """
        if not self.websocket:
            logger.error("WebSocket-anslutning saknas")
            return False
        
        try:
            # Skapa och skicka autentiseringsmeddelande
            auth_message = build_ws_auth_payload()
            await self.websocket.send(auth_message)
            logger.info("WebSocket autentiseringsförfrågan skickad")
            
            # Autentisering bekräftas via callback i ws/manager.py
            # Denna metod returnerar bara att förfrågan skickades
            return True
            
        except Exception as e:
            logger.error(f"Fel vid WebSocket-autentisering: {e}")
            return False
    
    async def place_order(self, order: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Lägger en order via WebSocket.
        
        Args:
            order: Orderdata
            
        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        if not self.websocket:
            return False, "WebSocket-anslutning saknas"
        
        if not self.authenticated:
            return False, "WebSocket inte autentiserad"
        
        try:
            # Validera ordern
            is_valid, error_message = self.order_validator.validate_order(order)
            if not is_valid:
                return False, error_message
            
            # Formatera ordern för Bitfinex API
            formatted_order = self.order_validator.format_order_for_bitfinex(order)
            
            # Skapa WebSocket-meddelande för ny order
            # Format: [0, "on", null, {order_details}]
            message = [0, "on", None, {
                "type": formatted_order["type"],
                "symbol": formatted_order["symbol"],
                "amount": formatted_order["amount"],
                "price": formatted_order.get("price", "0")
            }]
            
            # Lägg till valfria parametrar
            if "price_trailing" in formatted_order:
                message[3]["price_trailing"] = formatted_order["price_trailing"]
                
            if "price_aux_limit" in formatted_order:
                message[3]["price_aux_limit"] = formatted_order["price_aux_limit"]
                
            if "flags" in formatted_order:
                message[3]["flags"] = formatted_order["flags"]
            
            # Skicka meddelandet
            await self.websocket.send(json.dumps(message))
            logger.info(f"WebSocket order skickad: {formatted_order}")
            
            return True, None
            
        except Exception as e:
            error_msg = f"Fel vid WebSocket orderläggning: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    async def cancel_order(self, order_id: int) -> Tuple[bool, Optional[str]]:
        """
        Avbryter en order via WebSocket.
        
        Args:
            order_id: ID för ordern som ska avbrytas
            
        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        if not self.websocket:
            return False, "WebSocket-anslutning saknas"
        
        if not self.authenticated:
            return False, "WebSocket inte autentiserad"
        
        try:
            # Skapa WebSocket-meddelande för att avbryta order
            # Format: [0, "oc", null, {id: order_id}]
            message = [0, "oc", None, {"id": order_id}]
            
            # Skicka meddelandet
            await self.websocket.send(json.dumps(message))
            logger.info(f"WebSocket avbryt order skickad: {order_id}")
            
            return True, None
            
        except Exception as e:
            error_msg = f"Fel vid WebSocket orderavbrytning: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    async def get_active_orders(self) -> Tuple[bool, Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Hämtar aktiva order via WebSocket.
        
        Returns:
            Tuple[bool, Optional[List[Dict[str, Any]]], Optional[str]]: 
                (success, orders, error_message)
        """
        if not self.websocket:
            return False, None, "WebSocket-anslutning saknas"
        
        if not self.authenticated:
            return False, None, "WebSocket inte autentiserad"
        
        try:
            # Skapa WebSocket-meddelande för att hämta aktiva order
            # Format: [0, "os", null, {}]
            message = [0, "os", None, {}]
            
            # Skicka meddelandet
            await self.websocket.send(json.dumps(message))
            logger.info("WebSocket förfrågan om aktiva order skickad")
            
            # Svaret hanteras via callback i ws/manager.py
            # Denna metod returnerar bara att förfrågan skickades
            return True, None, None
            
        except Exception as e:
            error_msg = f"Fel vid WebSocket förfrågan om aktiva order: {e}"
            logger.error(error_msg)
            return False, None, error_msg


# Singleton-instans för enkel åtkomst
ws_order_handler = WSOrderHandler()