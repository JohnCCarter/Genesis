#!/usr/bin/env python3
"""
Test Hanging Fixes - TradingBot Backend

Testa specifikt de fixes vi implementerat för hängningsproblem.
"""

import asyncio
import os
import sys
import time
from typing import Dict, Any

# Lägg till project root i path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import get_logger

logger = get_logger(__name__)


async def test_websocket_no_race_condition():
    """Testa att WebSocket inte skapar race conditions."""
    logger.info("🧪 Testar WebSocket race condition fix...")

    try:
        from services.bitfinex_websocket import bitfinex_ws

        # Försök ansluta flera gånger snabbt
        tasks = []
        for _i in range(3):
            task = asyncio.create_task(bitfinex_ws.connect())
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Kontrollera att vi inte får race condition errors
        race_condition_errors = 0
        for result in results:
            if isinstance(result, Exception):
                if "recv while another coroutine" in str(result):
                    race_condition_errors += 1

        logger.info(f"✅ WebSocket race condition test: {race_condition_errors} errors")
        return race_condition_errors == 0

    except Exception as e:
        logger.error(f"❌ WebSocket race condition test misslyckades: {e}")
        return False


async def test_risk_guards_equity_timeout():
    """Testa att risk guards equity-hämtning inte hänger."""
    logger.info("🧪 Testar risk guards equity timeout fix...")

    try:
        from services.risk_guards import risk_guards

        start_time = time.perf_counter()

        # Testa equity-hämtning med timeout
        equity = risk_guards._get_current_equity()

        duration = (time.perf_counter() - start_time) * 1000

        logger.info(f"✅ Risk guards equity: ${equity:.2f} ({duration:.1f}ms)")

        # Borde vara snabb (<5s) och inte hänga
        return duration < 5000

    except Exception as e:
        logger.error(f"❌ Risk guards equity test misslyckades: {e}")
        return False


async def test_market_data_timeout():
    """Testa att market data har timeout och fallback."""
    logger.info("🧪 Testar market data timeout fix...")

    try:
        from services.market_data_facade import get_market_data

        facade = get_market_data()

        # Testa med timeout
        start_time = time.perf_counter()
        ticker = await facade.get_ticker("BTCUSD")
        duration = (time.perf_counter() - start_time) * 1000

        logger.info(
            f"✅ Market data timeout test: {ticker is not None} ({duration:.1f}ms)"
        )

        # Borde vara snabb (<1s) med timeout
        return duration < 1000 and ticker is not None

    except Exception as e:
        logger.error(f"❌ Market data timeout test misslyckades: {e}")
        return False


async def test_rate_limiter_no_deadlock():
    """Testa att rate limiter inte skapar deadlock."""
    logger.info("🧪 Testar rate limiter deadlock fix...")

    try:
        from utils.advanced_rate_limiter import get_advanced_rate_limiter

        limiter = get_advanced_rate_limiter()

        # Testa flera samtidiga anrop
        async def test_endpoint(endpoint: str):
            async with limiter.limit(endpoint):
                await asyncio.sleep(0.1)  # Simulera arbete
                return True

        tasks = []
        for _i in range(5):
            task = asyncio.create_task(test_endpoint("ticker"))
            tasks.append(task)

        start_time = time.perf_counter()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        duration = (time.perf_counter() - start_time) * 1000

        success_count = sum(1 for r in results if r is True)

        logger.info(
            f"✅ Rate limiter deadlock test: {success_count}/5 success ({duration:.1f}ms)"
        )

        # Borde inte hänga och alla ska lyckas
        return success_count == 5 and duration < 2000

    except Exception as e:
        logger.error(f"❌ Rate limiter deadlock test misslyckades: {e}")
        return False


async def run_hanging_fixes_tests():
    """Kör alla hängningsfix-tester."""
    logger.info("🚀 Startar hängningsfix-tester...")

    tests = [
        ("WebSocket Race Condition", test_websocket_no_race_condition),
        ("Risk Guards Equity Timeout", test_risk_guards_equity_timeout),
        ("Market Data Timeout", test_market_data_timeout),
        ("Rate Limiter Deadlock", test_rate_limiter_no_deadlock),
    ]

    results = {}

    for test_name, test_func in tests:
        logger.info(f"\n--- {test_name} ---")
        try:
            result = await test_func()
            results[test_name] = result
            logger.info(
                f"{'✅' if result else '❌'} {test_name}: {'PASS' if result else 'FAIL'}"
            )
        except Exception as e:
            logger.error(f"❌ {test_name}: ERROR - {e}")
            results[test_name] = False

        # Kort paus mellan tester
        await asyncio.sleep(0.5)

    # Sammanfattning
    logger.info("\n" + "=" * 50)
    logger.info("HÄNGNINGSFIX SAMMANFATTNING:")
    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"  {test_name}: {status}")

    logger.info(f"\nTotalt: {passed}/{total} fixes fungerar")

    if passed == total:
        logger.info("🎉 Alla hängningsfix fungerar!")
    else:
        logger.warning(f"⚠️ {total - passed} fixes behöver mer arbete")

    return results


if __name__ == "__main__":
    # Kör tester
    asyncio.run(run_hanging_fixes_tests())
