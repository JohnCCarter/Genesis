"""
Active Orders Service - TradingBot Backend

Denna modul hanterar aktiva ordrar från Bitfinex API.
Inkluderar funktioner för att hämta aktiva ordrar och hantera dem.
"""

import json
from typing import Any, Dict, List, Optional

import httpx

from config.settings import Settings
from models.api_models import OrderResponse, OrderSide, OrderType
from rest.auth import build_auth_headers
from utils.logger import get_logger

logger = get_logger(__name__)


class ActiveOrdersService:
    """Service för att hämta och hantera aktiva ordrar från Bitfinex."""

    def __init__(self):
        self.settings = Settings()
        self.base_url = (
            getattr(self.settings, "BITFINEX_AUTH_API_URL", None)
            or self.settings.BITFINEX_API_URL
        )

    async def get_active_orders(self) -> List[OrderResponse]:
        """
        Hämtar alla aktiva ordrar från Bitfinex.

        Returns:
            Lista med OrderResponse-objekt
        """
        try:
            endpoint = "auth/r/orders"
            # För v2 auth/r endpoints ska body vara en tom JSON {} och signaturen inkludera '{}'
            empty_json = "{}"
            headers = build_auth_headers(endpoint, payload_str=empty_json)

            async with httpx.AsyncClient() as client:
                logger.info(
                    f"🌐 REST API: Hämtar aktiva ordrar från {self.base_url}/{endpoint}"
                )
                response = await client.post(
                    f"{self.base_url}/{endpoint}",
                    headers=headers,
                    content=empty_json.encode("utf-8"),
                )
                response.raise_for_status()

                orders_data = response.json()
                logger.info(f"✅ REST API: Hämtade {len(orders_data)} aktiva ordrar")

                orders = [
                    OrderResponse.from_bitfinex_data(order) for order in orders_data
                ]
                return orders

        except Exception as e:
            logger.error(f"Fel vid hämtning av aktiva ordrar: {e}")
            raise

    async def get_active_orders_by_symbol(self, symbol: str) -> List[OrderResponse]:
        """
        Hämtar aktiva ordrar för en specifik symbol.

        Args:
            symbol: Handelssymbol (t.ex. "tBTCUSD")

        Returns:
            Lista med OrderResponse-objekt
        """
        orders = await self.get_active_orders()
        return [order for order in orders if order.symbol.lower() == symbol.lower()]

    async def get_active_orders_by_type(
        self, order_type: OrderType
    ) -> List[OrderResponse]:
        """
        Hämtar aktiva ordrar av en specifik typ.

        Args:
            order_type: Ordertyp (t.ex. OrderType.LIMIT)

        Returns:
            Lista med OrderResponse-objekt
        """
        orders = await self.get_active_orders()
        return [order for order in orders if order.type == order_type]

    async def get_active_orders_by_side(self, side: OrderSide) -> List[OrderResponse]:
        """
        Hämtar aktiva ordrar för en specifik sida (köp/sälj).

        Args:
            side: Ordersida (OrderSide.BUY eller OrderSide.SELL)

        Returns:
            Lista med OrderResponse-objekt
        """
        orders = await self.get_active_orders()

        if side == OrderSide.BUY:
            return [order for order in orders if order.amount > 0]
        else:
            return [order for order in orders if order.amount < 0]

    async def get_order_by_id(self, order_id: int) -> Optional[OrderResponse]:
        """
        Hämtar en specifik order baserat på ID.

        Args:
            order_id: Order-ID

        Returns:
            OrderResponse-objekt eller None om ordern inte hittas
        """
        orders = await self.get_active_orders()

        for order in orders:
            if order.id == order_id:
                return order

        return None

    async def get_order_by_client_id(
        self, client_order_id: int
    ) -> Optional[OrderResponse]:
        """
        Hämtar en specifik order baserat på klient-ID.

        Args:
            client_order_id: Klient-order-ID

        Returns:
            OrderResponse-objekt eller None om ordern inte hittas
        """
        orders = await self.get_active_orders()

        for order in orders:
            if order.client_order_id == client_order_id:
                return order

        return None

    async def update_order(
        self,
        order_id: int,
        price: Optional[float] = None,
        amount: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Uppdaterar en aktiv order.

        Args:
            order_id: Order-ID
            price: Nytt pris (valfritt)
            amount: Ny mängd (valfritt)

        Returns:
            Svar från API:et
        """
        try:
            # Hämta ordern först för att se om den finns
            order = await self.get_order_by_id(order_id)
            if not order:
                raise ValueError(f"Ingen aktiv order hittad med ID: {order_id}")

            endpoint = "auth/w/order/update"

            # Skapa payload med orderdata
            payload = {"id": order_id}
            if price is not None:
                payload["price"] = str(price)
            if amount is not None:
                payload["amount"] = str(amount)

            headers = build_auth_headers(endpoint, payload)

            async with httpx.AsyncClient() as client:
                logger.info(f"🌐 REST API: Uppdaterar order {order_id}")
                response = await client.post(
                    f"{self.base_url}/{endpoint}", headers=headers, json=payload
                )
                response.raise_for_status()

                result = response.json()
                logger.info(f"✅ REST API: Order {order_id} uppdaterad framgångsrikt")

                return {
                    "success": True,
                    "message": f"Order {order_id} uppdaterad",
                    "data": result,
                }

        except Exception as e:
            logger.error(f"Fel vid uppdatering av order: {e}")
            raise

    async def cancel_all_orders(self) -> Dict[str, Any]:
        """
        Avbryter alla aktiva ordrar.

        Returns:
            Svar från API:et
        """
        try:
            endpoint = "auth/w/order/cancel/all"
            headers = build_auth_headers(endpoint)

            async with httpx.AsyncClient() as client:
                logger.info("🌐 REST API: Avbryter alla ordrar")
                response = await client.post(
                    f"{self.base_url}/{endpoint}", headers=headers
                )
                try:
                    response.raise_for_status()
                    result = response.json()
                    logger.info("✅ REST API: Alla ordrar avbrutna framgångsrikt")
                    return {
                        "success": True,
                        "message": "Alla ordrar avbrutna",
                        "data": result,
                    }
                except httpx.HTTPStatusError as e:
                    if e.response is not None and e.response.status_code == 404:
                        logger.warning(
                            "⚠️ cancel/all inte tillgänglig (404). Faller tillbaka till att avbryta individuellt."
                        )
                    else:
                        raise

            # Fallback: hämta alla ordrar och avbryt en och en
            orders = await self.get_active_orders()
            results: List[Dict[str, Any]] = []
            async with httpx.AsyncClient() as client:
                for order in orders:
                    try:
                        cancel_endpoint = "auth/w/order/cancel"
                        payload = {"id": order.id}
                        body_json = json.dumps(
                            payload, separators=(",", ":"), ensure_ascii=False
                        )
                        cancel_headers = build_auth_headers(
                            cancel_endpoint, payload_str=body_json
                        )
                        logger.info(
                            f"🌐 REST API: Fallback – avbryter order {order.id}"
                        )
                        resp = await client.post(
                            f"{self.base_url}/{cancel_endpoint}",
                            headers=cancel_headers,
                            content=body_json.encode("utf-8"),
                        )
                        resp.raise_for_status()
                        results.append({"id": order.id, "success": True})
                    except Exception as ex:
                        logger.error(f"Fel vid avbrytning av order {order.id}: {ex}")
                        results.append(
                            {"id": order.id, "success": False, "error": str(ex)}
                        )

            num_success = len([r for r in results if r.get("success")])
            return {
                "success": True,
                "message": f"Avbröt {num_success} av {len(results)} ordrar via fallback",
                "data": results,
            }

        except Exception as e:
            logger.error(f"Fel vid avbrytning av alla ordrar: {e}")
            raise

    async def cancel_orders_by_symbol(self, symbol: str) -> Dict[str, Any]:
        """
        Avbryter alla aktiva ordrar för en specifik symbol.

        Args:
            symbol: Handelssymbol (t.ex. "tBTCUSD")

        Returns:
            Svar från API:et
        """
        try:
            # Hämta aktiva ordrar för symbolen
            orders = await self.get_active_orders_by_symbol(symbol)

            if not orders:
                return {
                    "success": True,
                    "message": f"Inga aktiva ordrar hittades för {symbol}",
                    "data": [],
                }

            # Avbryt varje order
            results = []
            for order in orders:
                try:
                    endpoint = "auth/w/order/cancel"
                    payload = {"id": order.id}
                    headers = build_auth_headers(endpoint, payload)

                    async with httpx.AsyncClient() as client:
                        logger.info(
                            f"🌐 REST API: Avbryter order {order.id} för {symbol}"
                        )
                        response = await client.post(
                            f"{self.base_url}/{endpoint}", headers=headers, json=payload
                        )
                        response.raise_for_status()

                        result = response.json()
                        logger.info(
                            f"✅ REST API: Order {order.id} avbruten framgångsrikt"
                        )
                        results.append({"id": order.id, "success": True})

                except Exception as e:
                    logger.error(f"Fel vid avbrytning av order {order.id}: {e}")
                    results.append({"id": order.id, "success": False, "error": str(e)})

            return {
                "success": True,
                "message": f"Avbröt {len(results)} ordrar för {symbol}",
                "data": results,
            }

        except Exception as e:
            logger.error(f"Fel vid avbrytning av ordrar för {symbol}: {e}")
            raise


# Skapa en global instans av ActiveOrdersService
active_orders_service = ActiveOrdersService()


# Exportera funktioner för enkel användning
async def get_active_orders() -> List[OrderResponse]:
    return await active_orders_service.get_active_orders()


async def get_active_orders_by_symbol(symbol: str) -> List[OrderResponse]:
    return await active_orders_service.get_active_orders_by_symbol(symbol)


async def get_active_orders_by_type(order_type: OrderType) -> List[OrderResponse]:
    return await active_orders_service.get_active_orders_by_type(order_type)


async def get_active_orders_by_side(side: OrderSide) -> List[OrderResponse]:
    return await active_orders_service.get_active_orders_by_side(side)


async def get_order_by_id(order_id: int) -> Optional[OrderResponse]:
    return await active_orders_service.get_order_by_id(order_id)


async def get_order_by_client_id(client_order_id: int) -> Optional[OrderResponse]:
    return await active_orders_service.get_order_by_client_id(client_order_id)


async def update_order(
    order_id: int, price: Optional[float] = None, amount: Optional[float] = None
) -> Dict[str, Any]:
    return await active_orders_service.update_order(order_id, price, amount)


async def cancel_all_orders() -> Dict[str, Any]:
    return await active_orders_service.cancel_all_orders()


async def cancel_orders_by_symbol(symbol: str) -> Dict[str, Any]:
    return await active_orders_service.cancel_orders_by_symbol(symbol)
