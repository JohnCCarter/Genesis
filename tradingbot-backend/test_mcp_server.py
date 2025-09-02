#!/usr/bin/env python3
"""
Test script för MCP-server integration
"""

import asyncio
import json
from typing import Any, Dict

import httpx

MCP_SERVER_URL = "https://kxibqgvpdfmklvwhmcry.supabase.co/functions/v1/mcp-server"


async def test_mcp_server():
    """Testa MCP-servern med olika anrop"""

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1: Initialize
        print("🧪 Test 1: Initialize")
        init_request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "Genesis-Test", "version": "1.0.0"},
            },
            "id": 1,
        }

        try:
            response = await client.post(
                MCP_SERVER_URL, json=init_request, headers={"Content-Type": "application/json"}
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        except Exception as e:
            print(f"❌ Initialize failed: {e}")

        print("\n" + "=" * 50 + "\n")

        # Test 2: List tools
        print("🧪 Test 2: List tools")
        tools_request = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2}

        try:
            response = await client.post(
                MCP_SERVER_URL, json=tools_request, headers={"Content-Type": "application/json"}
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        except Exception as e:
            print(f"❌ List tools failed: {e}")

        print("\n" + "=" * 50 + "\n")

        # Test 3: Call specific tool (om vi vet vilka som finns)
        print("🧪 Test 3: Test trading status tool")
        call_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "get_trading_status", "arguments": {}},
            "id": 3,
        }

        try:
            response = await client.post(
                MCP_SERVER_URL, json=call_request, headers={"Content-Type": "application/json"}
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        except Exception as e:
            print(f"❌ Tool call failed: {e}")


if __name__ == "__main__":
    print("🚀 Testing MCP Server...")
    print(f"URL: {MCP_SERVER_URL}")
    print("=" * 50)

    asyncio.run(test_mcp_server())
