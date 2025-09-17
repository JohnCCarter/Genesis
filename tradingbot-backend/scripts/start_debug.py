#!/usr/bin/env python3
"""
Debug Start Script - TradingBot Backend

Starta boten med debug-flags för att diagnostisera hängningsproblem.
"""

import os
import sys
import subprocess
from pathlib import Path

# Lägg till project root i path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def set_debug_environment():
    """Sätt debug environment variables."""
    debug_env = {
        # Asyncio debug
        "PYTHONASYNCIODEBUG": "1",
        "DEBUG_ASYNC": "true",
        # Market data mode
        "MARKETDATA_MODE": "rest_only",  # Force REST för att undvika WS-problem
        # UI push
        "UI_PUSH_ENABLED": "false",  # Stäng av UI push för att undvika backpressure
        # Trading mode
        "TRADING_MODE": "read_only",  # Read-only mode för att undvika trading-problem
        # Rate limiting (mer permissivt)
        "BITFINEX_RATE_LIMIT_ENABLED": "false",  # Stäng av rate limiting temporärt
        # WebSocket
        "WS_CONNECT_ON_START": "false",  # Stäng av WS vid startup
        # Logging
        "LOG_LEVEL": "DEBUG",
    }

    for key, value in debug_env.items():
        os.environ[key] = value
        print(f"🔧 {key}={value}")


def start_with_debug():
    """Starta boten med debug-flags."""
    print("🚀 Startar TradingBot med debug-flags...")
    print("=" * 50)

    # Sätt debug environment
    set_debug_environment()

    print("\n📋 Debug-konfiguration:")
    print("  - Asyncio debug: AKTIVERAT")
    print("  - Market data: REST-only")
    print("  - UI push: AVSTÄNGT")
    print("  - Trading: Read-only")
    print("  - Rate limiting: AVSTÄNGT")
    print("  - WebSocket: AVSTÄNGT vid startup")
    print("  - Logging: DEBUG")

    print("\n🔍 Debug endpoints tillgängliga:")
    print("  - GET /api/v2/debug/tasks - Dump asyncio tasks")
    print("  - GET /api/v2/debug/threads - Dump threads")
    print("  - GET /api/v2/debug/rate_limiter - Rate limiter status")
    print("  - GET /api/v2/debug/market_data - Market data status")
    print("  - GET /api/v2/debug/risk_guards - Risk guards status")
    print("  - GET /api/v2/debug/websocket - WebSocket status")

    print("\n🧪 Test-script tillgängligt:")
    print("  - python scripts/test_isolation.py")

    print("\n" + "=" * 50)
    print("Startar uvicorn...")

    # Starta uvicorn med debug-flags
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--reload",
        "--log-level",
        "debug",
    ]

    try:
        subprocess.run(cmd, cwd=project_root, check=True)
    except KeyboardInterrupt:
        print("\n🛑 Stoppad av användare")
    except Exception as e:
        print(f"\n❌ Fel vid start: {e}")


if __name__ == "__main__":
    start_with_debug()
