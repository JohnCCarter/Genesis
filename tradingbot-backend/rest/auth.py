"""
REST Authentication - TradingBot Backend

Denna modul hanterar autentisering för REST API endpoints.
Inkluderar JWT-token validering och användarhantering.
"""

import hashlib
import hmac
import json
import os
from datetime import datetime

from fastapi.security import HTTPBearer

from config.settings import settings
from services.exchange_client import get_exchange_client
from utils.logger import get_logger

security = HTTPBearer()
logger = get_logger(__name__)

# Bitfinex API credentials - använd Settings (logga endast status, inte nycklar)
logger.info(
    "API Key status: %s",
    "✅ Konfigurerad" if settings.BITFINEX_API_KEY else "❌ Saknas",
)
logger.info(
    "API Secret status: %s",
    "✅ Konfigurerad" if settings.BITFINEX_API_SECRET else "❌ Saknas",
)


def build_auth_headers(
    endpoint: str,
    payload: dict = None,
    v1: bool = False,
    payload_str: str | None = None,
) -> dict:
    """Proxy till ExchangeClient för att behålla bakåtkompatibelt API."""
    client = get_exchange_client()
    return client.build_rest_headers(
        endpoint=endpoint, payload=payload, v1=v1, payload_str=payload_str
    )


def redact_headers(headers: dict) -> dict:
    """
    Return a copy of headers with sensitive fields redacted.
    """
    redacted = headers.copy()
    if redacted.get("bfx-apikey"):
        redacted["bfx-apikey"] = "[REDACTED]"
    if redacted.get("bfx-signature"):
        redacted["bfx-signature"] = "[REDACTED]"
    return redacted


def get_auth_headers() -> dict:
    """Publik helper för health checks m.fl. att generera signerade headers för ett no-op endpoint.

    Använder v2 och ett harmlöst endpointvärde för att validera signeringskedjan utan att göra nätverksanrop.
    """
    try:
        # Använd ett fiktivt endpoint för signeringstest
        return build_auth_headers(endpoint="auth/r/ping", payload_str="{}")
    except Exception:
        return {}


async def place_order(order: dict) -> dict:
    """
    Lägger en order via Bitfinex REST API.

    Args:
        order: Dict med orderdata (symbol, amount, price, type)

    Returns:
        dict: API-svar från Bitfinex
    """
    try:
        # Kontrollera API-nycklar (dynamiskt)
        if not settings.BITFINEX_API_KEY or not settings.BITFINEX_API_SECRET:
            error_msg = "API-nycklar saknas. Kontrollera BITFINEX_API_KEY och BITFINEX_API_SECRET i .env-filen."
            logger.error(error_msg)
            return {"error": error_msg}

        endpoint = "auth/w/order/submit"
        base_url = (
            getattr(settings, "BITFINEX_AUTH_API_URL", None)
            or settings.BITFINEX_API_URL
        )
        url = f"{base_url}/{endpoint}"

        # Konvertera till Bitfinex format (REST v2 använder tecken på amount som riktning)
        # Säkerställ korrekt tecken utifrån "side" om uppgiven
        in_amount = order.get("amount")
        amount_str = str(in_amount) if in_amount is not None else ""
        side_val = order.get("side")
        if isinstance(side_val, str):
            s = side_val.strip().lower()
            if s == "sell" and amount_str and not amount_str.startswith("-"):
                amount_str = f"-{amount_str}"
            if s == "buy" and amount_str.startswith("-"):
                amount_str = amount_str.lstrip("-")
        # Mappa order-typer till Bitfinex format
        order_type = order.get("type", "EXCHANGE LIMIT")
        if order_type == "MARKET":
            order_type = "EXCHANGE MARKET"
        elif order_type == "LIMIT":
            order_type = "EXCHANGE LIMIT"

        bitfinex_order = {
            "type": order_type,
            "symbol": order.get("symbol"),
            "amount": amount_str,
            "price": order.get("price"),
        }

        # Extra flaggor (Reduce-Only/Post-Only/flags)
        try:
            if bool(order.get("reduce_only")):
                bitfinex_order["reduce_only"] = True
        except Exception:
            pass
        try:
            # Bitfinex fält heter ofta "postonly" i API:t
            if bool(order.get("post_only")) or bool(order.get("postonly")):
                bitfinex_order["postonly"] = True
        except Exception:
            pass
        try:
            if order.get("flags") is not None:
                bitfinex_order["flags"] = int(order.get("flags"))
        except Exception:
            pass

        logger.info(f"🌐 REST API: Lägger order")
        logger.info(f"📋 Order data: {bitfinex_order}")

        # Skicka via central ExchangeClient
        ec = get_exchange_client()
        response_data = await ec.signed_request(
            method="post",
            endpoint=endpoint,
            body=bitfinex_order,
            timeout=settings.ORDER_HTTP_TIMEOUT,
        )
        response_data.raise_for_status()
        result = response_data.json()
        logger.info(f"✅ REST API: Order lagd framgångsrikt: {result}")
        return result

    except Exception as e:
        error_msg = f"Fel vid orderläggning: {e}"
        logger.error(error_msg)
        return {"error": error_msg}


async def cancel_order(order_id: int) -> dict:
    """
    Stänger/cancela en order via Bitfinex REST API.

    Args:
        order_id: ID för ordern som ska stängas

    Returns:
        dict: API-svar från Bitfinex
    """
    try:
        # Kontrollera API-nycklar dynamiskt
        if not settings.BITFINEX_API_KEY or not settings.BITFINEX_API_SECRET:
            error_msg = "API-nycklar saknas. Kontrollera BITFINEX_API_KEY och BITFINEX_API_SECRET i .env-filen."
            logger.error(error_msg)
            return {"error": error_msg}

        endpoint = "auth/w/order/cancel"
        base_url = (
            getattr(settings, "BITFINEX_AUTH_API_URL", None)
            or settings.BITFINEX_API_URL
        )
        url = f"{base_url}/{endpoint}"

        # Konvertera till Bitfinex format
        bitfinex_cancel = {"id": order_id}

        logger.info(f"🌐 REST API: Stänger order {order_id}")
        logger.info(f"📋 Cancel data: {bitfinex_cancel}")

        # Skicka via central ExchangeClient
        ec = get_exchange_client()
        response_data = await ec.signed_request(
            method="post",
            endpoint=endpoint,
            body=bitfinex_cancel,
            timeout=settings.ORDER_HTTP_TIMEOUT,
        )
        response_data.raise_for_status()
        result = response_data.json()
        logger.info(f"✅ REST API: Order stängd framgångsrikt: {result}")
        return result

    except Exception as e:
        error_msg = f"Fel vid orderstängning: {e}"
        logger.error(error_msg)
        return {"error": error_msg}


# TODO: Implementera JWT autentiseringslogik för applikationen
