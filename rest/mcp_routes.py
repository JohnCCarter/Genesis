"""
MCP API Routes för Supabase-integration
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from rest.auth import require_auth
# MCP client removed - MCP functionality disabled
# from services.mcp_client import mcp_tools
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
    # MCP functionality disabled
    return []


@router.post("/tools/call", response_model=MCPToolCallResponse)
async def call_mcp_tool(request: MCPToolCall, _: bool = Depends(require_auth)):
    """Anropa ett MCP-tool"""
    # MCP functionality disabled
    return MCPToolCallResponse(success=False, result={}, error="MCP functionality disabled")


@router.get("/trading/status")
async def get_trading_status(_: bool = Depends(require_auth)):
    """Hämta trading-status via MCP"""
    # MCP functionality disabled
    return {"status": "disabled", "message": "MCP functionality disabled"}


@router.post("/trading/execute")
async def execute_trade_via_mcp(
    symbol: str, side: str, amount: float, _: bool = Depends(require_auth)
):
    """Exekvera trade via MCP"""
    # MCP functionality disabled
    raise HTTPException(status_code=503, detail="MCP functionality disabled")


@router.get("/performance/{timeframe}")
async def get_performance_via_mcp(timeframe: str, _: bool = Depends(require_auth)):
    """Hämta prestanda via MCP"""
    # MCP functionality disabled
    return {"message": "MCP functionality disabled", "timeframe": timeframe}


@router.post("/strategy/update")
async def update_strategy_via_mcp(
    strategy_name: str, parameters: dict[str, Any], _: bool = Depends(require_auth)
):
    """Uppdatera strategi via MCP"""
    # MCP functionality disabled
    raise HTTPException(status_code=503, detail="MCP functionality disabled")


@router.get("/health")
async def mcp_health_check():
    """Health check för MCP-anslutningen"""
    # MCP functionality disabled
    return {
        "status": "disabled",
        "mcp_connected": False,
        "message": "MCP functionality disabled",
        "timestamp": "2025-09-05T18:00:00Z",
    }