"""
MCP API Routes för Supabase-integration
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from rest.auth import require_auth
from services.mcp_client import mcp_tools
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2/mcp", tags=["MCP"])


class MCPToolInfo(BaseModel):
    """MCP tool information"""

    name: str
    description: str
    inputSchema: dict[str, Any]


class MCPToolCall(BaseModel):
    """MCP tool call request"""

    tool_name: str
    arguments: dict[str, Any]


class MCPToolCallResponse(BaseModel):
    """MCP tool call response"""

    success: bool
    result: dict[str, Any] = {}
    error: str = ""


@router.get("/tools", response_model=list[MCPToolInfo])
async def list_mcp_tools(_: bool = Depends(require_auth)):
    """Lista tillgängliga MCP-tools"""
    try:
        tools = await mcp_tools.mcp_client.list_tools()
        return [
            MCPToolInfo(name=tool.name, description=tool.description, inputSchema=tool.inputSchema)
            for tool in tools
        ]
    except Exception as e:
        logger.error(f"❌ Kunde inte lista MCP-tools: {e}")
        raise HTTPException(status_code=500, detail=f"Kunde inte lista MCP-tools: {e!s}")


@router.post("/tools/call", response_model=MCPToolCallResponse)
async def call_mcp_tool(request: MCPToolCall, _: bool = Depends(require_auth)):
    """Anropa ett MCP-tool"""
    try:
        result = await mcp_tools.mcp_client.call_tool(request.tool_name, request.arguments)

        if result:
            return MCPToolCallResponse(success=True, result=result, error="")
        else:
            return MCPToolCallResponse(success=False, result={}, error="Tool call misslyckades")

    except Exception as e:
        logger.error(f"❌ MCP tool call fel: {e}")
        return MCPToolCallResponse(success=False, result={}, error=str(e))


@router.get("/trading/status")
async def get_trading_status(_: bool = Depends(require_auth)):
    """Hämta trading-status via MCP"""
    try:
        status = await mcp_tools.get_trading_status()
        return status
    except Exception as e:
        logger.error(f"❌ Kunde inte hämta trading-status: {e}")
        raise HTTPException(status_code=500, detail=f"Kunde inte hämta trading-status: {e!s}")


@router.post("/trading/execute")
async def execute_trade_via_mcp(
    symbol: str, side: str, amount: float, _: bool = Depends(require_auth)
):
    """Exekvera trade via MCP"""
    try:
        result = await mcp_tools.execute_trade(symbol, side, amount)
        return result
    except Exception as e:
        logger.error(f"❌ Kunde inte exekvera trade: {e}")
        raise HTTPException(status_code=500, detail=f"Kunde inte exekvera trade: {e!s}")


@router.get("/performance/{timeframe}")
async def get_performance_via_mcp(timeframe: str, _: bool = Depends(require_auth)):
    """Hämta prestanda via MCP"""
    try:
        metrics = await mcp_tools.get_performance_metrics(timeframe)
        return metrics
    except Exception as e:
        logger.error(f"❌ Kunde inte hämta prestanda: {e}")
        raise HTTPException(status_code=500, detail=f"Kunde inte hämta prestanda: {e!s}")


@router.post("/strategy/update")
async def update_strategy_via_mcp(
    strategy_name: str, parameters: dict[str, Any], _: bool = Depends(require_auth)
):
    """Uppdatera strategi via MCP"""
    try:
        result = await mcp_tools.update_strategy_parameters(strategy_name, parameters)
        return result
    except Exception as e:
        logger.error(f"❌ Kunde inte uppdatera strategi: {e}")
        raise HTTPException(status_code=500, detail=f"Kunde inte uppdatera strategi: {e!s}")


@router.get("/health")
async def mcp_health_check():
    """Health check för MCP-anslutningen"""
    try:
        # Testa enkel anslutning
        initialized = await mcp_tools.mcp_client.initialize()
        return {
            "status": "healthy" if initialized else "unhealthy",
            "mcp_connected": initialized,
            "timestamp": "2025-09-02T09:00:00Z",
        }
    except Exception as e:
        logger.error(f"❌ MCP health check misslyckades: {e}")
        return {
            "status": "unhealthy",
            "mcp_connected": False,
            "error": str(e),
            "timestamp": "2025-09-02T09:00:00Z",
        }
