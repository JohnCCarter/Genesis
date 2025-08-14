"""
Account Examples - TradingBot Backend

Detta skript innehåller exempel på hur man använder de olika account-relaterade endpoints
som finns tillgängliga i tradingboten.
"""

import asyncio
import os
import sys

from rest.margin import get_leverage, get_margin_info
from rest.order_history import get_ledgers, get_order_trades, get_orders_history, get_trades_history
from rest.positions import get_position_by_symbol, get_positions
from rest.wallet import get_wallet_by_type_and_currency, get_wallets
from utils.logger import get_logger

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = get_logger(__name__)


async def get_wallets_example():
    """Exempel på hur man hämtar plånboksinformation."""
    try:
        # Hämta alla plånböcker
        wallets = await get_wallets()

        print("\n=== Plånböcker ===")
        for wallet in wallets:
            print(
                f"{wallet.wallet_type.upper()} - {wallet.currency}: {wallet.balance} "
                + f"(Tillgängligt: {wallet.available_balance if wallet.available_balance is not None else wallet.balance})"
            )

        # Hämta en specifik plånbok
        btc_exchange = await get_wallet_by_type_and_currency("exchange", "BTC")
        if btc_exchange:
            print(f"\nBTC Exchange Wallet: {btc_exchange.balance} BTC")
        else:
            print("\nIngen BTC Exchange Wallet hittad")

    except Exception as e:
        logger.error(f"Fel vid hämtning av plånböcker: {e}")
        print(f"Fel: {e}")


async def get_positions_example():
    """Exempel på hur man hämtar positionsinformation."""
    try:
        # Hämta alla positioner
        positions = await get_positions()

        print("\n=== Positioner ===")
        if positions:
            for position in positions:
                direction = "LONG" if position.amount > 0 else "SHORT"
                print(
                    f"{position.symbol} {direction}: {abs(position.amount)} @ {position.base_price} "
                    + f"(PnL: {position.profit_loss})"
                )
        else:
            print("Inga aktiva positioner")

        # Hämta en specifik position
        btc_position = await get_position_by_symbol("tBTCUSD")
        if btc_position:
            print(f"\nBTC Position: {btc_position.amount} @ {btc_position.base_price}")
        else:
            print("\nIngen BTC position hittad")

    except Exception as e:
        logger.error(f"Fel vid hämtning av positioner: {e}")
        print(f"Fel: {e}")


async def get_margin_info_example():
    """Exempel på hur man hämtar margin-information."""
    try:
        # Hämta margin info
        try:
            margin_info = await get_margin_info()

            print("\n=== Margin Information ===")
            print(f"Margin Balance: {margin_info.margin_balance}")
            print(f"Unrealized PL: {margin_info.unrealized_pl}")
            print(f"Net Value: {margin_info.net_value}")
            print(f"Required Margin: {margin_info.required_margin}")

            # Hämta hävstång
            leverage = await get_leverage()
            print(f"Current Leverage: {leverage}x")
        except Exception as e:
            print("\n=== Margin Information ===")
            print(f"Kunde inte hämta margin-information: {e}")
            print(
                "OBS: Detta kan bero på att ditt konto inte har margin aktiverat eller att du använder ett testkonto."
            )

    except Exception as e:
        logger.error(f"Fel vid hämtning av margin-information: {e}")
        print(f"Fel: {e}")


async def get_order_history_example():
    """Exempel på hur man hämtar orderhistorik."""
    try:
        try:
            # Hämta de senaste 10 ordrarna
            orders = await get_orders_history(10)

            print("\n=== Orderhistorik (10 senaste) ===")
            if orders:
                for order in orders:
                    created = order.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    print(
                        f"{created} - {order.symbol} {order.type}: {order.amount} @ {order.price} ({order.status})"
                    )
            else:
                print("Ingen orderhistorik hittad")

            # Om det finns ordrar, hämta trades för den första
            if orders:
                first_order = orders[0]
                trades = await get_order_trades(first_order.id)

                print(f"\n=== Trades för Order {first_order.id} ===")
                if trades:
                    for trade in trades:
                        executed = trade.executed_at.strftime("%Y-%m-%d %H:%M:%S")
                        print(
                            f"{executed} - {trade.amount} @ {trade.price} (Fee: {trade.fee} {trade.fee_currency})"
                        )
                else:
                    print(f"Inga trades hittade för order {first_order.id}")
        except Exception as e:
            print("\n=== Orderhistorik ===")
            print(f"Kunde inte hämta orderhistorik: {e}")
            print(
                "OBS: Detta kan bero på att ditt konto inte har några ordrar eller att du använder ett testkonto."
            )

    except Exception as e:
        logger.error(f"Fel vid hämtning av orderhistorik: {e}")
        print(f"Fel: {e}")


async def get_trades_history_example():
    """Exempel på hur man hämtar handelshistorik."""
    try:
        try:
            # Hämta de senaste 10 trades
            trades = await get_trades_history(limit=10)

            print("\n=== Handelshistorik (10 senaste) ===")
            if trades:
                for trade in trades:
                    executed = trade.executed_at.strftime("%Y-%m-%d %H:%M:%S")
                    print(
                        f"{executed} - {trade.symbol}: {trade.amount} @ {trade.price} (Fee: {trade.fee} {trade.fee_currency})"
                    )
            else:
                print("Ingen handelshistorik hittad")

            # Hämta trades för en specifik symbol
            btc_trades = await get_trades_history(symbol="tBTCUSD", limit=5)

            print("\n=== BTC/USD Trades (5 senaste) ===")
            if btc_trades:
                for trade in btc_trades:
                    executed = trade.executed_at.strftime("%Y-%m-%d %H:%M:%S")
                    print(
                        f"{executed} - {trade.amount} @ {trade.price} (Fee: {trade.fee} {trade.fee_currency})"
                    )
            else:
                print("Inga BTC/USD trades hittade")
        except Exception as e:
            print("\n=== Handelshistorik ===")
            print(f"Kunde inte hämta handelshistorik: {e}")
            print(
                "OBS: Detta kan bero på att ditt konto inte har några trades eller att du använder ett testkonto."
            )

    except Exception as e:
        logger.error(f"Fel vid hämtning av handelshistorik: {e}")
        print(f"Fel: {e}")


async def get_ledgers_example():
    """Exempel på hur man hämtar ledger-poster."""
    try:
        try:
            # Hämta de senaste 10 ledger-posterna
            ledgers = await get_ledgers(limit=10)

            print("\n=== Ledger (10 senaste) ===")
            if ledgers:
                for ledger in ledgers:
                    created = ledger.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    print(
                        f"{created} - {ledger.wallet_type} {ledger.currency}: {ledger.amount} (Balance: {ledger.balance}) - {ledger.description}"
                    )
            else:
                print("Inga ledger-poster hittade")

            # Hämta ledger-poster för en specifik valuta
            usd_ledgers = await get_ledgers(currency="USD", limit=5)

            print("\n=== USD Ledger (5 senaste) ===")
            if usd_ledgers:
                for ledger in usd_ledgers:
                    created = ledger.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    print(
                        f"{created} - {ledger.wallet_type}: {ledger.amount} (Balance: {ledger.balance}) - {ledger.description}"
                    )
            else:
                print("Inga USD ledger-poster hittade")
        except Exception as e:
            print("\n=== Ledger ===")
            print(f"Kunde inte hämta ledger-poster: {e}")
            print(
                "OBS: Detta kan bero på att ditt konto inte har några ledger-poster eller att du använder ett testkonto."
            )

    except Exception as e:
        logger.error(f"Fel vid hämtning av ledger: {e}")
        print(f"Fel: {e}")


async def run_all_examples():
    """Kör alla exempel i sekvens."""
    print("\n=== Kör alla account examples ===\n")

    await get_wallets_example()
    await get_positions_example()
    await get_margin_info_example()
    await get_order_history_example()
    await get_trades_history_example()
    await get_ledgers_example()

    print("\n=== Alla examples körda ===\n")


if __name__ == "__main__":
    asyncio.run(run_all_examples())
