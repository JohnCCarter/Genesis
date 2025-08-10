"""
Trading Integration Example - TradingBot Backend

Detta skript visar hur man använder trading_integration-modulen för att integrera
olika delar av tradingboten för att skapa en komplett tradingfunktionalitet.
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Any, Dict

# Lägg till projektets rotmapp i Python-sökvägen
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.trading_integration import trading_integration
from utils.logger import get_logger

logger = get_logger(__name__)


async def signal_callback(result: Dict[str, Any]):
    """Callback-funktion för trading-signaler."""
    symbol = result.get("symbol", "unknown")
    signal = result.get("signal", "UNKNOWN")
    price = result.get("current_price", 0)
    reason = result.get("reason", "")

    print(f"\n=== Ny Trading Signal ===")
    print(f"Symbol: {symbol}")
    print(f"Signal: {signal}")
    print(f"Pris: ${price:,.2f}")
    print(f"Anledning: {reason}")

    # Om ordern utfördes, visa resultatet
    if "trade_result" in result:
        trade_result = result["trade_result"]
        if trade_result["success"]:
            print(f"Order lagd: {trade_result['message']}")
            if "order" in trade_result and trade_result["order"]:
                print(f"Order-ID: {trade_result['order']}")
        else:
            print(f"Order misslyckades: {trade_result['message']}")


async def initialize_trading_example():
    """Exempel på hur man initialiserar trading-integrationen."""
    try:
        print("\n=== Initialiserar Trading Integration ===")
        await trading_integration.initialize()

        # Hämta kontosammanfattning
        summary = await trading_integration.get_account_summary()

        print("\n=== Kontosammanfattning ===")
        print(f"Totalt saldo (USD): ${summary['total_balance_usd']:,.2f}")
        print(f"Margin-saldo: {summary['margin_balance']:,.2f}")
        print(f"Orealiserad vinst/förlust: {summary['unrealized_pl']:,.2f}")
        print(f"Hävstång: {summary['leverage']}x")
        print(f"Margin-nivå: {summary['margin_level']}")
        print(f"Margin-status: {summary['margin_status']}")
        print(f"Öppna positioner: {summary['open_positions']}")
        print(f"Totalt positionsvärde: ${summary['total_position_value']:,.2f}")

    except Exception as e:
        logger.error(f"Fel vid initialisering av trading-integration: {e}")
        print(f"Fel: {e}")


async def evaluate_trading_opportunity_example():
    """Exempel på hur man utvärderar en tradingmöjlighet."""
    try:
        symbol = "tBTCUSD"

        print(f"\n=== Utvärderar Trading-möjlighet för {symbol} ===")
        result = await trading_integration.evaluate_trading_opportunity(symbol)

        print(f"Symbol: {result['symbol']}")
        print(f"Signal: {result['signal']}")
        print(f"Pris: ${result.get('current_price', 0):,.2f}")
        print(f"Anledning: {result['reason']}")
        print(f"RSI: {result.get('rsi', 'N/A')}")
        print(f"EMA: {result.get('ema', 'N/A')}")
        print(f"Risk-nivå: {result.get('risk_level', 'UNKNOWN')}")
        print(f"Kan handla: {result.get('can_trade', False)}")

        # Om vi kan handla, fråga användaren om vi ska utföra signalen
        if result.get("can_trade", False) and result["signal"] in ["BUY", "SELL"]:
            response = input(
                f"\nVill du utföra {result['signal']} för {symbol}? (y/n): "
            )

            if response.lower() == "y":
                trade_result = await trading_integration.execute_trading_signal(
                    symbol, result
                )

                print("\n=== Trading Resultat ===")
                if trade_result["success"]:
                    print(f"Order lagd: {trade_result['message']}")
                    if "order" in trade_result and trade_result["order"]:
                        print(f"Order-ID: {trade_result['order']}")
                else:
                    print(f"Order misslyckades: {trade_result['message']}")

    except Exception as e:
        logger.error(f"Fel vid utvärdering av trading-möjlighet: {e}")
        print(f"Fel: {e}")


async def automated_trading_example():
    """Exempel på hur man använder automatiserad trading."""
    try:
        symbol = "tBTCUSD"

        print(f"\n=== Startar Automatiserad Trading för {symbol} ===")
        await trading_integration.start_automated_trading(symbol, signal_callback)

        print(f"Automatiserad trading startad för {symbol}")
        print("Väntar på signaler... (tryck Ctrl+C för att avbryta)")

        # Vänta på signaler (i ett riktigt scenario skulle detta köras kontinuerligt)
        try:
            await asyncio.sleep(60)  # Vänta 60 sekunder
        except asyncio.CancelledError:
            pass

        # Stoppa automatiserad trading
        print(f"\n=== Stoppar Automatiserad Trading för {symbol} ===")
        await trading_integration.stop_automated_trading(symbol)

        print(f"Automatiserad trading stoppad för {symbol}")

    except Exception as e:
        logger.error(f"Fel vid automatiserad trading: {e}")
        print(f"Fel: {e}")


async def run_all_examples():
    """Kör alla exempel i sekvens."""
    print("\n=== Kör alla trading integration examples ===\n")

    await initialize_trading_example()
    await evaluate_trading_opportunity_example()

    # Kommentera bort denna om du inte vill köra automatiserad trading
    # await automated_trading_example()

    print("\n=== Alla examples körda ===\n")


if __name__ == "__main__":
    try:
        asyncio.run(run_all_examples())
    except KeyboardInterrupt:
        print("\nAvbruten av användaren")
    except Exception as e:
        logger.error(f"Oväntat fel: {e}")
        print(f"Oväntat fel: {e}")
