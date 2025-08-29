"""
Bitfinex API Rate Limiter - TradingBot Backend

Intelligent rate limiting för Bitfinex API med server busy detection
och adaptiv backoff-strategi.
"""

import asyncio
import random
import time
from collections import deque

from config.settings import Settings
from utils.logger import get_logger

logger = get_logger(__name__)


class BitfinexRateLimiter:
    """Intelligent rate limiter för Bitfinex API med server busy handling."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self._request_timestamps: deque = deque()
        self._server_busy_count = 0
        self._last_server_busy_time = 0
        self._adaptive_backoff_multiplier = 1.0
        self._lock = asyncio.Lock()

    async def wait_if_needed(self, endpoint: str = "default") -> None:
        """
        Väntar om rate limit är nått.

        Args:
            endpoint: API endpoint för specifik rate limiting
        """
        if not self.settings.BITFINEX_RATE_LIMIT_ENABLED:
            return

        async with self._lock:
            now = time.time()
            window_start = now - self.settings.BITFINEX_RATE_LIMIT_WINDOW_SECONDS

            # Rensa gamla timestamps
            while self._request_timestamps and self._request_timestamps[0] < window_start:
                self._request_timestamps.popleft()

            # Kontrollera rate limit
            max_requests = self.settings.BITFINEX_RATE_LIMIT_REQUESTS_PER_MINUTE
            if len(self._request_timestamps) >= max_requests:
                # Beräkna väntetid
                oldest_request = self._request_timestamps[0]
                wait_time = window_start - oldest_request + 1.0

                if wait_time > 0:
                    logger.warning(f"Rate limit nått för {endpoint}, väntar {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)

            # Lägg till nuvarande request
            self._request_timestamps.append(now)

    async def handle_server_busy(self, endpoint: str = "default") -> float:
        """
        Hanterar server busy fel med intelligent backoff.

        Args:
            endpoint: API endpoint som orsakade server busy

        Returns:
            Väntetid i sekunder
        """
        async with self._lock:
            now = time.time()
            self._server_busy_count += 1

            # Öka backoff om vi får flera server busy i rad
            if now - self._last_server_busy_time < 60:  # Inom 1 minut
                self._adaptive_backoff_multiplier = min(4.0, self._adaptive_backoff_multiplier * 1.5)
            else:
                # Återställ om det varit länge sedan
                self._adaptive_backoff_multiplier = max(1.0, self._adaptive_backoff_multiplier * 0.8)

            self._last_server_busy_time = int(now)

            # Beräkna väntetid med exponential backoff
            base_min = self.settings.BITFINEX_SERVER_BUSY_BACKOFF_MIN_SECONDS
            base_max = self.settings.BITFINEX_SERVER_BUSY_BACKOFF_MAX_SECONDS

            wait_time = random.uniform(
                base_min * self._adaptive_backoff_multiplier,
                base_max * self._adaptive_backoff_multiplier,
            )

            logger.warning(
                f"Server busy för {endpoint} (nr {self._server_busy_count}), "
                f"väntar {wait_time:.1f}s (backoff: {self._adaptive_backoff_multiplier:.1f}x)"
            )

            await asyncio.sleep(wait_time)
            return wait_time

    def reset_server_busy_count(self) -> None:
        """Återställer server busy räknare vid framgångsrika requests."""
        self._server_busy_count = 0
        self._adaptive_backoff_multiplier = 1.0

    def get_stats(self) -> dict:
        """Returnerar rate limiter statistik."""
        return {
            "requests_in_window": len(self._request_timestamps),
            "max_requests_per_minute": self.settings.BITFINEX_RATE_LIMIT_REQUESTS_PER_MINUTE,
            "server_busy_count": self._server_busy_count,
            "adaptive_backoff_multiplier": self._adaptive_backoff_multiplier,
            "last_server_busy_time": self._last_server_busy_time,
        }


# Global instans
_bitfinex_rate_limiter: BitfinexRateLimiter | None = None


def get_bitfinex_rate_limiter() -> BitfinexRateLimiter:
    """Returnerar global Bitfinex rate limiter instans."""
    global _bitfinex_rate_limiter
    if _bitfinex_rate_limiter is None:
        _bitfinex_rate_limiter = BitfinexRateLimiter()
    return _bitfinex_rate_limiter
