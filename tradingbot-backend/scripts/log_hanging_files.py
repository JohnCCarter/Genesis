#!/usr/bin/env python3
"""
Logga kritiska filer som kan orsaka hängningar i TradingBot.
"""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# Lägg till projektets root i Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import get_logger

logger = get_logger(__name__)

# Konfigurera detaljerad logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('hanging_files_debug.log')],
)

# Lista över kritiska filer som kan orsaka hängningar
CRITICAL_FILES = [
    "services/bitfinex_websocket.py",
    "services/risk_guards.py",
    "services/market_data_facade.py",
    "services/ws_first_data_service.py",
    "services/performance.py",
    "utils/advanced_rate_limiter.py",
    "ws/manager.py",
    "ws/auth.py",
    "ws/position_handler.py",
    "ws/wallet_handler.py",
    "ws/order_handler.py",
    "rest/routes.py",
    "main.py",
]


async def log_file_analysis():
    """Analysera och logga kritiska filer för hängningsproblem."""

    logger.info("🔍 Börjar analys av kritiska filer för hängningsproblem...")

    for file_path in CRITICAL_FILES:
        full_path = project_root / file_path

        if not full_path.exists():
            logger.warning(f"⚠️ Fil saknas: {file_path}")
            continue

        logger.info(f"📁 Analyserar: {file_path}")

        try:
            with open(full_path, encoding='utf-8') as f:
                content = f.read()

            # Analysera potentiella problem
            issues = []

            # 1. Kontrollera för oändliga loopar
            if 'while True:' in content:
                issues.append("🔄 Oändlig while-loop")
            if 'while 1:' in content:
                issues.append("🔄 Oändlig while-loop (while 1)")

            # 2. Kontrollera för blocking calls utan timeout
            blocking_patterns = [
                'requests.get(',
                'requests.post(',
                'requests.put(',
                'requests.delete(',
                'time.sleep(',
                'asyncio.sleep(',
                'await asyncio.sleep(',
                'await websocket.recv()',
                'websocket.recv()',
                'await websocket.send(',
                'websocket.send(',
            ]

            for pattern in blocking_patterns:
                if pattern in content and 'timeout=' not in content:
                    issues.append(f"⏰ Potentiell blocking call utan timeout: {pattern}")

            # 3. Kontrollera för WebSocket race conditions
            if 'listen_for_messages' in content:
                issues.append("🔌 WebSocket message listener")
            if 'websocket.recv()' in content:
                issues.append("📡 WebSocket recv() call")
            if 'asyncio.create_task' in content:
                issues.append("🚀 AsyncIO task creation")

            # 4. Kontrollera för equity/performance calls
            if 'compute_current_equity' in content:
                issues.append("💰 Equity computation")
            if 'get_current_equity' in content:
                issues.append("💵 Current equity retrieval")

            # 5. Kontrollera för rate limiting
            if 'rate_limiter' in content:
                issues.append("🚦 Rate limiter usage")
            if 'semaphore' in content:
                issues.append("🔒 Semaphore usage")

            # 6. Kontrollera för authentication
            if 'authenticate' in content:
                issues.append("🔐 Authentication logic")
            if 'auth' in content:
                issues.append("🔑 Auth handling")

            # 7. Kontrollera för market data
            if 'get_ticker' in content:
                issues.append("📊 Ticker data retrieval")
            if 'get_candles' in content:
                issues.append("🕯️ Candle data retrieval")

            # 8. Kontrollera för error handling
            if 'except Exception:' in content:
                issues.append("⚠️ Generic exception handling")
            if 'except:' in content:
                issues.append("❌ Bare except clause")

            # 9. Kontrollera för timeout handling
            if 'timeout=' in content:
                issues.append("⏱️ Timeout handling present")
            if 'asyncio.wait_for' in content:
                issues.append("⏳ AsyncIO wait_for usage")

            # 10. Kontrollera för circuit breaker
            if 'circuit_breaker' in content:
                issues.append("🔌 Circuit breaker logic")
            if 'circuit_breaker' in content:
                issues.append("🛡️ Circuit breaker protection")

            # Logga resultat
            if issues:
                logger.warning(f"🚨 {file_path} - Potentiella problem:")
                for issue in issues:
                    logger.warning(f"   {issue}")
            else:
                logger.info(f"✅ {file_path} - Inga uppenbara problem")

        except Exception as e:
            logger.error(f"❌ Fel vid analys av {file_path}: {e}")

    logger.info("🏁 Filanalys slutförd!")


async def test_critical_services():
    """Testa kritiska services för hängningsproblem."""

    logger.info("🧪 Testar kritiska services...")

    # Test 1: Risk Guards Service
    try:
        logger.info("🔍 Testar RiskGuardsService...")
        from services.risk_guards import risk_guards

        start_time = time.perf_counter()
        equity = risk_guards._get_current_equity()
        duration = (time.perf_counter() - start_time) * 1000

        logger.info(f"✅ RiskGuards equity: ${equity:.2f} ({duration:.1f}ms)")

        if duration > 5000:
            logger.warning(f"⚠️ RiskGuards equity-hämtning tog {duration:.1f}ms (långsam)")

    except Exception as e:
        logger.error(f"❌ RiskGuards test misslyckades: {e}")

    # Test 2: Market Data Facade
    try:
        logger.info("🔍 Testar MarketDataFacade...")
        from services.market_data_facade import get_market_data

        facade = get_market_data()

        start_time = time.perf_counter()
        ticker = await facade.get_ticker("BTCUSD")
        duration = (time.perf_counter() - start_time) * 1000

        logger.info(f"✅ MarketData ticker: {ticker is not None} ({duration:.1f}ms)")

        if duration > 1000:
            logger.warning(f"⚠️ MarketData ticker-hämtning tog {duration:.1f}ms (långsam)")

    except Exception as e:
        logger.error(f"❌ MarketData test misslyckades: {e}")

    # Test 3: Rate Limiter
    try:
        logger.info("🔍 Testar AdvancedRateLimiter...")
        from utils.advanced_rate_limiter import get_advanced_rate_limiter

        limiter = get_advanced_rate_limiter()

        start_time = time.perf_counter()
        await limiter.wait_if_needed("test/endpoint")
        duration = (time.perf_counter() - start_time) * 1000

        logger.info(f"✅ RateLimiter wait: {duration:.1f}ms")

        if duration > 1000:
            logger.warning(f"⚠️ RateLimiter wait tog {duration:.1f}ms (långsam)")

    except Exception as e:
        logger.error(f"❌ RateLimiter test misslyckades: {e}")

    # Test 4: WebSocket Service
    try:
        logger.info("🔍 Testar BitfinexWebSocketService...")
        from services.bitfinex_websocket import BitfinexWebSocketService

        ws_service = BitfinexWebSocketService()

        # Testa endast att skapa service, inte ansluta
        logger.info("✅ WebSocket service skapad utan problem")

    except Exception as e:
        logger.error(f"❌ WebSocket service test misslyckades: {e}")


async def main():
    """Huvudfunktion för filanalys."""

    logger.info("🚀 Startar hanging files analys...")

    # Analysera filer
    await log_file_analysis()

    # Testa services
    await test_critical_services()

    logger.info("🎯 Analys slutförd! Se hanging_files_debug.log för detaljer.")


if __name__ == "__main__":
    asyncio.run(main())
