"""
Bitfinex Data Service - TradingBot Backend

Denna modul hanterar hämtning av marknadsdata från Bitfinex REST API.
Inkluderar candlestick-data, ticker-information och orderbook-data.
"""

import asyncio
import random
import time
from typing import Dict, List, Optional

import httpx

from config.settings import Settings
from services.bitfinex_websocket import bitfinex_ws
from utils.candle_cache import candle_cache
from utils.logger import get_logger

logger = get_logger(__name__)


# Global TTL-cache för ticker
_TICKER_CACHE: Dict[str, Dict] = {}
# In-flight lås per symbol för att samköra REST-förfrågningar
_TICKER_LOCKS: Dict[str, asyncio.Lock] = {}


class BitfinexDataService:
    """Service för att hämta marknadsdata från Bitfinex."""

    def __init__(self):
        self.settings = Settings()
        # Använd publik bas-URL för public endpoints
        self.base_url = getattr(self.settings, "BITFINEX_PUBLIC_API_URL", None) or self.settings.BITFINEX_API_URL

    async def get_candles(
        self, symbol: str = "tBTCUSD", timeframe: str = "1m", limit: int = 100
    ) -> Optional[List[List]]:
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
                    "Cache-hit: returnerar %s candles för %s %s",
                    len(cached),
                    symbol,
                    timeframe,
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
                        logger.info("🌐 REST API: Hämtar candles från %s", url)
                        response = await client.get(url, params=params)
                        if response.status_code in (429, 500, 502, 503, 504):
                            raise httpx.HTTPStatusError(
                                "server busy",
                                request=response.request,
                                response=response,
                            )
                        response.raise_for_status()
                        candles = response.json()
                        logger.info(
                            "✅ REST API: Hämtade %s candles för %s – cachar lokalt",
                            len(candles),
                            symbol,
                        )
                        try:
                            candle_cache.store(symbol, timeframe, candles)
                        except Exception:
                            pass
                        return candles
                except Exception as e:
                    last_exc = e
                    if attempt < retries:
                        delay = min(backoff_max, backoff_base * (2**attempt)) + random.uniform(0, 0.1)
                        await asyncio.sleep(delay)
                        continue
                    break
            logger.error("Fel vid hämtning av candles: %s", last_exc)
            return None

        except Exception as e:
            logger.error("Fel vid hämtning av candles: %s", e)
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

            # Mappa testsymbol till verklig Bitfinex-symbol för pris (fallback)
            # tTESTBTC:TESTUSD -> tBTCUSD, tTESTUSD:TESTBTC -> tBTCUSD
            # tTESTBTC:TESTUSDT -> tBTCUST (Bitfinex ticker använder UST för Tether)
            eff_symbol = symbol
            m = re.match(r"^tTEST([A-Z0-9]+):TESTUSD$", eff_symbol)
            if m:
                asset = m.group(1)
                eff_symbol = f"t{asset}USD"
            else:
                m = re.match(r"^tTESTUSD:TEST([A-Z0-9]+)$", eff_symbol)
                if m:
                    asset = m.group(1)
                    eff_symbol = f"t{asset}USD"
                else:
                    m = re.match(r"^tTEST([A-Z0-9]+):TESTUSDT$", eff_symbol)
                    if m:
                        asset = m.group(1)
                        eff_symbol = f"t{asset}UST"
                    else:
                        m = re.match(r"^tTESTUSDT:TEST([A-Z0-9]+)$", eff_symbol)
                        if m:
                            asset = m.group(1)
                            eff_symbol = f"t{asset}UST"
            # Enkel TTL‑cache för ticker (per eff_symbol)
            _ttl = max(int(getattr(self.settings, "TICKER_CACHE_TTL_SECS", 10) or 10), 1)
            cache_key = f"ticker::{eff_symbol}"
            entry = _TICKER_CACHE.get(cache_key)
            now = time.time()
            if entry and (now - entry.get("ts", 0)) <= _ttl:
                values = entry.get("values", {}) or {}
                # Returnera kopia med originalsymbolen
                return {
                    "symbol": symbol,
                    "last_price": values.get("last_price"),
                    "bid": values.get("bid"),
                    "ask": values.get("ask"),
                    "high": values.get("high"),
                    "low": values.get("low"),
                    "volume": values.get("volume"),
                }

            # 0) Om WS har färsk ticker för eff_symbol, använd den och hoppa REST
            try:
                ws_stale_secs = int(getattr(self.settings, "WS_TICKER_STALE_SECS", 10) or 10)
                ws_warmup_ms = int(getattr(self.settings, "WS_TICKER_WARMUP_MS", 400) or 400)
                # använd last_tick_ts om tillgängligt
                import time as _t

                last_ts = None
                last_price = None
                cand_syms = [symbol, eff_symbol]
                for s in cand_syms:
                    if hasattr(bitfinex_ws, "_last_tick_ts"):
                        last_ts = bitfinex_ws._last_tick_ts.get(s)  # type: ignore[attr-defined]
                    if last_ts:
                        last_price = bitfinex_ws.latest_prices.get(s)
                        break
                if last_ts and (_t.time() - float(last_ts)) <= ws_stale_secs and last_price is not None:
                    # Fyll från senaste fulla WS‑ticker-frame om tillgänglig
                    bid = None
                    ask = None
                    high = None
                    low = None
                    volume = None
                    frame = None
                    for s in cand_syms:
                        frame = getattr(bitfinex_ws, "latest_ticker_frames", {}).get(s)
                        if frame:
                            break
                    if isinstance(frame, dict):
                        bid = frame.get("bid")
                        ask = frame.get("ask")
                        high = frame.get("high")
                        low = frame.get("low")
                        volume = frame.get("volume")
                    return {
                        "symbol": symbol,
                        "last_price": last_price,
                        "bid": bid,
                        "ask": ask,
                        "high": high,
                        "low": low,
                        "volume": volume,
                    }

                # 0b) Auto-subscribe om inte färsk WS-data och vi inte redan sub:at
                try:
                    sub_key = f"ticker|{eff_symbol}"
                    already_subscribed = sub_key in getattr(bitfinex_ws, "subscriptions", {})
                    if not already_subscribed:
                        # registrera strategi/ticker-callback om inte finns
                        if eff_symbol not in getattr(bitfinex_ws, "strategy_callbacks", {}):
                            bitfinex_ws.strategy_callbacks[eff_symbol] = bitfinex_ws._handle_ticker_with_strategy
                        await bitfinex_ws.subscribe_ticker(eff_symbol, bitfinex_ws._handle_ticker_with_strategy)
                        # Vänta kort på första tick innan REST-fallback
                        warmup_deadline = _t.time() + (ws_warmup_ms / 1000.0)
                        while _t.time() < warmup_deadline:
                            last_ts = None
                            last_price = None
                            for s in cand_syms:
                                last_ts = getattr(bitfinex_ws, "_last_tick_ts", {}).get(s)
                                if last_ts:
                                    last_price = bitfinex_ws.latest_prices.get(s)
                                    break
                            if last_ts and (_t.time() - float(last_ts)) <= ws_stale_secs and last_price is not None:
                                frame = None
                                bid = ask = high = low = volume = None
                                for s in cand_syms:
                                    frame = getattr(bitfinex_ws, "latest_ticker_frames", {}).get(s)
                                    if frame:
                                        break
                                if isinstance(frame, dict):
                                    bid = frame.get("bid")
                                    ask = frame.get("ask")
                                    high = frame.get("high")
                                    low = frame.get("low")
                                    volume = frame.get("volume")
                                return {
                                    "symbol": symbol,
                                    "last_price": last_price,
                                    "bid": bid,
                                    "ask": ask,
                                    "high": high,
                                    "low": low,
                                    "volume": volume,
                                }
                            await asyncio.sleep(0.05)
                except Exception:
                    pass
            except Exception:
                pass

            endpoint = f"ticker/{eff_symbol}"
            url = f"{self.base_url}/{endpoint}"

            timeout = self.settings.DATA_HTTP_TIMEOUT
            retries = max(int(self.settings.DATA_MAX_RETRIES), 0)
            backoff_base = max(int(self.settings.DATA_BACKOFF_BASE_MS), 0) / 1000.0
            backoff_max = max(int(self.settings.DATA_BACKOFF_MAX_MS), 0) / 1000.0
            last_exc = None

            # In-flight lås per symbol så endast ett REST-anrop sker åt gången
            lock = _TICKER_LOCKS.get(eff_symbol)
            if lock is None:
                lock = asyncio.Lock()
                _TICKER_LOCKS[eff_symbol] = lock

            async with lock:
                # Re-check cache under lås (kan ha fyllts av parallell request)
                now = time.time()
                entry = _TICKER_CACHE.get(cache_key)
                if entry and (now - entry.get("ts", 0)) <= _ttl:
                    values = entry.get("values", {}) or {}
                    return {
                        "symbol": symbol,
                        "last_price": values.get("last_price"),
                        "bid": values.get("bid"),
                        "ask": values.get("ask"),
                        "high": values.get("high"),
                        "low": values.get("low"),
                        "volume": values.get("volume"),
                    }

                for attempt in range(retries + 1):
                    try:
                        async with httpx.AsyncClient(timeout=timeout) as client:
                            logger.info("🌐 REST API: Hämtar ticker från %s", url)
                            response = await client.get(url)
                            if response.status_code in (429, 500, 502, 503, 504):
                                raise httpx.HTTPStatusError(
                                    "server busy",
                                    request=response.request,
                                    response=response,
                                )
                            response.raise_for_status()
                            ticker = response.json()
                            logger.info(
                                "✅ REST API: Hämtade ticker för %s: %s",
                                eff_symbol,
                                ticker[6],
                            )  # Last price
                            out = {
                                "symbol": symbol,
                                "last_price": ticker[6],
                                "bid": ticker[0],
                                "ask": ticker[2],
                                "high": ticker[8],
                                "low": ticker[9],
                                "volume": ticker[7],
                            }
                            # Cacha värden (utan symbolbindning) med kort TTL
                            try:
                                now = time.time()
                                _TICKER_CACHE[cache_key] = {
                                    "ts": now,
                                    "values": {
                                        "last_price": out["last_price"],
                                        "bid": out["bid"],
                                        "ask": out["ask"],
                                        "high": out["high"],
                                        "low": out["low"],
                                        "volume": out["volume"],
                                    },
                                }
                            except Exception:
                                pass
                            return out
                    except Exception as e:
                        last_exc = e
                        if attempt < retries:
                            delay = min(backoff_max, backoff_base * (2**attempt)) + random.uniform(0, 0.1)
                            await asyncio.sleep(delay)
                            continue
                        break
            logger.error("Fel vid hämtning av ticker: %s", last_exc)
            return None

        except Exception as e:
            logger.error("Fel vid hämtning av ticker: %s", e)
            return None

    async def get_tickers(self, symbols: List[str]) -> Optional[List[List]]:
        """
        Hämta flera tickers i batch via REST public.

        Args:
            symbols: Lista av Bitfinex v2-symboler (t.ex. ['tBTCUSD','tETHUSD'])

        Returns:
            List med ticker-rader (Bitfinex format) eller None vid fel
        """
        try:
            if not symbols:
                return []
            # Bitfinex endpoint: /v2/tickers?symbols=tBTCUSD,tETHUSD
            qs = ",".join(symbols)
            url = f"{self.base_url}/tickers?symbols={qs}"
            timeout = self.settings.DATA_HTTP_TIMEOUT
            retries = max(int(self.settings.DATA_MAX_RETRIES), 0)
            backoff_base = max(int(self.settings.DATA_BACKOFF_BASE_MS), 0) / 1000.0
            backoff_max = max(int(self.settings.DATA_BACKOFF_MAX_MS), 0) / 1000.0
            last_exc = None
            for attempt in range(retries + 1):
                try:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        logger.info("🌐 REST API: Hämtar tickers (batch)")
                        resp = await client.get(url)
                        if resp.status_code in (429, 500, 502, 503, 504):
                            raise httpx.HTTPStatusError("server busy", request=resp.request, response=resp)
                        resp.raise_for_status()
                        data = resp.json()
                        # Uppdatera cache och ev. latest_prices med snapshot
                        now = time.time()
                        try:
                            for row in data or []:
                                if not row or not isinstance(row, list):
                                    continue
                                # Ticker-rad format: [SYMBOL, BID, BID_SIZE, ASK, ASK_SIZE, DAILY_CHANGE, DAILY_CHANGE_RELATIVE, LAST_PRICE, VOLUME, HIGH, LOW]
                                sy = row[0]
                                out = {
                                    "last_price": row[7] if len(row) > 7 else None,
                                    "bid": row[1] if len(row) > 1 else None,
                                    "ask": row[3] if len(row) > 3 else None,
                                    "high": row[9] if len(row) > 9 else None,
                                    "low": row[10] if len(row) > 10 else None,
                                    "volume": row[8] if len(row) > 8 else None,
                                }
                                _TICKER_CACHE[f"ticker::{sy}"] = {
                                    "ts": now,
                                    "values": out,
                                }
                                # Om WS inte levererar ännu, fyll latest_prices som snapshot
                                try:
                                    if out["last_price"] is not None and sy not in bitfinex_ws.latest_prices:
                                        bitfinex_ws.latest_prices[sy] = out["last_price"]
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        return data
                except Exception as e:
                    last_exc = e
                    if attempt < retries:
                        delay = min(backoff_max, backoff_base * (2**attempt)) + random.uniform(0, 0.1)
                        await asyncio.sleep(delay)
                        continue
                    break
            logger.warning("tickers batch misslyckades: %s", last_exc)
            return None
        except Exception as e:
            logger.error("Fel vid hämtning av tickers (batch): %s", e)
            return None

    async def get_platform_status(self) -> Optional[List[int]]:
        """
        Hämta Bitfinex plattformsstatus via REST public.
        Returns: [status] (1=up, 0=maintenance) eller None vid fel.
        """
        try:
            url = f"{self.base_url}/platform/status"
            async with httpx.AsyncClient(timeout=self.settings.DATA_HTTP_TIMEOUT) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning(f"Fel vid hämtning av platform status: {e}")
            return None

    async def get_configs_symbols(self) -> Optional[List[str]]:
        """
        Hämta symboler via REST public Configs (ersätta statisk lista).
        """
        try:
            # Enklare variant: configs/symbols kan kräva parse; Bitfinex har olika config endpoints.
            # Vi använder /conf för att hämta t.ex. 'pub:list:pair:exchange'
            url = f"{self.base_url}/conf/pub:list:pair:exchange"
            async with httpx.AsyncClient(timeout=self.settings.DATA_HTTP_TIMEOUT) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                # Förväntat format: [["BTCUSD","ETHUSD",...]]
                if isinstance(data, list) and data and isinstance(data[0], list):
                    return [str(s) for s in data[0]]
                return None
        except Exception as e:
            logger.warning("Fel vid hämtning av configs symbols: %s", e)
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

            for _ in range(max_batches):
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
                                raise httpx.HTTPStatusError("server busy", request=resp.request, response=resp)
                            resp.raise_for_status()
                            candles = resp.json() or []
                            break
                    except Exception as e:
                        last_exc = e
                        if attempt < retries:
                            delay = min(backoff_max, backoff_base * (2**attempt)) + random.uniform(0, 0.1)
                            await asyncio.sleep(delay)
                            continue
                        break
                if candles is None:
                    logger.warning("Backfill misslyckades: %s", last_exc)
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
            logger.warning("Backfill fel: %s", e)
            return 0

    def parse_candles_to_strategy_data(self, candles: List[List]) -> Dict[str, List[float]]:
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

        logger.debug("Parsade %s datapunkter för strategiutvärdering", len(closes))

        return {"closes": closes, "highs": highs, "lows": lows}


# Global instans för enkel åtkomst
bitfinex_data = BitfinexDataService()
