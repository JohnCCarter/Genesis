"""
Order Examples - TradingBot Backend

Detta skript visar exempel på hur man kan använda order-funktionalitet
i både REST och WebSocket API.
"""

import asyncio
import json
import os
import sys
from datetime import datetime

import httpx

# Lägg till projektets rot i Python-sökvägen
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rest.auth import place_order as rest_place_order
from rest.order_validator import order_validator
from utils.logger import get_logger
from ws.order_handler import ws_order_handler

logger = get_logger("order_examples")


async def example_rest_order():
    """
    Exempel på hur man lägger en order via REST API.
    """
    print("\n=== REST API Order Example ===\n")

    # Skapa en exempelorder
    order = {
        "symbol": "tTESTBTC:TESTUSD",  # Paper trading symbol
        "amount": "0.001",  # Köp 0.001 BTC
        "price": "20000",  # Limit pris på $20,000
        "type": "EXCHANGE LIMIT",  # Limit order
    }

    # Validera ordern
    is_valid, error = order_validator.validate_order(order)
    if not is_valid:
        print(f"❌ Ogiltig order: {error}")
        return

    print(f"✅ Order validerad: {order}")

    # Formatera ordern för Bitfinex API
    formatted_order = order_validator.format_order_for_bitfinex(order)
    print(f"📝 Formaterad order: {formatted_order}")

    # Skicka ordern till Bitfinex via REST API
    print("🚀 Skickar order via REST API...")
    result = await rest_place_order(formatted_order)

    # Visa resultatet
    if "error" in result:
        print(f"❌ Order misslyckades: {result['error']}")
    else:
        print(f"✅ Order framgångsrikt lagd: {json.dumps(result, indent=2)}")


async def example_ws_order():
    """
    Exempel på hur man lägger en order via WebSocket API.
    """
    print("\n=== WebSocket API Order Example ===\n")

    # Skapa en exempelorder
    order = {
        "symbol": "tTESTBTC:TESTUSD",  # Paper trading symbol
        "amount": "0.001",  # Köp 0.001 BTC
        "price": "20000",  # Limit pris på $20,000
        "type": "EXCHANGE LIMIT",  # Limit order
    }

    # Validera ordern
    is_valid, error = order_validator.validate_order(order)
    if not is_valid:
        print(f"❌ Ogiltig order: {error}")
        return

    print(f"✅ Order validerad: {order}")

    # Kontrollera om WebSocket är ansluten
    if not ws_order_handler.websocket:
        print(
            "❌ WebSocket är inte ansluten. Kör main.py först för att starta WebSocket-anslutningen."
        )
        return

    # Kontrollera om WebSocket är autentiserad
    if not ws_order_handler.authenticated:
        print("🔑 WebSocket är inte autentiserad. Försöker autentisera...")
        auth_success = await ws_order_handler.authenticate()
        if not auth_success:
            print("❌ WebSocket-autentisering misslyckades")
            return
        print("✅ WebSocket autentiserad")

    # Skicka ordern via WebSocket
    print("🚀 Skickar order via WebSocket...")
    success, error = await ws_order_handler.place_order(order)

    # Visa resultatet
    if not success:
        print(f"❌ Order misslyckades: {error}")
    else:
        print("✅ Order skickad via WebSocket")
        print("⚠️ Notera: WebSocket-svar hanteras asynkront via callbacks")


async def example_rest_backend_order():
    """
    Exempel på hur man lägger en order via backend REST API.
    """
    print("\n=== Backend REST API Order Example ===\n")

    # Skapa en exempelorder
    order_data = {
        "symbol": "tTESTBTC:TESTUSD",  # Paper trading symbol
        "amount": "0.001",  # Köp 0.001 BTC
        "price": "20000",  # Limit pris på $20,000
        "type": "EXCHANGE LIMIT",  # Limit order
        "side": "buy",  # Köp
    }

    # Skicka ordern till backend API
    print("🚀 Skickar order via backend REST API...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8000/api/v2/order", json=order_data
            )

            # Visa resultatet
            print(f"📡 Status: {response.status_code}")
            result = response.json()

            if result.get("success"):
                print(
                    f"✅ Order framgångsrikt lagd: {json.dumps(result.get('data'), indent=2)}"
                )
            else:
                print(f"❌ Order misslyckades: {result.get('error')}")

    except Exception as e:
        print(f"❌ Fel vid anrop till backend API: {e}")
        print("⚠️ Kontrollera att backend-servern körs med 'python main.py'")


async def example_market_order():
    """
    Exempel på hur man lägger en market order.
    """
    print("\n=== Market Order Example ===\n")

    # Skapa en exempelorder för market order
    order = {
        "symbol": "tTESTBTC:TESTUSD",  # Paper trading symbol
        "amount": "0.001",  # Köp 0.001 BTC
        "type": "EXCHANGE MARKET",  # Market order
        "side": "buy",  # Köp
    }

    # Validera ordern
    is_valid, error = order_validator.validate_order(order)
    if not is_valid:
        print(f"❌ Ogiltig order: {error}")
        return

    print(f"✅ Market order validerad: {order}")

    # Formatera ordern för Bitfinex API
    formatted_order = order_validator.format_order_for_bitfinex(order)
    print(f"📝 Formaterad market order: {formatted_order}")

    # Skicka ordern till Bitfinex via REST API
    print("🚀 Skickar market order via REST API...")
    result = await rest_place_order(formatted_order)

    # Visa resultatet
    if "error" in result:
        print(f"❌ Market order misslyckades: {result['error']}")
    else:
        print(f"✅ Market order framgångsrikt lagd: {json.dumps(result, indent=2)}")


async def example_cancel_order(order_id: int):
    """
    Exempel på hur man avbryter en order.

    Args:
        order_id: ID för ordern som ska avbrytas
    """
    print(f"\n=== Cancel Order Example (ID: {order_id}) ===\n")

    # REST API exempel
    print("🚀 Avbryter order via REST API...")
    from rest.auth import cancel_order as rest_cancel_order

    result = await rest_cancel_order(order_id)

    # Visa resultatet
    if "error" in result:
        print(f"❌ Orderavbrytning misslyckades: {result['error']}")
    else:
        print(f"✅ Order framgångsrikt avbruten: {json.dumps(result, indent=2)}")

    # WebSocket exempel (om tillgängligt)
    if ws_order_handler.websocket and ws_order_handler.authenticated:
        print("🚀 Avbryter order via WebSocket...")
        success, error = await ws_order_handler.cancel_order(order_id)

        if not success:
            print(f"❌ WebSocket orderavbrytning misslyckades: {error}")
        else:
            print("✅ WebSocket avbrytningsförfrågan skickad")


async def run_examples():
    """
    Kör alla exempel.
    """
    print("🚀 Genesis Trading Bot - Order Examples")
    print("======================================")

    # Kör REST API exempel
    await example_rest_order()

    # Kör market order exempel
    await example_market_order()

    # Kör backend REST API exempel
    await example_rest_backend_order()

    # Notera: WebSocket exempel kräver en aktiv WebSocket-anslutning
    print("\n⚠️ WebSocket-exempel kräver en aktiv anslutning.")
    print("⚠️ Kör main.py i en separat terminal för att starta WebSocket-servern.")

    # Avsluta
    print("\n✅ Exempel slutförda!")


if __name__ == "__main__":
    asyncio.run(run_examples())
