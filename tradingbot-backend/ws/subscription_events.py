"""
Socket.IO bridge events for subscription management.

Ger UI-direkt WS-åtkomst utan REST-wrappers:
- subscribe_channel: { channel: 'ticker'|'trades'|'candles', symbol: 'tPAIR', timeframe?: '1m' }
- unsubscribe_channel: samma fält; beräknar sub_key och kallar unsubscribe
- get_pool_status: returnerar WS-poolstatus
"""

from __future__ import annotations

from typing import Any

from ws.manager import socket_app


@socket_app.event
async def get_pool_status(sid, data=None):
    try:
        from services.bitfinex_websocket import bitfinex_ws

        return bitfinex_ws.get_pool_status()
    except Exception as e:
        return {"success": False, "error": str(e)}


@socket_app.event
async def subscribe_channel(sid, payload: dict[str, Any]):
    try:
        chan = str((payload or {}).get("channel") or "").lower()
        sym = (payload or {}).get("symbol")
        if not sym or not chan:
            return {"success": False, "error": "invalid_payload"}

        from services.bitfinex_websocket import bitfinex_ws

        if chan == "ticker":
            await bitfinex_ws.subscribe_ticker(sym, bitfinex_ws._handle_ticker_with_strategy)
            sub_key = f"ticker|{sym}"
        elif chan == "trades":
            await bitfinex_ws.subscribe_trades(sym, bitfinex_ws._handle_ticker_with_strategy)
            sub_key = f"trades|{sym}"
        elif chan == "candles":
            tf = str((payload or {}).get("timeframe") or "1m").strip()
            await bitfinex_ws.subscribe_candles(sym, tf, bitfinex_ws._handle_ticker_with_strategy)
            sub_key = f"candles|trade:{tf}:{sym}"
        else:
            return {"success": False, "error": "invalid_channel"}

        return {"success": True, "sub_key": sub_key}
    except Exception as e:
        return {"success": False, "error": str(e)}


@socket_app.event
async def unsubscribe_channel(sid, payload: dict[str, Any]):
    try:
        chan = str((payload or {}).get("channel") or "").lower()
        sym = (payload or {}).get("symbol")
        if not sym or not chan:
            return {"success": False, "error": "invalid_payload"}

        if chan == "ticker":
            sub_key = f"ticker|{sym}"
        elif chan == "trades":
            sub_key = f"trades|{sym}"
        elif chan == "candles":
            tf = str((payload or {}).get("timeframe") or "1m").strip()
            sub_key = f"candles|trade:{tf}:{sym}"
        else:
            return {"success": False, "error": "invalid_channel"}

        from services.bitfinex_websocket import bitfinex_ws

        await bitfinex_ws.unsubscribe(sub_key)
        return {"success": True, "sub_key": sub_key}
    except Exception as e:
        return {"success": False, "error": str(e)}
