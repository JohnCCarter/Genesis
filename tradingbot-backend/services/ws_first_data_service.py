"""
WebSocket-First Data Service - TradingBot Backend

Prioriterar WebSocket för marknadsdata med intelligent fallback till REST.
Implementerar debounce, throttling och backpressure hantering.
"""

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from utils.advanced_rate_limiter import get_advanced_rate_limiter
from utils.logger import get_logger

from services.bitfinex_data import BitfinexDataService
from services.bitfinex_websocket import bitfinex_ws
from services.incremental_indicators import ATRState, EMAState, RSIState

logger = get_logger(__name__)


@dataclass
class DataPoint:
    """Datapunkt med timestamp"""

    symbol: str
    data: dict[str, Any]
    timestamp: float
    source: str  # "ws" eller "rest"


class WSFirstDataService:
    """
    WebSocket-first data service med intelligent caching och fallback.

    Funktioner:
    - WS-prioritet för alla marknadsdata
    - Intelligent REST-fallback
    - Debounce för uppdateringar
    - Backpressure hantering
    - Rate limiting integration
    """

    def __init__(self):
        self.rest_service = BitfinexDataService()
        self.rate_limiter = get_advanced_rate_limiter()
        self._initialized: bool = False

        # Data caches
        self._ticker_cache: dict[str, DataPoint] = {}
        self._candle_cache: dict[str, dict[str, DataPoint]] = defaultdict(dict)  # symbol -> timeframe -> data

        # Freshness thresholds
        self.ticker_stale_seconds = 30
        self.candle_stale_seconds = 300  # 5 minuter för candles

        # Debounce/throttle settings
        self._update_queues: dict[str, deque] = defaultdict(deque)
        self._last_update_time: dict[str, float] = {}
        self.debounce_ms = 200  # Max en uppdatering per 200ms per symbol

        # Backpressure settings
        self.max_queue_size = 100

        # Candle WS queues/throttle
        self._candle_queues: dict[str, deque] = defaultdict(lambda: deque(maxlen=500))
        self._candle_last_update: dict[str, float] = {}
        self.candle_debounce_ms = 250

        # Statistics
        self.stats = {"ws_hits": 0, "rest_fallbacks": 0, "debounced_updates": 0, "cache_hits": 0}

        # Inkrementella indikatorer per (symbol|timeframe)
        self._ema_state: dict[str, EMAState] = {}
        self._rsi_state: dict[str, RSIState] = {}
        self._atr_state: dict[str, ATRState] = {}
        self._ind_values: dict[str, dict] = {}

    async def initialize(self) -> None:
        """Initialisera WS-anslutning och prenumerationer"""
        try:
            if self._initialized:
                return
            if not bitfinex_ws.is_connected:
                await bitfinex_ws.connect()

            # Prenumerera på standardsymboler
            from config.settings import Settings

            settings = Settings()

            if settings.WS_SUBSCRIBE_SYMBOLS:
                symbols = [s.strip() for s in settings.WS_SUBSCRIBE_SYMBOLS.split(",")]
                logger.info(f"🚀 Initialiserar WS-prenumerationer för {len(symbols)} symboler")

                # Timeframes att prenumerera på (ex: 1m,5m)
                try:
                    tfs = [tf.strip() for tf in Settings().WS_CANDLE_TIMEFRAMES.split(",") if tf.strip()]
                except Exception:
                    tfs = ["1m", "5m"]

                backfill_pairs: list[tuple[str, str]] = []
                for symbol in symbols[:6]:  # Begränsa till 6 för att undvika rate limits
                    try:
                        await bitfinex_ws.subscribe_ticker(symbol=symbol, callback=self._handle_ws_ticker)

                        # Prenumerera på candles för alla timeframes
                        for tf in tfs:

                            async def _cb(data, sym=symbol, tf=tf):
                                await self._handle_ws_candles(sym, tf, data)

                            await bitfinex_ws.subscribe_candles(symbol=symbol, timeframe=tf, callback=_cb)
                            backfill_pairs.append((symbol, tf))
                            await asyncio.sleep(0.05)
                        await asyncio.sleep(0.1)  # Små pauser mellan symboler
                    except Exception as e:
                        logger.warning(f"Kunde inte prenumerera på {symbol}: {e}")

            logger.info("✅ WS-First Data Service initialiserad")
            self._initialized = True

            # Starta REST-backfill i bakgrunden (fönster, staggered) för varje (symbol, timeframe)
            try:
                if backfill_pairs:
                    asyncio.create_task(self._run_backfills(backfill_pairs), name="wsfirst-backfill")
            except Exception:
                pass

        except Exception as e:
            logger.error(f"❌ Fel vid initialisering av WS-First Data Service: {e}")

    async def _handle_ws_candles(self, symbol: str, timeframe: str, message_data: list | tuple | dict | None) -> None:
        """Hantera WS candles-data (snapshot eller uppdateringar)."""
        try:
            now = time.time()
            key = f"{symbol}|{timeframe}"
            # Debounce per symbol/timeframe
            last = float(self._candle_last_update.get(key, 0) or 0)
            if now - last < (self.candle_debounce_ms / 1000.0):
                return

            dq = self._candle_queues[key]
            # Snapshot: lista av listor
            if isinstance(message_data, list) and message_data and isinstance(message_data[0], list):
                # Ta senaste upp till 500
                for row in message_data[-500:]:
                    if isinstance(row, (list, tuple)) and len(row) >= 6:
                        dq.append([row[0], row[1], row[2], row[3], row[4], row[5]])
            # Enstaka uppdatering
            elif isinstance(message_data, list) and len(message_data) >= 6:
                mts = message_data[0]
                # undvik dubbletter: om sista har samma mts, ersätt
                if dq and isinstance(dq[-1], list) and len(dq[-1]) >= 1 and dq[-1][0] == mts:
                    dq[-1] = [
                        message_data[0],
                        message_data[1],
                        message_data[2],
                        message_data[3],
                        message_data[4],
                        message_data[5],
                    ]
                else:
                    dq.append(
                        [
                            message_data[0],
                            message_data[1],
                            message_data[2],
                            message_data[3],
                            message_data[4],
                            message_data[5],
                        ]
                    )
            else:
                # Ignorera heartbeats eller okända format
                return

            # Uppdatera cachedatapunkt från de senaste N
            # Begränsa längd till 'limit' när get_candles begär; här lagrar vi en god buffert
            latest_list = list(dq)
            self._candle_last_update[key] = now
            # Backpressure: vi använder maxlen på deque så äldsta släpps automatiskt

            # Skriv till cache med DataPoint
            data_point = DataPoint(symbol=symbol, data=latest_list, timestamp=now, source="ws")
            self._candle_cache[symbol][timeframe] = data_point
            self.stats["ws_hits"] += 1

            # Uppdatera inkrementella indikatorer
            last = latest_list[-1] if latest_list else None
            if isinstance(last, (list, tuple)) and len(last) >= 5:
                mts = last[0]
                o = last[1]
                c = last[2]
                h = last[3]
                low_val = last[4]
                # Läs perioder från strategiinställningar
                try:
                    from services.strategy_settings import StrategySettingsService

                    ssvc = StrategySettingsService()
                    s = ssvc.get_settings(symbol=symbol)
                    ema_p, rsi_p, atr_p = int(s.ema_period), int(s.rsi_period), int(s.atr_period)
                except Exception:
                    ema_p = rsi_p = atr_p = 14

                ind_key = key
                if ind_key not in self._ema_state:
                    self._ema_state[ind_key] = EMAState(period=ema_p)
                if ind_key not in self._rsi_state:
                    self._rsi_state[ind_key] = RSIState(period=rsi_p)
                if ind_key not in self._atr_state:
                    self._atr_state[ind_key] = ATRState(period=atr_p)

                # Seed vid behov med senaste historiken
                try:
                    closes = [row[2] for row in latest_list if isinstance(row, (list, tuple)) and len(row) >= 3]
                    highs = [row[3] for row in latest_list if isinstance(row, (list, tuple)) and len(row) >= 4]
                    lows = [row[4] for row in latest_list if isinstance(row, (list, tuple)) and len(row) >= 5]
                    if self._ema_state[ind_key].value is None:
                        for px in closes[-ema_p:]:
                            self._ema_state[ind_key].update(float(px))
                    if self._rsi_state[ind_key].prev_close is None and len(closes) >= 2:
                        for px in closes[-(rsi_p + 1) :]:
                            self._rsi_state[ind_key].update(float(px))
                    if self._atr_state[ind_key].prev_close is None and len(highs) == len(lows) == len(closes):
                        start = max(0, len(closes) - atr_p)
                        for i in range(start, len(closes)):
                            self._atr_state[ind_key].update(float(highs[i]), float(lows[i]), float(closes[i]))
                except Exception:
                    pass

                ema_val = self._ema_state[ind_key].update(float(c))
                rsi_val = self._rsi_state[ind_key].update(float(c))
                atr_val = self._atr_state[ind_key].update(float(h), float(low_val), float(c))
                self._ind_values[ind_key] = {
                    "ema": float(ema_val),
                    "rsi": float(rsi_val),
                    "atr": float(atr_val),
                }
        except Exception as e:
            logger.error(f"Fel vid hantering av WS candles för {symbol} {timeframe}: {e}")

    def _handle_ws_ticker(self, symbol: str, ticker_data: dict[str, Any]) -> None:
        """Hantera WS ticker-data med debounce"""
        try:
            now = time.time()

            # Debounce check
            last_update = self._last_update_time.get(symbol, 0)
            if now - last_update < (self.debounce_ms / 1000):
                self.stats["debounced_updates"] += 1
                return

            # Uppdatera cache
            data_point = DataPoint(symbol=symbol, data=ticker_data, timestamp=now, source="ws")

            self._ticker_cache[symbol] = data_point
            self._last_update_time[symbol] = now
            self.stats["ws_hits"] += 1

            # Backpressure hantering
            queue = self._update_queues[symbol]
            if len(queue) >= self.max_queue_size:
                # Släpp äldsta
                queue.popleft()

            queue.append(data_point)

        except Exception as e:
            logger.error(f"Fel vid hantering av WS ticker för {symbol}: {e}")

    async def get_ticker(self, symbol: str, force_fresh: bool = False) -> dict[str, Any] | None:
        """
        Hämta ticker-data med WS-prioritet.

        Args:
            symbol: Trading symbol
            force_fresh: Tvinga ny data från API

        Returns:
            Ticker data eller None
        """
        try:
            now = time.time()

            # Kontrollera WS cache först (om inte force_fresh)
            if not force_fresh and symbol in self._ticker_cache:
                cached = self._ticker_cache[symbol]
                if now - cached.timestamp < self.ticker_stale_seconds:
                    self.stats["cache_hits"] += 1
                    return cached.data

            # WS-data för gammal eller saknas, använd REST fallback
            logger.debug(f"🔄 REST fallback för ticker {symbol}")
            self.stats["rest_fallbacks"] += 1

            # Använd rate limiter för REST-anrop
            await self.rate_limiter.wait_if_needed(f"ticker/{symbol}")

            ticker_data = await self.rest_service.get_ticker(symbol)

            if ticker_data:
                # Uppdatera cache med REST-data
                data_point = DataPoint(symbol=symbol, data=ticker_data, timestamp=now, source="rest")
                self._ticker_cache[symbol] = data_point

            return ticker_data

        except Exception as e:
            logger.error(f"Fel vid hämtning av ticker för {symbol}: {e}")
            return None

    async def get_candles(
        self, symbol: str, timeframe: str = "1m", limit: int = 100, force_fresh: bool = False
    ) -> list | None:
        """
        Hämta candle-data med intelligent caching.

        Args:
            symbol: Trading symbol
            timeframe: Tidsram (1m, 5m, 1h, etc.)
            limit: Antal candles
            force_fresh: Tvinga ny data från API

        Returns:
            Candle data eller None
        """
        try:
            now = time.time()
            cache_key = f"{symbol}_{timeframe}_{limit}"

            # Kontrollera cache först
            if not force_fresh and timeframe in self._candle_cache[symbol]:
                cached = self._candle_cache[symbol][timeframe]
                if now - cached.timestamp < self.candle_stale_seconds:
                    self.stats["cache_hits"] += 1
                    return cached.data

            # Om vi har WS-kö men stale cache, returnera senaste 'limit' från WS medan REST fyller bakgrund
            try:
                key = f"{symbol}|{timeframe}"
                if self._candle_queues.get(key):
                    latest = list(self._candle_queues[key])[-limit:]
                    # Uppdatera cachetimestamp
                    self._candle_cache[symbol][timeframe] = DataPoint(
                        symbol=symbol, data=latest, timestamp=now, source="ws"
                    )
                    return latest
            except Exception:
                pass

            # Cache miss eller för gammal, hämta från REST
            logger.debug(f"🔄 REST fallback för candles {symbol} {timeframe}")
            self.stats["rest_fallbacks"] += 1

            # Använd rate limiter för REST-anrop
            await self.rate_limiter.wait_if_needed(f"candles/{symbol}")

            candle_data = await self.rest_service.get_candles(symbol, timeframe, limit)

            if candle_data:
                # Uppdatera cache
                data_point = DataPoint(symbol=symbol, data=candle_data, timestamp=now, source="rest")
                self._candle_cache[symbol][timeframe] = data_point

                # Beräkna och spara indikator-snapshot från REST-data (för initialt läge)
                try:
                    key = f"{symbol}|{timeframe}"
                    closes = [row[2] for row in candle_data if isinstance(row, (list, tuple)) and len(row) >= 3]
                    highs = [row[3] for row in candle_data if isinstance(row, (list, tuple)) and len(row) >= 4]
                    lows = [row[4] for row in candle_data if isinstance(row, (list, tuple)) and len(row) >= 5]
                    if closes:
                        try:
                            from services.strategy_settings import StrategySettingsService

                            ssvc = StrategySettingsService()
                            s = ssvc.get_settings(symbol=symbol)
                            ema_p, rsi_p, atr_p = (
                                int(s.ema_period),
                                int(s.rsi_period),
                                int(s.atr_period),
                            )
                        except Exception:
                            ema_p = rsi_p = atr_p = 14
                        if key not in self._ema_state:
                            self._ema_state[key] = EMAState(period=ema_p)
                        if key not in self._rsi_state:
                            self._rsi_state[key] = RSIState(period=rsi_p)
                        if key not in self._atr_state:
                            self._atr_state[key] = ATRState(period=atr_p)
                        # Seed om oinitierat
                        if self._ema_state[key].value is None:
                            for px in closes[-ema_p:]:
                                self._ema_state[key].update(float(px))
                        if self._rsi_state[key].prev_close is None:
                            for px in closes[-(rsi_p + 1) :]:
                                self._rsi_state[key].update(float(px))
                        if self._atr_state[key].prev_close is None and len(highs) == len(lows) == len(closes):
                            for i in range(max(0, len(closes) - atr_p), len(closes)):
                                self._atr_state[key].update(float(highs[i]), float(lows[i]), float(closes[i]))
                        # Inkrementellt med sista raden
                        last_close = float(closes[-1])
                        last_high = float(highs[-1]) if highs else last_close
                        last_low = float(lows[-1]) if lows else last_close
                        ema_val = self._ema_state[key].update(last_close)
                        rsi_val = self._rsi_state[key].update(last_close)
                        atr_val = self._atr_state[key].update(last_high, last_low, last_close)
                        self._ind_values[key] = {
                            "ema": float(ema_val),
                            "rsi": float(rsi_val),
                            "atr": float(atr_val),
                        }
                except Exception:
                    pass

            return candle_data

        except Exception as e:
            logger.error(f"Fel vid hämtning av candles för {symbol}: {e}")
            return None

    def get_indicator_snapshot(self, symbol: str, timeframe: str) -> dict | None:
        """Returnera inkrementella indikatorvärden om tillgängliga."""
        key = f"{symbol}|{timeframe}"
        return self._ind_values.get(key)

    def get_live_symbols(self) -> set:
        """Returnera symboler som har live WS-data"""
        now = time.time()
        live_symbols = set()

        for symbol, data_point in self._ticker_cache.items():
            if data_point.source == "ws" and now - data_point.timestamp < self.ticker_stale_seconds:
                live_symbols.add(symbol)

        return live_symbols

    async def _run_backfills(self, pairs: list[tuple[str, str]]) -> None:
        """Kör REST-backfill i fönster per symbol/timeframe, med paus mellan batcher."""
        try:
            # Staggera för att undvika bursts
            for idx, (sym, tf) in enumerate(pairs):
                try:
                    await asyncio.sleep(0.2 * idx)
                    # Kör begränsad backfill per par – justerbart via Settings om behövs
                    inserted = await self.rest_service.backfill_history(sym, tf, max_batches=5, batch_limit=1000)
                    logger.info(f"📚 Backfill klar för {sym} {tf}: +{inserted} rader")
                except Exception as ie:
                    logger.warning(f"⚠️ Backfill misslyckades för {sym} {tf}: {ie}")
                # Liten paus mellan par även efter körning
                await asyncio.sleep(0.1)
        except Exception:
            return

    def get_stats(self) -> dict[str, Any]:
        """Returnera service-statistik"""
        live_symbols = self.get_live_symbols()

        return {
            **self.stats,
            "live_ws_symbols": len(live_symbols),
            "cached_tickers": len(self._ticker_cache),
            "cached_candles": sum(len(timeframes) for timeframes in self._candle_cache.values()),
            "queue_sizes": {symbol: len(queue) for symbol, queue in self._update_queues.items()},
            "rate_limiter_stats": self.rate_limiter.get_stats(),
        }

    def clear_stale_cache(self) -> None:
        """Rensa gammal cache-data"""
        now = time.time()

        # Rensa gamla tickers
        stale_tickers = [
            symbol
            for symbol, data_point in self._ticker_cache.items()
            if now - data_point.timestamp > self.ticker_stale_seconds * 2
        ]
        for symbol in stale_tickers:
            del self._ticker_cache[symbol]

        # Rensa gamla candles
        for symbol in list(self._candle_cache.keys()):
            timeframes = self._candle_cache[symbol]
            stale_timeframes = [
                tf
                for tf, data_point in timeframes.items()
                if now - data_point.timestamp > self.candle_stale_seconds * 2
            ]
            for tf in stale_timeframes:
                del self._candle_cache[symbol][tf]

            # Ta bort symbol helt om inga timeframes kvar
            if not self._candle_cache[symbol]:
                del self._candle_cache[symbol]

    async def close(self) -> None:
        """Stäng service och rensa resurser"""
        await self.rest_service.close()
        self._ticker_cache.clear()
        self._candle_cache.clear()
        self._update_queues.clear()


# Global instans
_ws_first_data_service: WSFirstDataService | None = None


def get_ws_first_data_service() -> WSFirstDataService:
    """Returnerar global WS-first data service instans"""
    global _ws_first_data_service
    if _ws_first_data_service is None:
        _ws_first_data_service = WSFirstDataService()
    return _ws_first_data_service
