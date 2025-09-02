#!/usr/bin/env python3
"""
Test de utökade MCP-tools
"""

import asyncio
import os
import sys

# Lägg till backend-mappen i Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "tradingbot-backend"))

from services.mcp_client import MCPClient


async def test_extended_mcp_tools():
    """Testa de utökade MCP-tools"""
    print("🧪 Testar utökade MCP-tools...")

    try:
        # Testa MCP-klienten
        client = MCPClient()

        # Testa MCP-initiering
        print("1. Initierar MCP-klient...")
        initialized = await client.initialize()
        print(f"   ✅ Initiering: {'Lyckades' if initialized else 'Misslyckades'}")

        if initialized:
            # Testa tools/list (borde nu visa 4 tools)
            print("2. Listar MCP-tools...")
            tools = await client.list_tools()
            print(f"   📋 Hittade {len(tools)} tools:")
            for tool in tools:
                print(f"      - {tool.name}: {tool.description}")

            # Testa get_performance_metrics
            print("3. Testar get_performance_metrics...")
            metrics_result = await client.call_tool(
                "get_performance_metrics", {"user_id": "genesis_bot", "timeframe": "1d"}
            )
            print(f"   📊 Performance metrics resultat: {metrics_result}")

            # Testa update_strategy_parameters
            print("4. Testar update_strategy_parameters...")
            strategy_result = await client.call_tool(
                "update_strategy_parameters",
                {
                    "user_id": "genesis_bot",
                    "strategy_name": "test_strategy",
                    "parameters": {"param1": "value1", "param2": 42, "param3": True},
                },
            )
            print(f"   ⚙️ Strategy update resultat: {strategy_result}")

            # Testa alla tools via GenesisMCPTools
            print("5. Testar via GenesisMCPTools...")
            from services.mcp_client import GenesisMCPTools

            mcp_tools = GenesisMCPTools()

            # Testa performance metrics
            metrics = await mcp_tools.get_performance_metrics("1d")
            print(f"   📈 Performance metrics: {metrics}")

            # Testa strategy update
            strategy_update = await mcp_tools.update_strategy_parameters(
                "test_strategy_via_class", {"param1": "updated_value", "param2": 100}
            )
            print(f"   🔧 Strategy update via class: {strategy_update}")

        else:
            print("   ❌ Initiering misslyckades")

    except Exception as e:
        print(f"❌ Test misslyckades: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_extended_mcp_tools())
