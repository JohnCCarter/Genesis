"""
MCP Client Service för Supabase-integration
"""

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel

from config.settings import Settings
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MCPTool:
    """Representerar ett MCP-tool"""

    name: str
    description: str
    inputSchema: dict[str, Any]


class MCPResponse(BaseModel):
    """MCP response model"""

    jsonrpc: str = "2.0"
    id: int
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


class MCPClient:
    """MCP-klient för Supabase-integration"""

    def __init__(self):
        self.settings = Settings()
        self.base_url = (
            "https://kxibqgvpdfmklvwhmcry.supabase.co/functions/v1/mcp_server"
        )
        self.client_info = {"name": "Genesis-TradingBot", "version": "1.0.0"}
        self.session_id: str | None = None
        self.initialized = False

        # HTTP-klient med timeout och retry
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )

    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def close(self):
        """Stäng HTTP-klienten"""
        await self.http_client.aclose()

    async def initialize(self) -> bool:
        """Initiera MCP-anslutningen"""
        try:
            # Skapa unik session_id
            import uuid

            session_id = str(uuid.uuid4())

            request = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "session_id": session_id,
                    "user_id": "genesis_bot",  # Vi kan göra detta konfigurerbart senare
                },
                "id": 1,
            }

            response = await self._make_request(request)
            if response and not response.get("error"):
                self.initialized = True
                logger.info("✅ MCP-klient initialiserad")
                return True
            else:
                logger.error(f"❌ MCP-initiering misslyckades: {response}")
                return False

        except Exception as e:
            logger.error(f"❌ MCP-initiering fel: {e}")
            return False

    async def list_tools(self) -> list[MCPTool]:
        """Lista tillgängliga MCP-tools"""
        if not self.initialized:
            await self.initialize()

        try:
            request = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2}

            response = await self._make_request(request)
            if response and not response.get("error"):
                tools_data = response.get("result", {}).get("tools", [])
                tools = []
                for tool_name in tools_data:
                    # Skapa enkla tool-objekt baserat på namnen
                    tool = MCPTool(
                        name=tool_name,
                        description=f"Trading tool: {tool_name}",
                        inputSchema={},  # Vi kan utöka detta senare
                    )
                    tools.append(tool)

                logger.info(f"📋 Hittade {len(tools)} MCP-tools")
                return tools
            else:
                logger.error(f"❌ Kunde inte lista tools: {response}")
                return []

        except Exception as e:
            logger.error(f"❌ List tools fel: {e}")
            return []

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Anropa ett MCP-tool"""
        if not self.initialized:
            await self.initialize()

        try:
            request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"tool": tool_name, "arguments": arguments},
                "id": 3,
            }

            response = await self._make_request(request)
            if response and not response.get("error"):
                result = response.get("result", {})
                logger.info(f"✅ Tool {tool_name} anropat framgångsrikt")
                return result
            else:
                logger.error(f"❌ Tool {tool_name} misslyckades: {response}")
                return None

        except Exception as e:
            logger.error(f"❌ Tool call fel för {tool_name}: {e}")
            return None

    async def _make_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Gör HTTP-request till MCP-servern"""
        try:
            response = await self.http_client.post(
                self.base_url,
                json=request,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"❌ HTTP {response.status_code}: {response.text}")
                return None

        except httpx.TimeoutException:
            logger.error("❌ MCP-request timeout")
            return None
        except httpx.ConnectError:
            logger.error("❌ MCP-anslutning misslyckades")
            return None
        except Exception as e:
            logger.error(f"❌ MCP-request fel: {e}")
            return None


# Trading-specifika MCP-tools
class GenesisMCPTools:
    """Högnivå MCP-tools för Genesis Trading Bot"""

    def __init__(self):
        self.mcp_client = MCPClient()

    async def get_trading_status(self) -> dict[str, Any]:
        """Hämta aktuell trading-status"""
        try:
            result = await self.mcp_client.call_tool(
                "get_trading_status", {"user_id": "genesis_bot"}
            )
            return result or {"status": "unknown", "error": "Tool not available"}
        except Exception as e:
            logger.error(f"❌ get_trading_status fel: {e}")
            return {"status": "error", "error": str(e)}

    async def execute_trade(
        self, symbol: str, side: str, amount: float
    ) -> dict[str, Any]:
        """Exekvera en trade"""
        try:
            arguments = {
                "user_id": "genesis_bot",
                "symbol": symbol,
                "side": side,
                "quantity": amount,
                "price": 0.0,  # Vi kan implementera price-fetching senare
            }
            result = await self.mcp_client.call_tool("execute_trade", arguments)
            return result or {"status": "failed", "error": "Tool not available"}
        except Exception as e:
            logger.error(f"❌ execute_trade fel: {e}")
            return {"status": "error", "error": str(e)}

    async def get_performance_metrics(self, timeframe: str = "1d") -> dict[str, Any]:
        """Hämta prestanda-metrics"""
        try:
            arguments = {"timeframe": timeframe}
            result = await self.mcp_client.call_tool(
                "get_performance_metrics", arguments
            )
            return result or {"metrics": {}, "error": "Tool not available"}
        except Exception as e:
            logger.error(f"❌ get_performance_metrics fel: {e}")
            return {"metrics": {}, "error": str(e)}

    async def update_strategy_parameters(
        self, strategy_name: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Uppdatera strategi-parametrar"""
        try:
            arguments = {"strategy_name": strategy_name, "parameters": params}
            result = await self.mcp_client.call_tool(
                "update_strategy_parameters", arguments
            )
            return result or {"status": "failed", "error": "Tool not available"}
        except Exception as e:
            logger.error(f"❌ update_strategy_parameters fel: {e}")
            return {"status": "error", "error": str(e)}


# Global instans
mcp_tools = GenesisMCPTools()


async def test_mcp_connection():
    """Testa MCP-anslutningen"""
    async with MCPClient() as client:
        # Lista tools
        tools = await client.list_tools()
        print(f"📋 Tillgängliga tools: {len(tools)}")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")

        # Testa trading status
        if tools:
            status = await client.call_tool("get_trading_status", {})
            print(f"📊 Trading status: {status}")


if __name__ == "__main__":
    # Test-script
    asyncio.run(test_mcp_connection())
