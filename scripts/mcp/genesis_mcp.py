import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

BASE_URL = os.getenv("GENESIS_BASE_URL", "http://127.0.0.1:8000")
USER_ID = os.getenv("GENESIS_USER_ID", "frontend_user")
SCOPE = os.getenv("GENESIS_SCOPE", "read")


def _headers(token: str | None) -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def _get_token() -> str:
    url = f"{BASE_URL}/api/v2/auth/ws-token"
    payload = {"user_id": USER_ID, "scope": SCOPE, "expiry_hours": 1}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("token") or data.get("access_token") or ""


app = FastMCP("genesis-mcp")


@app.tool()
async def get_token() -> dict[str, Any]:
    return {"token": await _get_token()}


@app.tool()
async def ws_status(
    token: str | None = None,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.get(
            f"{BASE_URL}/api/v2/ws/pool/status",
            headers=_headers(token),
        )
        response.raise_for_status()
        return response.json()


@app.tool()
async def toggle_ws_strategy(
    enabled: bool,
    token: str | None = None,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/v2/mode/ws-strategy",
            headers=_headers(token),
            json={"enabled": bool(enabled)},
        )
        response.raise_for_status()
        return response.json()


@app.tool()
async def toggle_validation_warmup(
    enabled: bool,
    token: str | None = None,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/v2/mode/validation-warmup",
            headers=_headers(token),
            json={"enabled": bool(enabled)},
        )
        response.raise_for_status()
        return response.json()


@app.tool()
async def toggle_ws_connect_on_start(
    enabled: bool,
    token: str | None = None,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/v2/mode/ws-connect-on-start",
            headers=_headers(token),
            json={"enabled": bool(enabled)},
        )
        response.raise_for_status()
        return response.json()


@app.tool()
async def market_ticker(
    symbol: str = "tBTCUSD",
    token: str | None = None,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.get(
            f"{BASE_URL}/api/v2/market/ticker/{symbol}",
            headers=_headers(token),
        )
        response.raise_for_status()
        return response.json()


@app.tool()
async def run_validation(
    symbols: str | None = None,
    timeframe: str | None = None,
    limit: int | None = None,
    max_samples: int | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "symbols": symbols,
        "timeframe": timeframe,
        "limit": limit,
        "max_samples": max_samples,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/v2/prob/validate/run",
            headers=_headers(token),
            json=payload,
        )
        response.raise_for_status()
        return response.json()


@app.tool()
async def place_order(
    symbol: str,
    amount: float,
    order_type: str = "EXCHANGE MARKET",
    price: float | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "symbol": symbol,
        "amount": amount,
        "type": order_type,
    }
    if price is not None:
        payload["price"] = price
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/v2/order", headers=_headers(token), json=payload
        )
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    # Defaulta till stdio-transport för MCP-klienter som Cursor/Lovable
    mode = os.getenv("MCP_TRANSPORT", "stdio").lower()
    if mode == "stdio":
        import asyncio as _asyncio

        _asyncio.run(app.run_stdio_async())
    else:
        app.run()
