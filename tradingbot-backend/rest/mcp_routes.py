"""
MCP API Routes för Genesis Trading Bot

Exponerar MCP-funktionalitet via REST API för att låta externa klienter
kontrollera och fråga boten via MCP-servern.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from utils.logger import get_logger

from services.mcp_client import mcp_tools


# Enkel autentiseringsfunktion för MCP-endpoints
async def require_auth() -> bool:
    """Enkel autentisering - returnerar alltid True för nu"""
    return True


logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2/mcp", tags=["MCP"])


class MCPToolInfo(BaseModel):
    """Information om ett MCP-tool"""

    name: str
    description: str
    inputSchema: dict[str, Any]  # noqa: N815


class MCPToolCall(BaseModel):
    """Request för att anropa ett MCP-tool"""

    tool_name: str
    arguments: dict[str, Any]


class MCPToolCallResponse(BaseModel):
    """Response från MCP-tool anrop"""

    success: bool
    result: dict[str, Any] = {}
    error: str = ""


class TradeExecutionRequest(BaseModel):
    """Request för trade execution"""

    symbol: str
    side: str
    amount: float


class StrategyUpdateRequest(BaseModel):
    """Request för strategy update"""

    strategy_name: str
    params: dict[str, Any]


@router.get("/tools", response_model=list[MCPToolInfo])
async def list_mcp_tools(_: bool = Depends(require_auth)):
    """Lista tillgängliga MCP-tools"""
    try:
        tools = await mcp_tools.mcp_client.list_tools()
        return [
            MCPToolInfo(name=tool.name, description=tool.description, inputSchema=tool.inputSchema) for tool in tools
        ]
    except Exception as e:
        logger.error(f"❌ Kunde inte lista MCP-tools: {e}")
        raise HTTPException(status_code=500, detail=f"Kunde inte lista MCP-tools: {e!s}")


@router.post("/tools/call", response_model=MCPToolCallResponse)
async def call_mcp_tool(request: MCPToolCall, _: bool = Depends(require_auth)):
    """Anropa ett MCP-tool"""
    try:
        result = await mcp_tools.mcp_client.call_tool(request.tool_name, request.arguments)

        if result is not None:
            return MCPToolCallResponse(success=True, result=result)
        else:
            return MCPToolCallResponse(success=False, error="Tool returnerade inget resultat")

    except Exception as e:
        logger.error(f"❌ MCP tool call fel: {e}")
        return MCPToolCallResponse(success=False, error=str(e))


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
async def execute_trade_via_mcp(request: TradeExecutionRequest, _: bool = Depends(require_auth)):
    """Exekvera en trade via MCP"""
    try:
        logger.info(f"🚀 Executing trade: {request.symbol} {request.side} {request.amount}")
        result = await mcp_tools.execute_trade(request.symbol, request.side, request.amount)
        logger.info(f"✅ Trade executed successfully: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Kunde inte exekvera trade: {e}")
        raise HTTPException(status_code=500, detail=f"Kunde inte exekvera trade: {e!s}")


@router.get("/trading/performance")
async def get_performance_metrics(timeframe: str = "1d", _: bool = Depends(require_auth)):
    """Hämta prestanda-metrics via MCP"""
    try:
        logger.info(f"📊 Fetching performance metrics for timeframe: {timeframe}")
        metrics = await mcp_tools.get_performance_metrics(timeframe)
        logger.info(f"✅ Performance metrics fetched: {metrics}")
        return metrics
    except Exception as e:
        logger.error(f"❌ Kunde inte hämta prestanda-metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Kunde inte hämta prestanda-metrics: {e!s}")


@router.post("/strategy/update")
async def update_strategy_parameters(request: StrategyUpdateRequest, _: bool = Depends(require_auth)):
    """Uppdatera strategi-parametrar via MCP"""
    try:
        logger.info(f"⚙️ Updating strategy parameters: {request.strategy_name} with {request.params}")
        result = await mcp_tools.update_strategy_parameters(request.strategy_name, request.params)
        logger.info(f"✅ Strategy parameters updated: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Kunde inte uppdatera strategi-parametrar: {e}")
        raise HTTPException(status_code=500, detail=f"Kunde inte uppdatera strategi-parametrar: {e!s}")


@router.get("/health")
async def mcp_health_check():
    """Hälsokontroll för MCP-integrationen"""
    try:
        # Testa grundläggande anslutning
        tools = await mcp_tools.mcp_client.list_tools()
        return {
            "status": "healthy",
            "mcp_server": "connected",
            "available_tools": len(tools),
            "timestamp": "2025-09-02T10:52:00Z",
        }
    except Exception as e:
        logger.error(f"❌ MCP health check misslyckades: {e}")
        return {
            "status": "unhealthy",
            "mcp_server": "disconnected",
            "error": str(e),
            "timestamp": "2025-09-02T10:52:00Z",
        }
