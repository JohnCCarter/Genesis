"""
Market Data Facade - WS-first med REST fallback och gemensam cache-access.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Tuple, Protocol

from config.settings import Settings
from services.ws_first_data_service import WSFirstDataService, get_ws_first_data_service
from utils.logger import get_logger

logger = get_logger(__name__)


class IMarketDataProvider(Protocol):
    async def get_ticker(self, symbol: str, *, force_fresh: bool = False) -> dict[str, Any] | None: ...
    async def get_candles(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 100,
        *,
        force_fresh: bool = False,
    ) -> list | None: ...
    def get_indicator_snapshot(self, symbol: str, timeframe: str) -> dict | None: ...


class MarketDataFacade:
    def __init__(self, ws_first: WSFirstDataService | None = None) -> None:
        self.ws_first = ws_first or get_ws_first_data_service()
        self.settings = Settings()

    async def get_ticker(self, symbol: str, *, force_fresh: bool = False) -> dict[str, Any] | None:
        """Hämta ticker med timeout och bättre logging."""
        start_time = time.perf_counter()

        try:
            # Kontrollera market data mode
            mode = getattr(self.settings, "MARKETDATA_MODE", "auto")
            if mode == "rest_only":
                # Force REST fallback
                data = await self.ws_first.rest_service.get_ticker(symbol)
                logger.info(
                    f"marketdata.source=rest reason=forced_mode symbol={symbol} lag_ms={(time.perf_counter() - start_time) * 1000:.1f}"
                )
                return data

            # Timeout för WS-snapshot
            timeout = 0.5  # 500ms timeout för WS
            try:
                data = await asyncio.wait_for(
                    self.ws_first.get_ticker(symbol, force_fresh=force_fresh),
                    timeout=timeout,
                )
                lag_ms = (time.perf_counter() - start_time) * 1000
                logger.info(f"marketdata.source=ws symbol={symbol} lag_ms={lag_ms:.1f}")
                return data
            except TimeoutError:
                # Fallback till REST
                data = await self.ws_first.rest_service.get_ticker(symbol)
                lag_ms = (time.perf_counter() - start_time) * 1000
                logger.info(f"marketdata.source=rest reason=ws_timeout symbol={symbol} lag_ms={lag_ms:.1f}")
                return data

        except Exception as e:
            lag_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"marketdata.error symbol={symbol} error={e!s} lag_ms={lag_ms:.1f}")
            return None

    async def get_candles(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 100,
        *,
        force_fresh: bool = False,
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
        try:
            # Exportera limiterstats innan hämtning (best effort)
            from utils.advanced_rate_limiter import get_advanced_rate_limiter

            get_advanced_rate_limiter().export_metrics()
        except Exception:
            pass
        return self.ws_first.get_stats()


_facade_singleton: MarketDataFacade | None = None


def get_market_data() -> MarketDataFacade:
    global _facade_singleton
    if _facade_singleton is None:
        # Lazy-load WSFirstDataService för att undvika WebSocket-anslutning vid startup
        from config.settings import Settings

        settings = Settings()
        ws_connect_on_start = getattr(settings, "WS_CONNECT_ON_START", True)

        if not ws_connect_on_start:
            # Skapa en mock WSFirstDataService som inte ansluter till WebSocket
            from services.ws_first_data_service import WSFirstDataService

            mock_ws_service = WSFirstDataService()
            mock_ws_service._initialized = True  # Markera som initialiserad utan WebSocket
            _facade_singleton = MarketDataFacade(ws_first=mock_ws_service)
        else:
            _facade_singleton = MarketDataFacade()
    return _facade_singleton
