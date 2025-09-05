"""
Market Data Facade - WS-first med REST fallback och gemensam cache-access.
"""

from __future__ import annotations

from typing import Any, Tuple

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

    async def get_configs_symbols(self) -> list[str] | None:
        """Proxy: hämta listade par via underliggande REST-service."""
        try:
            return await self.ws_first.rest_service.get_configs_symbols()
        except Exception:
            return None

    async def get_currency_symbol_map(self) -> tuple[dict[str, str], dict[str, str]]:
        """Proxy: hämta currency alias-map (fwd, rev) via REST-service."""
        try:
            return await self.ws_first.rest_service.get_currency_symbol_map()
        except Exception:
            return {}, {}

    def parse_candles_to_strategy_data(self, candles: list[list]) -> dict[str, list[float]]:
        """Hjälpare: centralisera candle-parsning till strategi-format."""
        try:
            from utils.candles import parse_candles_to_strategy_data as _parse

            return _parse(candles)
        except Exception:
            return {"closes": [], "highs": [], "lows": []}

    def stats(self) -> dict[str, Any]:
        return self.ws_first.get_stats()


_facade_singleton: MarketDataFacade | None = None


def get_market_data() -> MarketDataFacade:
    global _facade_singleton
    if _facade_singleton is None:
        # Lazy-load WSFirstDataService för att undvika WebSocket-anslutning vid startup
        from config.settings import Settings

        settings = Settings()
        ws_connect_on_start = getattr(settings, 'WS_CONNECT_ON_START', True)

        if not ws_connect_on_start:
            # Skapa en mock WSFirstDataService som inte ansluter till WebSocket
            from services.ws_first_data_service import WSFirstDataService

            mock_ws_service = WSFirstDataService()
            mock_ws_service._initialized = True  # Markera som initialiserad utan WebSocket
            _facade_singleton = MarketDataFacade(ws_first=mock_ws_service)
        else:
            _facade_singleton = MarketDataFacade()
    return _facade_singleton
