# -*- coding: utf-8 -*-
"""Test för marknadsdata och API-endpoints (Bitfinex)."""

import asyncio
import os
import sys

import pytest
from dotenv import load_dotenv

# Lägg till rotmappen i Python-sökvägen för att hitta moduler
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.mark.asyncio
async def test_market_data_integration():
    """Testar marknadsdata-integration med Bitfinex."""
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

    # Testa candlestick-hämtning
    print("\n📈 Hämtar candlestick-data...")
    candles = await bitfinex_data.get_candles("tBTCUSD", "1m", 50)

    assert candles is not None, "Candles ska inte vara None"
    assert len(candles) > 0, "Candles ska ha data"

    print("✅ Candlestick-data hämtad framgångsrikt")
    print(f"   Antal candles: {len(candles)}")

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


@pytest.mark.asyncio
async def test_api_endpoints():
    """Testar API-endpoints för marknadsdata."""
    print("\n🌐 Testar API-endpoints...")

    # Importera FastAPI test client
    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)

    # Testa ticker endpoint
    print("📊 Testar /api/v2/market/ticker/tBTCUSD...")
    response = client.get("/api/v2/market/ticker/tBTCUSD")
    assert response.status_code == 200, f"Ticker endpoint fel: {response.status_code}"
    ticker_data = response.json()

    assert "last_price" in ticker_data, "Ticker response ska ha last_price"
    assert "symbol" in ticker_data, "Ticker response ska ha symbol"

    # Testa candles endpoint
    print("📈 Testar /api/v2/market/candles/tBTCUSD...")
    response = client.get("/api/v2/market/candles/tBTCUSD?timeframe=1m&limit=50")
    assert response.status_code == 200, f"Candles endpoint fel: {response.status_code}"
    candles_data = response.json()

    assert "candles_count" in candles_data, "Candles response ska ha candles_count"
    assert "strategy" in candles_data, "Candles response ska ha strategy"
    assert "signal" in candles_data["strategy"], "Strategy ska ha signal"

    # Testa metrics endpoint (root). Acceptera både öppet (200) och skyddat
    # (401/403)
    print("📈 Testar /metrics (root) ...")
    resp = client.get("/metrics")
    if resp.status_code == 200:
        body = resp.text
        assert "tradingbot_orders_total" in body
        # Efter några GET:ar borde request-latency finnas
        assert "tradingbot_request_latency_ms_count" in body
    else:
        assert resp.status_code in (
            401,
            403,
        ), f"Unexpected status for /metrics: {resp.status_code}"


# Manuell körning
async def main():
    print("🚀 Startar marknadsdata-integrationstester...")
    await test_market_data_integration()
    await test_api_endpoints()


if __name__ == "__main__":
    asyncio.run(main())
