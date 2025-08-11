"""
Bitfinex Data Service - TradingBot Backend

Denna modul hanterar hämtning av marknadsdata från Bitfinex REST API.
Inkluderar candlestick-data, ticker-information och orderbook-data.
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from config.settings import Settings
from rest.auth import build_auth_headers
from utils.candle_cache import candle_cache
from utils.logger import get_logger

logger = get_logger(__name__)


class BitfinexDataService:
    """Service för att hämta marknadsdata från Bitfinex."""

    def __init__(self):
        self.settings = Settings()
        self.base_url = self.settings.BITFINEX_API_URL

    async def get_candles(
        self, symbol: str = "tBTCUSD", timeframe: str = "1m", limit: int = 100
    ) -> Optional[List[Dict]]:
        """
        Hämtar candlestick-data från Bitfinex.

        Args:
            symbol: Trading pair (t.ex. 'tBTCUSD')
            timeframe: Tidsram ('1m', '5m', '15m', '30m', '1h', '3h', '6h', '12h', '1D', '7D', '14D', '1M')
            limit: Antal candles att hämta (max 10000)

        Returns:
            Lista med candlestick-data eller None vid fel
        """
        try:
            symbol = (symbol or "").strip()
            # 1) Försök hämta från lokal cache
            cached = candle_cache.load(symbol, timeframe, limit)
            if cached:
                logger.debug(
                    f"Cache-hit: returnerar {len(cached)} candles för {symbol} {timeframe}"
                )
                return cached

            # 2) Annars hämta från Bitfinex och spara i cache (med retry/backoff)
            endpoint = f"candles/trade:{timeframe}:{symbol}/hist"
            url = f"{self.base_url}/{endpoint}"
            params = {"limit": limit}
            timeout = self.settings.DATA_HTTP_TIMEOUT
            retries = max(int(self.settings.DATA_MAX_RETRIES), 0)
            backoff_base = max(int(self.settings.DATA_BACKOFF_BASE_MS), 0) / 1000.0
            backoff_max = max(int(self.settings.DATA_BACKOFF_MAX_MS), 0) / 1000.0
            last_exc = None
            for attempt in range(retries + 1):
                try:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        logger.info(f"🌐 REST API: Hämtar candles från {url}")
                        response = await client.get(url, params=params)
                        if response.status_code in (429, 500, 502, 503, 504):
                            raise httpx.HTTPStatusError(
                                "server busy", request=None, response=response
                            )
                        response.raise_for_status()
                        candles = response.json()
                        logger.info(
                            f"✅ REST API: Hämtade {len(candles)} candles för {symbol} – cachar lokalt"
                        )
                        try:
                            candle_cache.store(symbol, timeframe, candles)
                        except Exception:
                            pass
                        return candles
                except Exception as e:
                    last_exc = e
                    if attempt < retries:
                        delay = min(
                            backoff_max, backoff_base * (2**attempt)
                        ) + random.uniform(0, 0.1)
                        await asyncio.sleep(delay)
                        continue
                    break
            logger.error(f"Fel vid hämtning av candles: {last_exc}")
            return None

        except Exception as e:
            logger.error(f"Fel vid hämtning av candles: {e}")
            return None

    async def get_ticker(self, symbol: str = "tBTCUSD") -> Optional[Dict]:
        """
        Hämtar ticker-information för en symbol.

        Args:
            symbol: Trading pair

        Returns:
            Dict med ticker-data eller None vid fel
        """
        try:
            import re

            symbol = (symbol or "").strip()
            # Normalisera testsymboler till kolonformat tTESTASSET:TESTUSD
            m = re.match(r"^tTEST([A-Z0-9]+)USD$", symbol)
            if m:
                asset = m.group(1)
                symbol = f"tTEST{asset}:TESTUSD"
            m = re.match(r"^tUSD:TEST([A-Z0-9]+)$", symbol)
            if m:
                asset = m.group(1)
                symbol = f"tTESTUSD:TEST{asset}"
            endpoint = f"ticker/{symbol}"
            url = f"{self.base_url}/{endpoint}"

            timeout = self.settings.DATA_HTTP_TIMEOUT
            retries = max(int(self.settings.DATA_MAX_RETRIES), 0)
            backoff_base = max(int(self.settings.DATA_BACKOFF_BASE_MS), 0) / 1000.0
            backoff_max = max(int(self.settings.DATA_BACKOFF_MAX_MS), 0) / 1000.0
            last_exc = None
            for attempt in range(retries + 1):
                try:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        logger.info(f"🌐 REST API: Hämtar ticker från {url}")
                        response = await client.get(url)
                        if response.status_code in (429, 500, 502, 503, 504):
                            raise httpx.HTTPStatusError(
                                "server busy", request=None, response=response
                            )
                        response.raise_for_status()
                        ticker = response.json()
                        logger.info(
                            f"✅ REST API: Hämtade ticker för {symbol}: {ticker[6]}"
                        )  # Last price
                        return {
                            "symbol": symbol,
                            "last_price": ticker[6],
                            "bid": ticker[0],
                            "ask": ticker[2],
                            "high": ticker[8],
                            "low": ticker[9],
                            "volume": ticker[7],
                        }
                except Exception as e:
                    last_exc = e
                    if attempt < retries:
                        delay = min(
                            backoff_max, backoff_base * (2**attempt)
                        ) + random.uniform(0, 0.1)
                        await asyncio.sleep(delay)
                        continue
                    break
            logger.error(f"Fel vid hämtning av ticker: {last_exc}")
            return None

        except Exception as e:
            logger.error(f"Fel vid hämtning av ticker: {e}")
            return None

    async def backfill_history(
        self,
        symbol: str,
        timeframe: str,
        max_batches: int = 20,
        batch_limit: int = 1000,
    ) -> int:
        """Hämta äldre historik och fyll cache med paginering och dedupe.

        - Startar från äldsta kända i cache (eller nu) och går bakåt i tiden.
        - Använder UPSERT i cache, så duplicering skadar inte.
        """
        try:
            from sqlite3 import Row

            # Hitta minsta mts i cache för symbol/timeframe
            oldest_mts = None
            try:
                import sqlite3

                with sqlite3.connect(candle_cache.db_path) as conn:
                    conn.row_factory = Row
                    row = conn.execute(
                        "SELECT MIN(mts) AS m FROM candles WHERE symbol=? AND timeframe=?",
                        (symbol, timeframe),
                    ).fetchone()
                    oldest_mts = int(row["m"]) if row and row["m"] is not None else None
            except Exception:
                oldest_mts = None

            total_inserted = 0
            end_param = oldest_mts - 1 if oldest_mts else None

            timeout = self.settings.DATA_HTTP_TIMEOUT
            retries = max(int(self.settings.DATA_MAX_RETRIES), 0)
            backoff_base = max(int(self.settings.DATA_BACKOFF_BASE_MS), 0) / 1000.0
            backoff_max = max(int(self.settings.DATA_BACKOFF_MAX_MS), 0) / 1000.0

            for b in range(max_batches):
                params = {"limit": batch_limit, "sort": 1}  # sort=1 => äldst->nyast
                if end_param is not None:
                    params["end"] = int(end_param)
                endpoint = f"candles/trade:{timeframe}:{symbol}/hist"
                url = f"{self.base_url}/{endpoint}"
                last_exc = None
                candles = None
                for attempt in range(retries + 1):
                    try:
                        async with httpx.AsyncClient(timeout=timeout) as client:
                            resp = await client.get(url, params=params)
                            if resp.status_code in (429, 500, 502, 503, 504):
                                raise httpx.HTTPStatusError(
                                    "server busy", request=None, response=resp
                                )
                            resp.raise_for_status()
                            candles = resp.json() or []
                            break
                    except Exception as e:
                        last_exc = e
                        if attempt < retries:
                            delay = min(
                                backoff_max, backoff_base * (2**attempt)
                            ) + random.uniform(0, 0.1)
                            await asyncio.sleep(delay)
                            continue
                        break
                if candles is None:
                    logger.warning(f"Backfill misslyckades: {last_exc}")
                    break
                if not candles:
                    # ingen mer historik
                    break
                # Spara och uppdatera nästa end till före äldsta mts i denna batch
                try:
                    inserted = candle_cache.store(symbol, timeframe, candles)
                    total_inserted += inserted
                except Exception:
                    pass
                oldest_in_batch = int(candles[0][0]) if candles else None
                if oldest_in_batch is None:
                    break
                end_param = oldest_in_batch - 1
            return total_inserted
        except Exception as e:
            logger.warning(f"Backfill fel: {e}")
            return 0

    def parse_candles_to_strategy_data(
        self, candles: List[List]
    ) -> Dict[str, List[float]]:
        """
        Konverterar candlestick-data till format för strategiutvärdering.

        Args:
            candles: Lista med candle-data från Bitfinex

        Returns:
            Dict med closes, highs, lows för strategiutvärdering
        """
        if not candles:
            return {"closes": [], "highs": [], "lows": []}

        # Bitfinex candle format: [MTS, OPEN, CLOSE, HIGH, LOW, VOLUME]
        closes = [candle[2] for candle in candles]
        highs = [candle[3] for candle in candles]
        lows = [candle[4] for candle in candles]

        logger.debug(f"Parsade {len(closes)} datapunkter för strategiutvärdering")

        return {"closes": closes, "highs": highs, "lows": lows}


# Global instans för enkel åtkomst
bitfinex_data = BitfinexDataService()
