import asyncio
import os

import pytest

from services.bitfinex_websocket import bitfinex_ws


@pytest.mark.asyncio
async def test_ws_pool_respects_max_sockets(monkeypatch):
    # Tvinga på pool och sätt lågt tak
    monkeypatch.setattr(bitfinex_ws, "_pool_enabled", True, raising=True)
    monkeypatch.setattr(bitfinex_ws, "_pool_max_sockets", 1, raising=True)
    monkeypatch.setattr(bitfinex_ws, "_pool_max_subs", 2, raising=True)

    # Mocka _open_public_socket så vi inte gör riktiga nätverksanrop
    class DummyWS:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

        async def send(self, _msg: str):  # pragma: no cover - inte relevant här
            pass

    opened = {"count": 0}

    async def _fake_open_public_socket():
        opened["count"] += 1
        return DummyWS()

    monkeypatch.setattr(bitfinex_ws, "_open_public_socket", _fake_open_public_socket, raising=True)

    # Rensa ev. tidigare state
    bitfinex_ws._pool_public.clear()
    bitfinex_ws._pool_sub_counts.clear()
    bitfinex_ws._sub_socket.clear()

    # Be om flera sockets genom att överbelasta subs per socket
    # Först sub:a två gånger (fyll max_subs)
    ws1 = await bitfinex_ws._get_public_socket()
    bitfinex_ws._pool_sub_counts[ws1] = bitfinex_ws._pool_max_subs

    # Nu ett nytt sub-försök som skulle trigga fler sockets om cap tillåter
    ws2 = await bitfinex_ws._get_public_socket()

    # Verifiera att vi inte skapat fler än cap
    assert len(bitfinex_ws._pool_public) <= bitfinex_ws._pool_max_sockets
    assert len(bitfinex_ws._pool_public) == 1
    assert ws1 is ws2  # ska återanvända samma eftersom cap=1


@pytest.mark.asyncio
async def test_ws_pool_trims_excess_when_cap_reduced(monkeypatch):
    # Starta med cap=2 och skapa två sockets
    monkeypatch.setattr(bitfinex_ws, "_pool_enabled", True, raising=True)
    monkeypatch.setattr(bitfinex_ws, "_pool_max_sockets", 2, raising=True)
    monkeypatch.setattr(bitfinex_ws, "_pool_max_subs", 1, raising=True)

    class DummyWS:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

        async def send(self, _msg: str):  # pragma: no cover
            pass

    async def _fake_open_public_socket():
        return DummyWS()

    monkeypatch.setattr(bitfinex_ws, "_open_public_socket", _fake_open_public_socket, raising=True)

    bitfinex_ws._pool_public.clear()
    bitfinex_ws._pool_sub_counts.clear()
    bitfinex_ws._sub_socket.clear()

    # Skapa första
    ws_a = await bitfinex_ws._get_public_socket()
    bitfinex_ws._pool_sub_counts[ws_a] = 1

    # Tvinga fram andra genom att låtsas att första är full
    bitfinex_ws._pool_sub_counts[ws_a] = bitfinex_ws._pool_max_subs
    ws_b = await bitfinex_ws._get_public_socket()
    assert len(bitfinex_ws._pool_public) == 2

    # Sänk cap till 1 och be om socket igen – överflöd ska trimmas bort
    monkeypatch.setattr(bitfinex_ws, "_pool_max_sockets", 1, raising=True)
    ws_c = await bitfinex_ws._get_public_socket()

    assert len(bitfinex_ws._pool_public) == 1
    # ws_c ska vara en av de kvarvarande referenserna
    assert ws_c in bitfinex_ws._pool_public
