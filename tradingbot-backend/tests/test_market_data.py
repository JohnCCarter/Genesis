"""
Test för marknadsdata-integration med Bitfinex.

Detta test validerar att vi kan hämta live marknadsdata från Bitfinex.
"""

import asyncio
import os
import sys

import pytest

# Lägg till rotmappen i Python-sökvägen för att hitta moduler
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv


@pytest.mark.asyncio
async def test_market_data_integration():
    """Testar marknadsdata-integration med Bitfinex."""
    try:
        # Ladda .env
        load_dotenv()

        print("🧪 Testar marknadsdata-integration...")

        # Testa data-service
        from services.bitfinex_data import bitfinex_data

        # Testa ticker-hämtning
        print("📊 Hämtar ticker-data...")
        ticker = await bitfinex_data.get_ticker("tBTCUSD")

        assert ticker is not None, "Ticker-data ska inte vara None"
        assert "symbol" in ticker, "Ticker ska ha symbol"
        assert "last_price" in ticker, "Ticker ska ha last_price"
        assert "bid" in ticker, "Ticker ska ha bid"
        assert "ask" in ticker, "Ticker ska ha ask"
        assert "volume" in ticker, "Ticker ska ha volume"

        print("✅ Ticker-data hämtad framgångsrikt")
        print(f"   Symbol: {ticker['symbol']}")
        print(f"   Last Price: ${ticker['last_price']:,.2f}")
        print(f"   Bid: ${ticker['bid']:,.2f}")
        print(f"   Ask: ${ticker['ask']:,.2f}")
        print(f"   Volume: {ticker['volume']:,.2f}")

        # Testa candlestick-hämtning
        print("\n📈 Hämtar candlestick-data...")
        candles = await bitfinex_data.get_candles("tBTCUSD", "1m", 50)

        assert candles is not None, "Candles ska inte vara None"
        assert len(candles) > 0, "Candles ska ha data"

        print("✅ Candlestick-data hämtad framgångsrikt")
        print(f"   Antal candles: {len(candles)}")
        print(f"   Senaste candle: {candles[0]}")

        # Testa strategiutvärdering med live data
        print("\n🎯 Testar strategiutvärdering med live data...")
        strategy_data = bitfinex_data.parse_candles_to_strategy_data(candles)

        from services.strategy import evaluate_strategy

        result = evaluate_strategy(strategy_data)

        assert "signal" in result, "Resultat ska ha signal"
        assert "rsi" in result, "Resultat ska ha rsi"
        assert "ema" in result, "Resultat ska ha ema"
        assert "atr" in result, "Resultat ska ha atr"
        assert "reason" in result, "Resultat ska ha reason"

        print("✅ Strategiutvärdering med live data slutförd")
        print(f"   Signal: {result['signal']}")
        print(f"   RSI: {result['rsi']}")
        print(f"   EMA: {result['ema']}")
        print(f"   ATR: {result['atr']}")
        print(f"   Reason: {result['reason']}")

        print("\n🎉 Alla marknadsdata-tester godkända!")

    except Exception as e:
        pytest.fail(f"Test-fel: {e}")


@pytest.mark.asyncio
async def test_api_endpoints():
    """Testar API-endpoints för marknadsdata."""
    try:
        print("\n🌐 Testar API-endpoints...")

        # Importera FastAPI test client
        from fastapi.testclient import TestClient

        from main import app

        client = TestClient(app)

        # Testa ticker endpoint
        print("📊 Testar /api/v2/market/ticker/tBTCUSD...")
        response = client.get("/api/v2/market/ticker/tBTCUSD")

        assert (
            response.status_code == 200
        ), f"Ticker endpoint fel: {response.status_code}"
        ticker_data = response.json()

        assert "last_price" in ticker_data, "Ticker response ska ha last_price"
        assert "symbol" in ticker_data, "Ticker response ska ha symbol"

        print("✅ Ticker endpoint fungerar")
        print(f"   Last Price: ${ticker_data['last_price']:,.2f}")

        # Testa candles endpoint
        print("📈 Testar /api/v2/market/candles/tBTCUSD...")
        response = client.get("/api/v2/market/candles/tBTCUSD?timeframe=1m&limit=50")

        assert (
            response.status_code == 200
        ), f"Candles endpoint fel: {response.status_code}"
        candles_data = response.json()

        assert "candles_count" in candles_data, "Candles response ska ha candles_count"
        assert "strategy" in candles_data, "Candles response ska ha strategy"
        assert "signal" in candles_data["strategy"], "Strategy ska ha signal"

        print("✅ Candles endpoint fungerar")
        print(f"   Candles: {candles_data['candles_count']}")
        print(f"   Signal: {candles_data['strategy']['signal']}")

        print("🎉 Alla API-endpoint-tester godkända!")

    except Exception as e:
        pytest.fail(f"API-test fel: {e}")


# Behåll den ursprungliga main-funktionen för manuell körning
async def main():
    """Huvudfunktion för tester."""
    print("🚀 Startar marknadsdata-integrationstester...")

    # Testa data-service
    await test_market_data_integration()

    # Testa API-endpoints
    await test_api_endpoints()

    print("\n🎉 Alla tester godkända! Marknadsdata-integration fungerar.")


if __name__ == "__main__":
    asyncio.run(main())
