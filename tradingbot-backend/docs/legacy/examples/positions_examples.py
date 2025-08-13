"""
Positions Examples - TradingBot Backend

Detta skript innehåller exempel på hur man använder de olika positions-relaterade endpoints
som finns tillgängliga i tradingboten.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta

from rest.positions import (close_position, get_long_positions,
                            get_position_by_symbol, get_positions,
                            get_short_positions)
from rest.positions_history import (claim_position, get_positions_audit,
                                    get_positions_history,
                                    get_positions_snapshot,
                                    update_position_funding_type)
from utils.logger import get_logger

# Lägg till projektets rotmapp i Python-sökvägen
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = get_logger(__name__)


async def get_positions_example():
    """Exempel på hur man hämtar aktiva positioner."""
    try:
        try:
            # Hämta alla positioner
            positions = await get_positions()

            print("\n=== Aktiva Positioner ===")
            if positions:
                for position in positions:
                    direction = "LONG" if position.is_long else "SHORT"
                    print(
                        f"{position.symbol} {direction}: {abs(position.amount)} @ {position.base_price} "
                        + f"(PnL: {position.profit_loss})"
                    )
            else:
                print("Inga aktiva positioner")

            # Hämta en specifik position
            btc_position = await get_position_by_symbol("tBTCUSD")
            if btc_position:
                print(
                    f"\nBTC Position: {btc_position.amount} @ {btc_position.base_price}"
                )
            else:
                print("\nIngen BTC position hittad")

            # Hämta long-positioner
            long_positions = await get_long_positions()
            print(f"\nAntal long-positioner: {len(long_positions)}")

            # Hämta short-positioner
            short_positions = await get_short_positions()
            print(f"Antal short-positioner: {len(short_positions)}")
        except Exception as e:
            print("\n=== Aktiva Positioner ===")
            print(f"Kunde inte hämta positioner: {e}")
            print(
                "OBS: Detta kan bero på att ditt konto inte har några positioner eller att du använder ett testkonto."
            )

    except Exception as e:
        logger.error(f"Fel vid hämtning av positioner: {e}")
        print(f"Fel: {e}")


async def get_positions_history_example():
    """Exempel på hur man hämtar positionshistorik."""
    try:
        try:
            # Beräkna tidsintervall (senaste 30 dagarna)
            end_time = int(datetime.now().timestamp() * 1000)  # Millisekunder
            start_time = int(
                (datetime.now() - timedelta(days=30)).timestamp() * 1000
            )  # Millisekunder

            # Hämta positionshistorik
            positions = await get_positions_history(start_time, end_time, 10)

            print("\n=== Positionshistorik (10 senaste) ===")
            if positions:
                for position in positions:
                    direction = "LONG" if position.is_long else "SHORT"
                    created = (
                        position.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        if position.created_at
                        else "N/A"
                    )
                    closed = (
                        position.closed_at.strftime("%Y-%m-%d %H:%M:%S")
                        if position.closed_at
                        else "N/A"
                    )
                    print(
                        f"{position.symbol} {direction}: {abs(position.amount)} @ {position.base_price} "
                        + f"(Status: {position.status}, Skapad: {created}, Stängd: {closed})"
                    )
            else:
                print("Ingen positionshistorik hittad")
        except Exception as e:
            print("\n=== Positionshistorik ===")
            print(f"Kunde inte hämta positionshistorik: {e}")
            print(
                "OBS: Detta kan bero på att ditt konto inte har någon positionshistorik eller att du använder ett testkonto."
            )

    except Exception as e:
        logger.error(f"Fel vid hämtning av positionshistorik: {e}")
        print(f"Fel: {e}")


async def get_positions_snapshot_example():
    """Exempel på hur man hämtar en ögonblicksbild av positioner."""
    try:
        try:
            # Hämta positionsögonblicksbild
            positions = await get_positions_snapshot()

            print("\n=== Positionsögonblicksbild ===")
            if positions:
                for position in positions:
                    direction = "LONG" if position.is_long else "SHORT"
                    print(
                        f"{position.symbol} {direction}: {abs(position.amount)} @ {position.base_price} "
                        + f"(Status: {position.status})"
                    )
            else:
                print("Inga positioner i ögonblicksbilden")
        except Exception as e:
            print("\n=== Positionsögonblicksbild ===")
            print(f"Kunde inte hämta positionsögonblicksbild: {e}")
            print(
                "OBS: Detta kan bero på att ditt konto inte har några positioner eller att du använder ett testkonto."
            )

    except Exception as e:
        logger.error(f"Fel vid hämtning av positionsögonblicksbild: {e}")
        print(f"Fel: {e}")


async def get_positions_audit_example():
    """Exempel på hur man hämtar positionsrevision."""
    try:
        try:
            # Beräkna tidsintervall (senaste 30 dagarna)
            end_time = int(datetime.now().timestamp() * 1000)  # Millisekunder
            start_time = int(
                (datetime.now() - timedelta(days=30)).timestamp() * 1000
            )  # Millisekunder

            # Hämta positionsrevision för en specifik symbol
            symbol = "tBTCUSD"
            positions = await get_positions_audit(symbol, start_time, end_time, 10)

            print(f"\n=== Positionsrevision för {symbol} (10 senaste) ===")
            if positions:
                for position in positions:
                    direction = "LONG" if position.is_long else "SHORT"
                    created = (
                        position.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        if position.created_at
                        else "N/A"
                    )
                    print(
                        f"{position.symbol} {direction}: {abs(position.amount)} @ {position.base_price} "
                        + f"(Status: {position.status}, Skapad: {created})"
                    )
            else:
                print(f"Ingen positionsrevision hittad för {symbol}")
        except Exception as e:
            print("\n=== Positionsrevision ===")
            print(f"Kunde inte hämta positionsrevision: {e}")
            print(
                "OBS: Detta kan bero på att ditt konto inte har någon positionshistorik eller att du använder ett testkonto."
            )

    except Exception as e:
        logger.error(f"Fel vid hämtning av positionsrevision: {e}")
        print(f"Fel: {e}")


async def close_position_example():
    """Exempel på hur man stänger en position."""
    try:
        try:
            # Hämta alla positioner
            positions = await get_positions()

            if positions:
                # Välj den första positionen att stänga
                position_to_close = positions[0]
                symbol = position_to_close.symbol

                print(f"\n=== Stänger Position {symbol} ===")
                result = await close_position(symbol)
                print(f"Resultat: {result}")
            else:
                print("\n=== Stänger Position ===")
                print("Inga positioner att stänga")
        except Exception as e:
            print("\n=== Stänger Position ===")
            print(f"Kunde inte stänga position: {e}")
            print(
                "OBS: Detta kan bero på att ditt konto inte har några positioner eller att du använder ett testkonto."
            )

    except Exception as e:
        logger.error(f"Fel vid stängning av position: {e}")
        print(f"Fel: {e}")


async def claim_position_example():
    """Exempel på hur man gör anspråk på en position."""
    try:
        try:
            # Hämta alla positioner
            positions = await get_positions()

            if positions:
                # Välj den första positionen att göra anspråk på
                position_to_claim = positions[0]
                position_id = position_to_claim.symbol

                print(f"\n=== Gör Anspråk på Position {position_id} ===")
                result = await claim_position(position_id)
                print(f"Resultat: {result}")
            else:
                print("\n=== Gör Anspråk på Position ===")
                print("Inga positioner att göra anspråk på")
        except Exception as e:
            print("\n=== Gör Anspråk på Position ===")
            print(f"Kunde inte göra anspråk på position: {e}")
            print(
                "OBS: Detta kan bero på att ditt konto inte har några positioner eller att du använder ett testkonto."
            )

    except Exception as e:
        logger.error(f"Fel vid anspråk på position: {e}")
        print(f"Fel: {e}")


async def update_position_funding_type_example():
    """Exempel på hur man uppdaterar finansieringstypen för en position."""
    try:
        try:
            # Hämta alla positioner
            positions = await get_positions()

            if positions:
                # Välj den första positionen att uppdatera
                position_to_update = positions[0]
                symbol = position_to_update.symbol

                # Byt finansieringstyp (0 för daily, 1 för term)
                new_funding_type = 1 if position_to_update.funding_type == 0 else 0

                print(
                    f"\n=== Uppdaterar Finansieringstyp för Position {symbol} till {new_funding_type} ==="
                )
                result = await update_position_funding_type(symbol, new_funding_type)
                print(f"Resultat: {result}")
            else:
                print("\n=== Uppdaterar Finansieringstyp för Position ===")
                print("Inga positioner att uppdatera")
        except Exception as e:
            print("\n=== Uppdaterar Finansieringstyp för Position ===")
            print(f"Kunde inte uppdatera finansieringstyp: {e}")
            print(
                "OBS: Detta kan bero på att ditt konto inte har några positioner eller att du använder ett testkonto."
            )

    except Exception as e:
        logger.error(f"Fel vid uppdatering av finansieringstyp: {e}")
        print(f"Fel: {e}")


async def run_all_examples():
    """Kör alla exempel i sekvens."""
    print("\n=== Kör alla positions examples ===\n")

    await get_positions_example()
    await get_positions_history_example()
    await get_positions_snapshot_example()
    await get_positions_audit_example()

    # Kommentera bort dessa om du inte vill göra ändringar i positioner
    # await close_position_example()
    # await claim_position_example()
    # await update_position_funding_type_example()

    print("\n=== Alla examples körda ===\n")


if __name__ == "__main__":
    asyncio.run(run_all_examples())
