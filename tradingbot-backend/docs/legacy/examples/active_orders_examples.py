"""
Active Orders Examples - TradingBot Backend

Detta skript innehåller exempel på hur man använder de olika active orders-relaterade endpoints
som finns tillgängliga i tradingboten.
"""

import asyncio
import os
import sys

# Lägg till projektets rotmapp i Python-sökvägen
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.api_models import OrderSide, OrderType
from rest.active_orders import (
    cancel_orders_by_symbol,
    get_active_orders,
    get_active_orders_by_side,
    get_active_orders_by_symbol,
    get_active_orders_by_type,
    get_order_by_id,
    update_order,
)
from rest.auth import place_order
from utils.logger import get_logger

logger = get_logger(__name__)


async def get_active_orders_example():
    """Exempel på hur man hämtar aktiva ordrar."""
    try:
        try:
            # Hämta alla aktiva ordrar
            orders = await get_active_orders()

            print("\n=== Aktiva Ordrar ===")
            if orders:
                for order in orders:
                    print(
                        f"{order.id}: {order.symbol} - {order.amount} @ {order.price} ({order.status})"
                    )
            else:
                print("Inga aktiva ordrar")
        except Exception as e:
            print("\n=== Aktiva Ordrar ===")
            print(f"Kunde inte hämta aktiva ordrar: {e}")
            print(
                "OBS: Detta kan bero på att ditt konto inte har några aktiva ordrar eller att du använder ett testkonto."
            )

    except Exception as e:
        logger.error(f"Fel vid hämtning av aktiva ordrar: {e}")
        print(f"Fel: {e}")


async def get_active_orders_by_symbol_example():
    """Exempel på hur man hämtar aktiva ordrar för en specifik symbol."""
    try:
        try:
            # Välj en symbol att filtrera på
            symbol = "tBTCUSD"

            # Hämta aktiva ordrar för symbolen
            orders = await get_active_orders_by_symbol(symbol)

            print(f"\n=== Aktiva Ordrar för {symbol} ===")
            if orders:
                for order in orders:
                    print(
                        f"{order.id}: {order.amount} @ {order.price} ({order.status})"
                    )
            else:
                print(f"Inga aktiva ordrar för {symbol}")
        except Exception as e:
            print("\n=== Aktiva Ordrar för symbol ===")
            print(f"Kunde inte hämta aktiva ordrar för symbol: {e}")
            print(
                "OBS: Detta kan bero på att ditt konto inte har några aktiva ordrar eller att du använder ett testkonto."
            )

    except Exception as e:
        logger.error(f"Fel vid hämtning av aktiva ordrar för symbol: {e}")
        print(f"Fel: {e}")


async def get_active_orders_by_type_example():
    """Exempel på hur man hämtar aktiva ordrar av en specifik typ."""
    try:
        try:
            # Välj en ordertyp att filtrera på
            order_type = OrderType.LIMIT

            # Hämta aktiva ordrar av den valda typen
            orders = await get_active_orders_by_type(order_type)

            print(f"\n=== Aktiva {order_type.value}-Ordrar ===")
            if orders:
                for order in orders:
                    print(
                        f"{order.id}: {order.symbol} - {order.amount} @ {order.price} ({order.status})"
                    )
            else:
                print(f"Inga aktiva {order_type.value}-ordrar")
        except Exception as e:
            print("\n=== Aktiva Ordrar efter typ ===")
            print(f"Kunde inte hämta aktiva ordrar efter typ: {e}")
            print(
                "OBS: Detta kan bero på att ditt konto inte har några aktiva ordrar eller att du använder ett testkonto."
            )

    except Exception as e:
        logger.error(f"Fel vid hämtning av aktiva ordrar efter typ: {e}")
        print(f"Fel: {e}")


async def get_active_orders_by_side_example():
    """Exempel på hur man hämtar aktiva ordrar för en specifik sida (köp/sälj)."""
    try:
        try:
            # Välj en sida att filtrera på
            side = OrderSide.BUY

            # Hämta aktiva ordrar för den valda sidan
            orders = await get_active_orders_by_side(side)

            print(f"\n=== Aktiva {side.value}-Ordrar ===")
            if orders:
                for order in orders:
                    print(
                        f"{order.id}: {order.symbol} - {abs(order.amount)} @ {order.price} ({order.status})"
                    )
            else:
                print(f"Inga aktiva {side.value}-ordrar")
        except Exception as e:
            print("\n=== Aktiva Ordrar efter sida ===")
            print(f"Kunde inte hämta aktiva ordrar efter sida: {e}")
            print(
                "OBS: Detta kan bero på att ditt konto inte har några aktiva ordrar eller att du använder ett testkonto."
            )

    except Exception as e:
        logger.error(f"Fel vid hämtning av aktiva ordrar efter sida: {e}")
        print(f"Fel: {e}")


async def place_and_update_order_example():
    """Exempel på hur man lägger och uppdaterar en order."""
    try:
        try:
            # Lägg en order
            order_data = {
                "symbol": "tBTCUSD",
                "amount": "0.001",  # Positivt för köp, negativt för sälj
                "price": "20000",  # Pris långt från marknadspris för att undvika exekvering
                "type": "EXCHANGE LIMIT",
            }

            print("\n=== Lägger Order ===")
            result = await place_order(order_data)

            if "error" in result:
                print(f"Fel vid orderläggning: {result['error']}")
                return

            print(f"Order lagd: {result}")

            # Hämta order ID från resultatet
            order_id = None
            if isinstance(result, dict) and "id" in result:
                order_id = result["id"]
            elif (
                isinstance(result, list)
                and len(result) > 0
                and isinstance(result[0], int)
            ):
                order_id = result[0]

            if not order_id:
                print("Kunde inte extrahera order ID från resultatet")
                return

            # Vänta lite för att låta ordern registreras
            print("Väntar 2 sekunder...")
            await asyncio.sleep(2)

            # Uppdatera ordern
            new_price = 21000.0
            print(f"\n=== Uppdaterar Order {order_id} ===")
            print(f"Nytt pris: {new_price}")

            update_result = await update_order(order_id, price=new_price)
            print(f"Uppdateringsresultat: {update_result}")

            # Vänta lite för att låta uppdateringen registreras
            print("Väntar 2 sekunder...")
            await asyncio.sleep(2)

            # Hämta den uppdaterade ordern
            updated_order = await get_order_by_id(order_id)
            if updated_order:
                print("\n=== Uppdaterad Order ===")
                print(
                    f"{updated_order.id}: {updated_order.symbol} - {updated_order.amount} @ {updated_order.price} ({updated_order.status})"
                )
            else:
                print("\nKunde inte hitta den uppdaterade ordern")
        except Exception as e:
            print("\n=== Lägga och Uppdatera Order ===")
            print(f"Kunde inte lägga eller uppdatera order: {e}")
            print(
                "OBS: Detta kan bero på att ditt konto inte har tillräckligt med saldo eller att du använder ett testkonto."
            )

    except Exception as e:
        logger.error(f"Fel vid orderläggning och uppdatering: {e}")
        print(f"Fel: {e}")


async def cancel_orders_example():
    """Exempel på hur man avbryter ordrar."""
    try:
        try:
            # Hämta aktiva ordrar
            orders = await get_active_orders()

            if not orders:
                print("\n=== Avbryta Ordrar ===")
                print("Inga aktiva ordrar att avbryta")
                return

            # Välj en symbol att avbryta ordrar för
            symbol = orders[0].symbol

            print(f"\n=== Avbryter Ordrar för {symbol} ===")
            result = await cancel_orders_by_symbol(symbol)
            print(f"Avbrytningsresultat: {result}")

            # Vänta lite för att låta avbrytningen registreras
            print("Väntar 2 sekunder...")
            await asyncio.sleep(2)

            # Kontrollera att ordrarna har avbrutits
            remaining_orders = await get_active_orders_by_symbol(symbol)
            print(f"\n=== Kvarvarande Ordrar för {symbol} ===")
            if remaining_orders:
                for order in remaining_orders:
                    print(
                        f"{order.id}: {order.symbol} - {order.amount} @ {order.price} ({order.status})"
                    )
            else:
                print(f"Inga aktiva ordrar kvar för {symbol}")
        except Exception as e:
            print("\n=== Avbryta Ordrar ===")
            print(f"Kunde inte avbryta ordrar: {e}")
            print(
                "OBS: Detta kan bero på att ditt konto inte har några aktiva ordrar eller att du använder ett testkonto."
            )

    except Exception as e:
        logger.error(f"Fel vid avbrytning av ordrar: {e}")
        print(f"Fel: {e}")


async def run_all_examples():
    """Kör alla exempel i sekvens."""
    print("\n=== Kör alla active orders examples ===\n")

    await get_active_orders_example()
    await get_active_orders_by_symbol_example()
    await get_active_orders_by_type_example()
    await get_active_orders_by_side_example()

    # Kommentera bort dessa om du inte vill göra ändringar i ordrar
    # await place_and_update_order_example()
    # await cancel_orders_example()

    print("\n=== Alla examples körda ===\n")


if __name__ == "__main__":
    asyncio.run(run_all_examples())
