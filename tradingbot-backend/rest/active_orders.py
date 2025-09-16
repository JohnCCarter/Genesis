"""
Active Orders Service - TradingBot Backend

Denna modul hanterar aktiva ordrar från Bitfinex API.
Inkluderar funktioner för att hämta aktiva ordrar och hantera dem.
"""

import json
from typing import Any

import httpx

from services.exchange_client import get_exchange_client
from config.settings import settings
from models.api_models import OrderResponse, OrderSide, OrderType
from utils.logger import get_logger

logger = get_logger(__name__)


class ActiveOrdersService:
    """Service för att hämta och hantera aktiva ordrar från Bitfinex."""

    def __init__(self):
        self.settings = settings
        self.base_url = getattr(self.settings, "BITFINEX_AUTH_API_URL", None) or self.settings.BITFINEX_API_URL

    async def get_active_orders(self) -> list[OrderResponse]:
        """
        Hämtar alla aktiva ordrar från Bitfinex.

        Returns:
            Lista med OrderResponse-objekt
        """
        try:
            # Safeguard: om API‑nycklar saknas, returnera tom lista i stället för att krascha UI
            if not (self.settings.BITFINEX_API_KEY and self.settings.BITFINEX_API_SECRET):
                logger.info("BITFINEX_API_KEY/SECRET saknas – returnerar tom lista för aktiva ordrar")
                return []
            endpoint = "auth/r/orders"
            ec = get_exchange_client()
            logger.info(f"🌐 REST API: Hämtar aktiva ordrar från {self.base_url}/{endpoint}")
            response = await ec.signed_request(method="post", endpoint=endpoint, body={})
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as he:
                status = he.response.status_code if he.response is not None else "?"
                logger.warning(f"Bitfinex svarade {status} vid hämtning av aktiva ordrar – returnerar tom lista")
                return []

            orders_data = response.json()
            logger.info(f"✅ REST API: Hämtade {len(orders_data)} aktiva ordrar")

            orders = [OrderResponse.from_bitfinex_data(order) for order in orders_data]
            return orders

        except Exception as e:
            # Tystare fallback för UI: returnera tom lista vid oväntade fel
            logger.error(f"Fel vid hämtning av aktiva ordrar: {e}")
            return []

    async def get_active_orders_by_symbol(self, symbol: str) -> list[OrderResponse]:
        """
        Hämtar aktiva ordrar för en specifik symbol.

        Args:
            symbol: Handelssymbol (t.ex. "tBTCUSD")

        Returns:
            Lista med OrderResponse-objekt
        """
        orders = await self.get_active_orders()
        return [order for order in orders if order.symbol.lower() == symbol.lower()]

    async def get_active_orders_by_type(self, order_type: OrderType) -> list[OrderResponse]:
        """
        Hämtar aktiva ordrar av en specifik typ.

        Args:
            order_type: Ordertyp (t.ex. OrderType.LIMIT)

        Returns:
            Lista med OrderResponse-objekt
        """
        orders = await self.get_active_orders()
        return [order for order in orders if order.type == order_type]

    async def get_active_orders_by_side(self, side: OrderSide) -> list[OrderResponse]:
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

    async def get_order_by_id(self, order_id: int) -> OrderResponse | None:
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

    async def get_order_by_client_id(self, client_order_id: int) -> OrderResponse | None:
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
        price: float | None = None,
        amount: float | None = None,
    ) -> dict[str, Any]:
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

            ec = get_exchange_client()
            logger.info(f"🌐 REST API: Uppdaterar order {order_id}")
            response = await ec.signed_request(method="post", endpoint=endpoint, body=payload)
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

    async def cancel_all_orders(self) -> dict[str, Any]:
        """
        Avbryter alla aktiva ordrar.

        Returns:
            Svar från API:et
        """
        try:
            endpoint = "auth/w/order/cancel/all"
            ec = get_exchange_client()
            logger.info("🌐 REST API: Avbryter alla ordrar")
            response = await ec.signed_request(method="post", endpoint=endpoint, body={})
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
            results: list[dict[str, Any]] = []
            ec = get_exchange_client()
            for order in orders:
                try:
                    cancel_endpoint = "auth/w/order/cancel"
                    payload = {"id": order.id}
                    logger.info(f"🌐 REST API: Fallback – avbryter order {order.id}")
                    resp = await ec.signed_request(method="post", endpoint=cancel_endpoint, body=payload)
                    resp.raise_for_status()
                    results.append({"id": order.id, "success": True})
                except Exception as ex:
                    logger.error(f"Fel vid avbrytning av order {order.id}: {ex}")
                    results.append({"id": order.id, "success": False, "error": str(ex)})

            num_success = len([r for r in results if r.get("success")])
            return {
                "success": True,
                "message": f"Avbröt {num_success} av {len(results)} ordrar via fallback",
                "data": results,
            }

        except Exception as e:
            logger.error(f"Fel vid avbrytning av alla ordrar: {e}")
            raise

    async def cancel_orders_by_symbol(self, symbol: str) -> dict[str, Any]:
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
            ec = get_exchange_client()
            for order in orders:
                try:
                    endpoint = "auth/w/order/cancel"
                    payload = {"id": order.id}
                    logger.info(f"🌐 REST API: Avbryter order {order.id} för {symbol}")
                    response = await ec.signed_request(method="post", endpoint=endpoint, body=payload)
                    response.raise_for_status()

                    result = response.json()
                    logger.info(f"✅ REST API: Order {order.id} avbruten framgångsrikt")
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
async def get_active_orders() -> list[OrderResponse]:
    return await active_orders_service.get_active_orders()


async def get_active_orders_by_symbol(symbol: str) -> list[OrderResponse]:
    return await active_orders_service.get_active_orders_by_symbol(symbol)


async def get_active_orders_by_type(order_type: OrderType) -> list[OrderResponse]:
    return await active_orders_service.get_active_orders_by_type(order_type)


async def get_active_orders_by_side(side: OrderSide) -> list[OrderResponse]:
    return await active_orders_service.get_active_orders_by_side(side)


async def get_order_by_id(order_id: int) -> OrderResponse | None:
    return await active_orders_service.get_order_by_id(order_id)


async def get_order_by_client_id(client_order_id: int) -> OrderResponse | None:
    return await active_orders_service.get_order_by_client_id(client_order_id)


async def update_order(order_id: int, price: float | None = None, amount: float | None = None) -> dict[str, Any]:
    return await active_orders_service.update_order(order_id, price, amount)


async def cancel_all_orders() -> dict[str, Any]:
    return await active_orders_service.cancel_all_orders()


async def cancel_orders_by_symbol(symbol: str) -> dict[str, Any]:
    return await active_orders_service.cancel_orders_by_symbol(symbol)
