"""
# AI Change: Inför lazy per-event-loop AsyncClient och säker stängning
# (Agent: Codex, Date: 2025-09-16) – Fixar "Event loop is closed" vid reload/shutdown
"""

import asyncio
import httpx
from typing import Dict

limits = httpx.Limits(max_keepalive_connections=20, max_connections=40)
timeout = httpx.Timeout(connect=2.0, read=6.0, write=6.0, pool=2.0)

# Per-event-loop klienter för att undvika att en stängd klient återanvänds i ny loop
_clients_by_loop: Dict[int, httpx.AsyncClient] = {}


def _get_loop_id() -> int:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None  # type: ignore
    return id(loop)


def get_async_client() -> httpx.AsyncClient:
    loop_id = _get_loop_id()
    client = _clients_by_loop.get(loop_id)
    if client is None or getattr(client, "is_closed", False):
        client = httpx.AsyncClient(limits=limits, timeout=timeout, http2=False)
        _clients_by_loop[loop_id] = client
    return client


async def close_http_clients() -> None:
    # Stänger alla kända klienter säkert
    to_close = list(_clients_by_loop.items())
    _clients_by_loop.clear()
    for _, client in to_close:
        try:
            await client.aclose()
        except Exception:
            pass


async def aget(url: str, headers: dict | None = None, params: dict | None = None):
    client = get_async_client()
    r = await client.get(url, headers=headers, params=params)
    r.raise_for_status()
    return r


async def apost(url: str, headers: dict | None = None, json: dict | None = None):
    client = get_async_client()
    r = await client.post(url, headers=headers, json=json)
    r.raise_for_status()
    return r
