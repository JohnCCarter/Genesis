"""
Debug Routes - TradingBot Backend

Debug endpoints för att diagnostisera hängningar och prestandaproblem.
"""

import asyncio
import sys
import threading
import traceback
from typing import Any

from fastapi import APIRouter
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/api/v2/debug/tasks")
async def dump_tasks() -> dict[str, Any]:
    """Dump alla aktiva asyncio tasks med stack traces."""
    try:
        tasks = asyncio.all_tasks()
        out = []

        for task in tasks:
            try:
                # Hämta stack trace för task
                stack = ""
                if hasattr(task, "_coro") and task._coro:
                    try:
                        # Försök få stack från coroutine
                        frame = task._coro.cr_frame
                        if frame:
                            stack = "".join(traceback.format_stack(frame, limit=10))
                    except Exception:
                        stack = f"Task: {task.get_name()}"
                else:
                    stack = f"Task: {task.get_name()}"

                out.append(
                    {
                        "name": task.get_name(),
                        "done": task.done(),
                        "cancelled": task.cancelled(),
                        "exception": (str(task.exception()) if task.done() and task.exception() else None),
                        "stack": stack,
                    }
                )
            except Exception as e:
                out.append({"name": "unknown", "error": str(e), "stack": ""})

        return {
            "count": len(out),
            "tasks": out,
            "current_task": (asyncio.current_task().get_name() if asyncio.current_task() else None),
        }
    except Exception as e:
        logger.error(f"Fel vid task dump: {e}")
        return {"error": str(e), "count": 0, "tasks": []}


@router.get("/api/v2/debug/threads")
def dump_threads() -> dict[str, Any]:
    """Dump alla aktiva trådar med stack traces."""
    try:
        frames = sys._current_frames()
        data = []

        for thread in threading.enumerate():
            try:
                frame = frames.get(thread.ident)
                stack = ""
                if frame:
                    stack = "".join(traceback.format_stack(frame, limit=10))

                data.append(
                    {
                        "name": thread.name,
                        "ident": thread.ident,
                        "daemon": thread.daemon,
                        "alive": thread.is_alive(),
                        "stack": stack,
                    }
                )
            except Exception as e:
                data.append({"name": "unknown", "error": str(e), "stack": ""})

        return {
            "count": len(data),
            "threads": data,
            "main_thread": threading.main_thread().name,
        }
    except Exception as e:
        logger.error(f"Fel vid thread dump: {e}")
        return {"error": str(e), "count": 0, "threads": []}


@router.get("/api/v2/debug/rate_limiter")
async def dump_rate_limiter() -> dict[str, Any]:
    """Dump rate limiter status och circuit breaker state."""
    try:
        from utils.advanced_rate_limiter import get_advanced_rate_limiter

        limiter = get_advanced_rate_limiter()
        stats = limiter.get_stats()

        # Hämta circuit breaker state
        cb_state = {}
        for endpoint in ["ticker", "auth/r/wallets", "auth/w/order/submit"]:
            cb_state[endpoint] = {
                "can_request": limiter.can_request(endpoint),
                "time_until_open": limiter.time_until_open(endpoint),
            }

        return {
            "stats": stats,
            "circuit_breakers": cb_state,
            "server_busy_count": limiter._server_busy_count,
            "adaptive_backoff_multiplier": limiter._adaptive_backoff_multiplier,
        }
    except Exception as e:
        logger.error(f"Fel vid rate limiter dump: {e}")
        return {"error": str(e)}


@router.get("/api/v2/debug/market_data")
async def dump_market_data() -> dict[str, Any]:
    """Dump market data facade status."""
    try:
        from services.market_data_facade import get_market_data

        facade = get_market_data()
        stats = facade.get_stats()

        return {
            "stats": stats,
            "ws_connected": getattr(facade.ws_first, "_ws_connected", False),
            "initialized": getattr(facade.ws_first, "_initialized", False),
        }
    except Exception as e:
        logger.error(f"Fel vid market data dump: {e}")
        return {"error": str(e)}


@router.get("/api/v2/debug/risk_guards")
async def dump_risk_guards() -> dict[str, Any]:
    """Dump risk guards status."""
    try:
        from services.risk_guards import risk_guards

        status = risk_guards.get_guards_status()
        return status
    except Exception as e:
        logger.error(f"Fel vid risk guards dump: {e}")
        return {"error": str(e)}


@router.get("/api/v2/debug/websocket")
async def dump_websocket() -> dict[str, Any]:
    """Dump WebSocket service status."""
    try:
        from services.bitfinex_websocket import bitfinex_ws

        return {
            "connected": bitfinex_ws.is_connected,
            "authenticated": getattr(bitfinex_ws, "_authenticated", False),
            "last_ping": getattr(bitfinex_ws, "_last_ping_time", None),
            "last_pong": getattr(bitfinex_ws, "_last_pong_time", None),
            "message_count": getattr(bitfinex_ws, "_message_count", 0),
            "error_count": getattr(bitfinex_ws, "_error_count", 0),
        }
    except Exception as e:
        logger.error(f"Fel vid WebSocket dump: {e}")
        return {"error": str(e)}
