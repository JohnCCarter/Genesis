"""
Data Coordinator Service - TradingBot Backend

Centraliserar data-hämtning och delar data mellan tjänster för att minska
duplicerade API-anrop och förbättra prestanda.
"""

# ruff: noqa: ANN401, ARG001

import asyncio
from datetime import datetime
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)


class DataCoordinatorService:
    """Centraliserad data-koordinator för att minska API-anrop."""

    def __init__(self):
        self._data_cache: dict[str, dict[str, Any]] = {}
        # Öka cache TTL för bättre prestanda
        self._cache_ttl_seconds = 600  # 10 minuter TTL (tidigare 300)
        self._margin_cache_ttl_seconds = 1200  # 20 minuter för margin-data (tidigare 600)
        self._request_locks: dict[str, asyncio.Lock] = {}
        self._last_cleanup = datetime.now()
        self._batch_requests: dict[str, asyncio.Future] = {}

    def _get_cache_key(self, data_type: str, symbol: str, **kwargs: Any) -> str:
        """Generera unik cache-nyckel."""
        params = "_".join([f"{k}={v}" for k, v in sorted(kwargs.items())])
        return f"{data_type}:{symbol}:{params}"

    def _is_cache_valid(self, cache_key: str, ttl_seconds: int = None) -> bool:
        """Kontrollera om cache är giltig."""
        if cache_key not in self._data_cache:
            return False

        ttl = ttl_seconds or self._cache_ttl_seconds
        cache_entry = self._data_cache[cache_key]
        age = (datetime.now() - cache_entry["timestamp"]).total_seconds()
        return age < ttl

    def _cleanup_expired_cache(self) -> None:
        """Rensa utgångna cache-entries."""
        now = datetime.now()
        if (now - self._last_cleanup).total_seconds() < 120:  # Rensa max var 2:e minut (tidigare 60s)
            return

        expired_keys = []
        for key, entry in self._data_cache.items():
            age = (now - entry["timestamp"]).total_seconds()
            # Använd margin TTL för margin-data
            ttl = self._margin_cache_ttl_seconds if "margin" in key else self._cache_ttl_seconds
            if age >= ttl:
                expired_keys.append(key)

        for key in expired_keys:
            del self._data_cache[key]

        self._last_cleanup = now
        if expired_keys:
            logger.debug(f"Rensade {len(expired_keys)} utgångna cache-entries")

    async def get_cached_data(self, data_type: str, symbol: str, fetch_func: Any, **kwargs: Any) -> Any | None:
        """
        Hämta data från cache eller via fetch_func om cache är utgången.

        Args:
            data_type: Typ av data (candles, ticker, etc.)
            symbol: Trading symbol
            fetch_func: Async funktion som hämtar data
            **kwargs: Ytterligare parametrar för cache-nyckel
        """
        cache_key = self._get_cache_key(data_type, symbol, **kwargs)

        # Använd margin TTL för margin-data
        ttl_seconds = self._margin_cache_ttl_seconds if "margin" in data_type else self._cache_ttl_seconds

        # Rensa utgångna cache-entries
        self._cleanup_expired_cache()

        # Kontrollera cache
        if self._is_cache_valid(cache_key, ttl_seconds):
            logger.debug(f"Cache-hit för {cache_key}")
            return self._data_cache[cache_key]["data"]

        # Skapa lock för denna request
        if cache_key not in self._request_locks:
            self._request_locks[cache_key] = asyncio.Lock()

        async with self._request_locks[cache_key]:
            # Dubbelkontrollera cache efter lock
            if self._is_cache_valid(cache_key, ttl_seconds):
                logger.debug(f"Cache-hit efter lock för {cache_key}")
                return self._data_cache[cache_key]["data"]

            try:
                # Hämta data via fetch_func
                data = await fetch_func(symbol, **kwargs)

                if data is not None:
                    # Spara i cache
                    self._data_cache[cache_key] = {"data": data, "timestamp": datetime.now()}
                    logger.debug(f"Cache-miss, sparade data för {cache_key}")

                return data

            except Exception as e:
                logger.error(f"Fel vid hämtning av {data_type} för {symbol}: {e}")
                return None

    async def get_candles(self, symbol: str, timeframe: str = "1m", limit: int = 100) -> list[list] | None:
        """Hämta candles med caching."""
        from services.bitfinex_data import BitfinexDataService

        data_service = BitfinexDataService()

        async def fetch_candles(sym: str, **kwargs: Any):
            return await data_service.get_candles(sym, timeframe, limit)

        return await self.get_cached_data("candles", symbol, fetch_candles, timeframe=timeframe, limit=limit)

    async def get_ticker(self, symbol: str) -> dict | None:
        """Hämta ticker med caching."""
        from services.bitfinex_data import BitfinexDataService

        data_service = BitfinexDataService()

        async def fetch_ticker(sym: str):
            return await data_service.get_ticker(sym)

        return await self.get_cached_data("ticker", symbol, fetch_ticker)

    async def get_margin_info(self) -> dict | None:
        """Hämta margin-info med förlängd caching."""
        from rest.margin import margin_service

        async def fetch_margin_info(_sym: str):
            margin_info = await margin_service.get_margin_info()
            return margin_info.dict() if margin_info else None

        # Använd intern TTL-styrning (margin TTL aktiveras automatiskt via data_type)
        return await self.get_cached_data("margin_info", "base", fetch_margin_info)

    async def get_margin_symbol_info(self, symbol: str) -> dict | None:
        """Hämta margin-info för specifik symbol med förlängd caching."""
        from rest.margin import margin_service

        async def fetch_margin_symbol(sym: str):
            margin_info = await margin_service.get_symbol_margin_status(sym)
            return margin_info if margin_info else None

        # Använd intern TTL-styrning (margin TTL aktiveras automatiskt via data_type)
        return await self.get_cached_data("margin_symbol", symbol, fetch_margin_symbol)

    async def batch_get_candles(self, symbols: list[str], timeframe: str = "15m", limit: int = 100) -> dict[str, list]:
        """
        Hämtar candles för flera symboler parallellt.

        Args:
            symbols: Lista med trading symbols
            timeframe: Tidsram för candles
            limit: Antal candles per symbol

        Returns:
            Dict med symbol -> candles mapping
        """
        try:
            from services.bitfinex_data import BitfinexDataService

            data_service = BitfinexDataService()

            # Skapa tasks för alla symboler
            tasks = []
            for symbol in symbols:
                task = self.get_cached_data(
                    "candles", symbol, data_service.get_candles, timeframe=timeframe, limit=limit
                )
                tasks.append(task)

            # Kör alla requests parallellt
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Mappa resultat till symboler
            candle_data = {}
            for i, result in enumerate(results):
                symbol = symbols[i]
                if isinstance(result, Exception):
                    logger.warning(f"Misslyckades att hämta candles för {symbol}: {result}")
                    candle_data[symbol] = None
                else:
                    candle_data[symbol] = result

            logger.info(f"Batch-hämtade candles för {len(symbols)} symboler")
            return candle_data

        except Exception as e:
            logger.error(f"Fel vid batch-hämtning av candles: {e}")
            return {symbol: None for symbol in symbols}

    async def batch_get_tickers(self, symbols: list[str]) -> dict[str, dict]:
        """
        Hämtar tickers för flera symboler parallellt.

        Args:
            symbols: Lista med trading symbols

        Returns:
            Dict med symbol -> ticker data mapping
        """
        try:
            from services.bitfinex_data import BitfinexDataService

            data_service = BitfinexDataService()

            # Skapa tasks för alla symboler
            tasks = []
            for symbol in symbols:
                task = self.get_cached_data("ticker", symbol, data_service.get_ticker)
                tasks.append(task)

            # Kör alla requests parallellt
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Mappa resultat till symboler
            ticker_data = {}
            for i, result in enumerate(results):
                symbol = symbols[i]
                if isinstance(result, Exception):
                    logger.warning(f"Misslyckades att hämta ticker för {symbol}: {result}")
                    ticker_data[symbol] = None
                else:
                    ticker_data[symbol] = result

            logger.info(f"Batch-hämtade tickers för {len(symbols)} symboler")
            return ticker_data

        except Exception as e:
            logger.error(f"Fel vid batch-hämtning av tickers: {e}")
            return {symbol: None for symbol in symbols}

    def get_cache_stats(self) -> dict[str, Any]:
        """Hämta cache-statistik."""
        now = datetime.now()
        total_entries = len(self._data_cache)
        valid_entries = sum(
            1
            for entry in self._data_cache.values()
            if (now - entry["timestamp"]).total_seconds() < self._cache_ttl_seconds
        )

        return {
            "total_entries": total_entries,
            "valid_entries": valid_entries,
            "expired_entries": total_entries - valid_entries,
            "cache_ttl_seconds": self._cache_ttl_seconds,
            "margin_cache_ttl_seconds": self._margin_cache_ttl_seconds,
            "active_locks": len(self._request_locks),
        }


# Global instans
data_coordinator = DataCoordinatorService()
