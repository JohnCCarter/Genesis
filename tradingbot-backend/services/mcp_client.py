"""
MCP Client Service för Supabase-integration
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel
from utils.logger import get_logger

from config.settings import Settings

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
        self.base_url = self.settings.MCP_SERVER_URL
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

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
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
            # Hämta JWT-token från Supabase Auth
            jwt_token = await self._get_jwt_token()
            if not jwt_token:
                logger.error("❌ Kunde inte hämta JWT-token")
                return None

            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {jwt_token}"}

            response = await self.http_client.post(self.base_url, json=request, headers=headers)

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

    async def _get_jwt_token(self) -> str | None:
        """Hämta JWT-token via JWT-hemligheten"""
        try:
            # Kontrollera om vi har JWT-hemlighet
            if not hasattr(self.settings, "JWT_SECRET") or not self.settings.JWT_SECRET:
                logger.error("❌ JWT_SECRET saknas i inställningar")
                return None

            # Skapa en enkel JWT-token för testing
            from datetime import datetime, timedelta

            import jwt

            # Payload för Genesis bot
            payload = {
                "sub": "genesis_bot",
                "email": "genesis@bot.local",
                "iat": datetime.utcnow(),
                "exp": datetime.utcnow() + timedelta(hours=1),  # 1 timme giltig
                "aud": "authenticated",
                "role": "authenticated",
            }

            # Skapa JWT med hemligheten
            token = jwt.encode(payload, self.settings.JWT_SECRET, algorithm="HS256")
            logger.info("✅ JWT-token skapad framgångsrikt")
            return token

        except Exception as e:
            logger.error(f"❌ JWT-token skapande misslyckades: {e}")
            logger.error(f"❌ Fel typ: {type(e)}")
            import traceback

            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return None


# Trading-specifika MCP-tools
class GenesisMCPTools:
    """Högnivå MCP-tools för Genesis Trading Bot"""

    def __init__(self):
        self.mcp_client = MCPClient()

    async def get_trading_status(self) -> dict[str, Any]:
        """Hämta aktuell trading-status från Supabase MCP-server"""
        try:
            # Först initiera MCP-klienten om den inte redan är det
            if not self.mcp_client.initialized:
                await self.mcp_client.initialize()

            result = await self.mcp_client.call_tool("get_trading_status", {"user_id": "genesis_bot"})
            if result:
                logger.info("✅ Trading status hämtad från Supabase MCP-server")
                return result
            else:
                logger.warning("⚠️ Kunde inte hämta trading status från MCP-server")
                return {"status": "unknown", "error": "Tool not available"}
        except Exception as e:
            logger.error(f"❌ get_trading_status fel: {e}")
            return {"status": "error", "error": str(e)}

    async def execute_trade(self, symbol: str, side: str, amount: float) -> dict[str, Any]:
        """Exekvera en trade via Supabase MCP-server"""
        try:
            # Först initiera MCP-klienten om den inte redan är det
            if not self.mcp_client.initialized:
                await self.mcp_client.initialize()

            arguments = {
                "user_id": "genesis_bot",
                "symbol": symbol,
                "side": side,
                "quantity": amount,
                "price": 0.0,  # Vi kan implementera price-fetching senare
            }
            result = await self.mcp_client.call_tool("execute_trade", arguments)
            if result:
                logger.info(f"✅ Trade exekverad via Supabase MCP-server: {symbol} {side} {amount}")
                return result
            else:
                logger.warning("⚠️ Kunde inte exekvera trade via MCP-server")
                return {"status": "failed", "error": "Tool not available"}
        except Exception as e:
            logger.error(f"❌ execute_trade fel: {e}")
            return {"status": "error", "error": str(e)}

    async def get_performance_metrics(self, timeframe: str = "1d") -> dict[str, Any]:
        """Hämta prestanda-metrics från Supabase MCP-server"""
        try:
            # Först initiera MCP-klienten om den inte redan är det
            if not self.mcp_client.initialized:
                await self.mcp_client.initialize()

            arguments = {"user_id": "genesis_bot", "timeframe": timeframe}
            result = await self.mcp_client.call_tool("get_performance_metrics", arguments)
            if result:
                logger.info(f"✅ Performance metrics hämtade från Supabase MCP-server: {timeframe}")
                return result
            else:
                logger.warning("⚠️ Kunde inte hämta performance metrics från MCP-server")
                return {"metrics": {}, "error": "Tool not available"}
        except Exception as e:
            logger.error(f"❌ get_performance_metrics fel: {e}")
            return {"metrics": {}, "error": str(e)}

    async def update_strategy_parameters(self, strategy_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Uppdatera strategi-parametrar via Supabase MCP-server"""
        try:
            # Först initiera MCP-klienten om den inte redan är det
            if not self.mcp_client.initialized:
                await self.mcp_client.initialize()

            arguments = {
                "user_id": "genesis_bot",
                "strategy_name": strategy_name,
                "parameters": params,
            }
            result = await self.mcp_client.call_tool("update_strategy_parameters", arguments)
            if result:
                logger.info(f"✅ Strategy parameters uppdaterade via Supabase MCP-server: {strategy_name}")
                return result
            else:
                logger.warning("⚠️ Kunde inte uppdatera strategy parameters via MCP-server")
                return {"status": "failed", "error": "Tool not available"}
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
            status = await client.call_tool("get_trading_status", {"user_id": "genesis_bot"})
            print(f"📊 Trading status: {status}")


if __name__ == "__main__":
    # Test-script
    asyncio.run(test_mcp_connection())
