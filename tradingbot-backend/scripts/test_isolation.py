#!/usr/bin/env python3
"""
Isolation Test Script - TradingBot Backend

Testa olika isolerings-scenarier för att identifiera hängningsproblem.
"""

import asyncio
import os
import sys
import time
from typing import Dict, Any

# Lägg till project root i path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Settings
from utils.logger import get_logger

logger = get_logger(__name__)


async def test_market_data_rest_only():
    """Testa market data med REST-only mode."""
    logger.info("🧪 Testar market data REST-only mode...")

    # Sätt environment flag
    os.environ["MARKETDATA_MODE"] = "rest_only"

    try:
        from services.market_data_facade import get_market_data

        facade = get_market_data()

        # Testa ticker
        start_time = time.perf_counter()
        ticker = await facade.get_ticker("BTCUSD")
        duration = (time.perf_counter() - start_time) * 1000

        logger.info(f"✅ REST-only ticker: {ticker is not None} ({duration:.1f}ms)")
        return ticker is not None

    except Exception as e:
        logger.error(f"❌ REST-only test misslyckades: {e}")
        return False


async def test_rate_limiter_status():
    """Testa rate limiter status."""
    logger.info("🧪 Testar rate limiter status...")

    try:
        from utils.advanced_rate_limiter import get_advanced_rate_limiter

        limiter = get_advanced_rate_limiter()
        stats = limiter.get_stats()

        logger.info(f"✅ Rate limiter stats: {len(stats)} buckets")
        for endpoint_type, stat in stats.items():
            tokens = stat.get("tokens_available", 0)
            capacity = stat.get("capacity", 0)
            logger.info(f"   {endpoint_type}: {tokens:.1f}/{capacity} tokens")

        return True

    except Exception as e:
        logger.error(f"❌ Rate limiter test misslyckades: {e}")
        return False


async def test_websocket_status():
    """Testa WebSocket status."""
    logger.info("🧪 Testar WebSocket status...")

    try:
        from services.bitfinex_websocket import bitfinex_ws

        logger.info(f"✅ WebSocket connected: {bitfinex_ws.is_connected}")
        logger.info(f"✅ WebSocket authenticated: {getattr(bitfinex_ws, '_authenticated', False)}")

        return bitfinex_ws.is_connected

    except Exception as e:
        logger.error(f"❌ WebSocket test misslyckades: {e}")
        return False


async def test_risk_guards():
    """Testa risk guards status."""
    logger.info("🧪 Testar risk guards...")

    try:
        from services.risk_guards import risk_guards

        status = risk_guards.get_guards_status()

        logger.info(f"✅ Risk guards status: {len(status.get('guards', {}))} guards")
        logger.info(f"✅ Current equity: ${status.get('current_equity', 0):.2f}")

        return True

    except Exception as e:
        logger.error(f"❌ Risk guards test misslyckades: {e}")
        return False


async def test_debug_endpoints():
    """Testa debug endpoints."""
    logger.info("🧪 Testar debug endpoints...")

    try:
        import httpx

        base_url = "http://localhost:8000"

        # Testa task dump
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/api/v2/debug/tasks", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Task dump: {data.get('count', 0)} tasks")
            else:
                logger.warning(f"⚠️ Task dump failed: {response.status_code}")

            # Testa rate limiter dump
            response = await client.get(f"{base_url}/api/v2/debug/rate_limiter", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Rate limiter dump: {len(data.get('stats', {}))} buckets")
            else:
                logger.warning(f"⚠️ Rate limiter dump failed: {response.status_code}")

        return True

    except Exception as e:
        logger.error(f"❌ Debug endpoints test misslyckades: {e}")
        return False


async def run_isolation_tests():
    """Kör alla isoleringstester."""
    logger.info("🚀 Startar isoleringstester...")

    tests = [
        ("Rate Limiter Status", test_rate_limiter_status),
        ("WebSocket Status", test_websocket_status),
        ("Risk Guards", test_risk_guards),
        ("Market Data REST-only", test_market_data_rest_only),
        ("Debug Endpoints", test_debug_endpoints),
    ]

    results = {}

    for test_name, test_func in tests:
        logger.info(f"\n--- {test_name} ---")
        try:
            result = await test_func()
            results[test_name] = result
            logger.info(f"{'✅' if result else '❌'} {test_name}: {'PASS' if result else 'FAIL'}")
        except Exception as e:
            logger.error(f"❌ {test_name}: ERROR - {e}")
            results[test_name] = False

        # Kort paus mellan tester
        await asyncio.sleep(0.5)

    # Sammanfattning
    logger.info("\n" + "=" * 50)
    logger.info("SAMMANFATTNING:")
    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"  {test_name}: {status}")

    logger.info(f"\nTotalt: {passed}/{total} tester passerade")

    if passed == total:
        logger.info("🎉 Alla tester passerade!")
    else:
        logger.warning(f"⚠️ {total - passed} tester misslyckades")

    return results


if __name__ == "__main__":
    # Kör tester
    asyncio.run(run_isolation_tests())
