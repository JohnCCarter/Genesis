#!/usr/bin/env python3
"""
Kontrollera tid och datum på MCP-tabellen

Testar att Supabase MCP-server returnerar korrekta timestamps
och att datum-hantering fungerar rätt.
"""

import asyncio
from datetime import UTC, datetime
import os
import sys

# Lägg till backend-mappen i Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "tradingbot-backend"))

from config.settings import Settings
from services.mcp_client import GenesisMCPTools, MCPClient


async def check_mcp_timestamps():
    """Kontrollera tid och datum på MCP-data"""
    print("🕐 Kontrollerar tid och datum på MCP-tabellen...")
    print("=" * 60)

    try:
        # Kontrollera inställningar
        settings = Settings()
        print(f"📋 MCP_SERVER_URL: {settings.MCP_SERVER_URL}")

        # Hämta aktuell tid
        now_utc = datetime.now(UTC)
        now_local = datetime.now()
        print(f"🕐 Lokal tid: {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"🕐 UTC tid: {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print()

        # Test 1: Kontrollera trading status timestamps
        print("1. 📊 Kontrollerar trading status timestamps...")
        mcp_tools = GenesisMCPTools()

        status = await mcp_tools.get_trading_status()
        print(f"   📊 Trading status: {status}")

        # Test 2: Kontrollera performance metrics timestamps
        print("\n2. 📈 Kontrollerar performance metrics timestamps...")
        metrics = await mcp_tools.get_performance_metrics("1d")
        print(f"   📈 Performance metrics: {metrics}")

        if "last_updated" in metrics:
            last_updated = metrics["last_updated"]
            print(f"   🕐 Last updated: {last_updated}")

            # Konvertera till datetime för jämförelse
            try:
                mcp_time = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                time_diff = abs((now_utc - mcp_time).total_seconds())
                print(f"   ⏱️ Tidsskillnad från nu: {time_diff:.1f} sekunder")

                if time_diff < 60:
                    print("   ✅ Timestamp är färsk (< 1 minut)")
                elif time_diff < 300:
                    print("   ⚠️ Timestamp är några minuter gammal")
                else:
                    print("   ❌ Timestamp är gammal (> 5 minuter)")

            except Exception as e:
                print(f"   ❌ Kunde inte parsa timestamp: {e}")

        # Test 3: Kontrollera strategy update timestamps
        print("\n3. ⚙️ Kontrollerar strategy update timestamps...")
        strategy_result = await mcp_tools.update_strategy_parameters(
            "timestamp_test", {"test_time": now_utc.isoformat(), "param2": 42}
        )
        print(f"   ⚙️ Strategy update: {strategy_result}")

        if "updated_at" in strategy_result:
            updated_at = strategy_result["updated_at"]
            print(f"   🕐 Updated at: {updated_at}")

            # Konvertera till datetime för jämförelse
            try:
                mcp_time = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                time_diff = abs((now_utc - mcp_time).total_seconds())
                print(f"   ⏱️ Tidsskillnad från nu: {time_diff:.1f} sekunder")

                if time_diff < 60:
                    print("   ✅ Timestamp är färsk (< 1 minut)")
                elif time_diff < 300:
                    print("   ⚠️ Timestamp är några minuter gammal")
                else:
                    print("   ❌ Timestamp är gammal (> 5 minuter)")

            except Exception as e:
                print(f"   ❌ Kunde inte parsa timestamp: {e}")

        # Test 4: Kontrollera trade execution timestamps
        print("\n4. 💰 Kontrollerar trade execution timestamps...")
        trade_result = await mcp_tools.execute_trade("BTCUSD", "buy", 0.001)
        print(f"   💰 Trade execution: {trade_result}")

        if "executed_at" in trade_result:
            executed_at = trade_result["executed_at"]
            print(f"   🕐 Executed at: {executed_at}")

            # Konvertera till datetime för jämförelse
            try:
                mcp_time = datetime.fromisoformat(executed_at.replace("Z", "+00:00"))
                time_diff = abs((now_utc - mcp_time).total_seconds())
                print(f"   ⏱️ Tidsskillnad från nu: {time_diff:.1f} sekunder")

                if time_diff < 60:
                    print("   ✅ Timestamp är färsk (< 1 minut)")
                elif time_diff < 300:
                    print("   ⚠️ Timestamp är några minuter gammal")
                else:
                    print("   ❌ Timestamp är gammal (> 5 minuter)")

            except Exception as e:
                print(f"   ❌ Kunde inte parsa timestamp: {e}")

        print("\n✅ Timestamp-kontroll slutförd!")

    except Exception as e:
        print(f"❌ Timestamp-kontroll misslyckades: {e}")
        import traceback

        traceback.print_exc()


async def check_mcp_server_time():
    """Kontrollera MCP-server tid direkt"""
    print("\n🔧 Kontrollerar MCP-server tid direkt...")
    print("=" * 60)

    try:
        client = MCPClient()
        await client.initialize()

        # Test tools/list för att se server-tid
        print("📋 Hämta tools från MCP-server...")
        tools = await client.list_tools()
        print(f"   📊 Hittade {len(tools)} tools")

        # Test en enkel tool call för att se response-tid
        print("\n🕐 Testar tool call för att se response-tid...")
        start_time = datetime.now()

        result = await client.call_tool("get_trading_status", {"user_id": "genesis_bot"})

        end_time = datetime.now()
        response_time = (end_time - start_time).total_seconds() * 1000

        print(f"   ⏱️ Response-tid: {response_time:.1f} ms")
        print(f"   📊 Resultat: {result}")

        await client.close()

    except Exception as e:
        print(f"❌ MCP-server tid-kontroll misslyckades: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    print("🕐 MCP Timestamp och Datum Kontroll")
    print("=" * 60)

    # Kör timestamp-kontroll
    asyncio.run(check_mcp_timestamps())

    # Kör MCP-server tid-kontroll
    asyncio.run(check_mcp_server_time())

    print("\n🏁 Timestamp-kontroll slutförd!")
