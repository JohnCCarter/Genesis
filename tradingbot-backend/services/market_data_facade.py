"""
Market Data Facade - WS-first med REST fallback och gemensam cache-access.
"""

from __future__ import annotations

from typing import Any

from services.ws_first_data_service import WSFirstDataService, get_ws_first_data_service


class MarketDataFacade:
    def __init__(self, ws_first: WSFirstDataService | None = None) -> None:
        self.ws_first = ws_first or get_ws_first_data_service()

    async def get_ticker(self, symbol: str, *, force_fresh: bool = False) -> dict[str, Any] | None:
        return await self.ws_first.get_ticker(symbol, force_fresh=force_fresh)

    async def get_candles(
        self, symbol: str, timeframe: str = "1m", limit: int = 100, *, force_fresh: bool = False
    ) -> list | None:
        return await self.ws_first.get_candles(symbol, timeframe=timeframe, limit=limit, force_fresh=force_fresh)

    def get_indicator_snapshot(self, symbol: str, timeframe: str) -> dict | None:
        return self.ws_first.get_indicator_snapshot(symbol, timeframe)

    def stats(self) -> dict[str, Any]:
        return self.ws_first.get_stats()


_facade_singleton: MarketDataFacade | None = None


def get_market_data() -> MarketDataFacade:
    global _facade_singleton
    if _facade_singleton is None:
        _facade_singleton = MarketDataFacade()
    return _facade_singleton
