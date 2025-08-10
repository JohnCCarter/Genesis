"""
WebSocket Account Examples - TradingBot Backend

Detta skript visar exempel på hur man kan använda WebSocket-anslutningar
för att få realtidsuppdateringar om plånböcker och positioner.
"""

import asyncio
import json
import os
import sys
from pprint import pprint

# Lägg till projektets rot i Python-sökvägen
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.bitfinex_websocket import BitfinexWebSocketService
from utils.logger import get_logger
from ws.position_handler import WSPositionHandler
from ws.wallet_handler import WSWalletHandler

logger = get_logger("websocket_account_examples")


class DummySIOClient:
    """
    En enkel dummy Socket.IO-klient för exempel.
    """

    async def emit(self, event, data):
        """Emulerar Socket.IO emit."""
        logger.info(f"Socket.IO emit: {event}")
        if event == "wallet_update":
            logger.info(
                f"  Plånboksuppdatering: {data['wallet_type']} {data['currency']} {data['balance']}"
            )
        elif event == "wallet_snapshot":
            logger.info(f"  Plånboks-snapshot: {len(data)} plånböcker")
        elif event == "position_update":
            logger.info(
                f"  Positionsuppdatering: {data['symbol']} {data['status']} {data['amount']}"
            )
        elif event == "position_snapshot":
            logger.info(f"  Positions-snapshot: {len(data)} positioner")
        elif event == "position_close":
            logger.info(f"  Position stängd: {data['symbol']}")


async def wallet_updates_example():
    """
    Exempel på hur man kan använda WSWalletHandler för att få plånboksuppdateringar.
    """
    print("\n=== WebSocket Wallet Updates Example ===\n")

    try:
        # Skapa Bitfinex WebSocket-service
        bitfinex_ws = BitfinexWebSocketService()
        await bitfinex_ws.connect()

        # Skapa dummy Socket.IO-klient
        sio_client = DummySIOClient()

        # Skapa WSWalletHandler
        wallet_handler = WSWalletHandler(sio_client, bitfinex_ws)

        # Registrera callback för plånboksuppdateringar
        def on_wallet_update(wallets):
            print(f"📢 Plånboksuppdatering mottagen: {len(wallets)} plånböcker")
            for wallet in wallets:
                print(
                    f"  {wallet['wallet_type']} {wallet['currency']}: {wallet['balance']}"
                )

        wallet_handler.register_wallet_callback(on_wallet_update)

        # Autentisera och starta plånboksuppdateringar
        print("🔑 Autentiserar WebSocket-anslutning...")
        auth_success = await wallet_handler.authenticate()
        if auth_success:
            print("✅ WebSocket-autentisering lyckades")

            # Starta plånboksuppdateringar
            print("📡 Startar prenumeration på plånboksuppdateringar...")
            updates_success = await wallet_handler.start_wallet_updates()
            if updates_success:
                print("✅ Prenumeration på plånboksuppdateringar startad")

                # Hämta nuvarande plånböcker
                wallets = await wallet_handler.get_wallets()
                print(f"\n📊 Nuvarande plånböcker ({len(wallets)}):")
                for wallet in wallets:
                    print(
                        f"  {wallet['wallet_type']} {wallet['currency']}: {wallet['balance']}"
                    )

                # Vänta på uppdateringar i 30 sekunder
                print("\n⏳ Väntar på plånboksuppdateringar i 30 sekunder...")
                await asyncio.sleep(30)

            else:
                print("❌ Kunde inte starta prenumeration på plånboksuppdateringar")
        else:
            print("❌ WebSocket-autentisering misslyckades")

        # Stäng anslutning
        await bitfinex_ws.close()

    except Exception as e:
        print(f"❌ Fel i wallet_updates_example: {e}")


async def position_updates_example():
    """
    Exempel på hur man kan använda WSPositionHandler för att få positionsuppdateringar.
    """
    print("\n=== WebSocket Position Updates Example ===\n")

    try:
        # Skapa Bitfinex WebSocket-service
        bitfinex_ws = BitfinexWebSocketService()
        await bitfinex_ws.connect()

        # Skapa dummy Socket.IO-klient
        sio_client = DummySIOClient()

        # Skapa WSPositionHandler
        position_handler = WSPositionHandler(sio_client, bitfinex_ws)

        # Registrera callback för positionsuppdateringar
        def on_position_update(positions):
            print(f"📢 Positionsuppdatering mottagen: {len(positions)} positioner")
            for position in positions:
                position_type = (
                    "LONG"
                    if position.get("is_long", False)
                    else "SHORT" if position.get("is_short", False) else "NEUTRAL"
                )
                print(
                    f"  {position['symbol']} {position['status']} {position_type}: {position['amount']} @ {position.get('base_price', 'N/A')}"
                )

        position_handler.register_position_callback(on_position_update)

        # Autentisera och starta positionsuppdateringar
        print("🔑 Autentiserar WebSocket-anslutning...")
        auth_success = await position_handler.authenticate()
        if auth_success:
            print("✅ WebSocket-autentisering lyckades")

            # Starta positionsuppdateringar
            print("📡 Startar prenumeration på positionsuppdateringar...")
            updates_success = await position_handler.start_position_updates()
            if updates_success:
                print("✅ Prenumeration på positionsuppdateringar startad")

                # Hämta nuvarande positioner
                positions = await position_handler.get_positions()
                print(f"\n📊 Nuvarande positioner ({len(positions)}):")
                for position in positions:
                    position_type = (
                        "LONG"
                        if position.get("is_long", False)
                        else "SHORT" if position.get("is_short", False) else "NEUTRAL"
                    )
                    print(
                        f"  {position['symbol']} {position['status']} {position_type}: {position['amount']} @ {position.get('base_price', 'N/A')}"
                    )

                # Vänta på uppdateringar i 30 sekunder
                print("\n⏳ Väntar på positionsuppdateringar i 30 sekunder...")
                await asyncio.sleep(30)

            else:
                print("❌ Kunde inte starta prenumeration på positionsuppdateringar")
        else:
            print("❌ WebSocket-autentisering misslyckades")

        # Stäng anslutning
        await bitfinex_ws.close()

    except Exception as e:
        print(f"❌ Fel i position_updates_example: {e}")


async def main():
    """
    Huvudfunktion som kör exemplen.
    """
    print("🔒 Genesis Trading Bot - WebSocket Account Examples")
    print("==============================================")

    # Kör exempel på plånboksuppdateringar
    await wallet_updates_example()

    # Kör exempel på positionsuppdateringar
    await position_updates_example()

    print("\n✅ Exempel slutförda!")


if __name__ == "__main__":
    asyncio.run(main())
