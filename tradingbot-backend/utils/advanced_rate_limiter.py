"""
Advanced Rate Limiter - TradingBot Backend

Token-bucket baserad rate limiting med separata limits för olika endpoint-typer.
"""

import asyncio
import random
import time
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from config.settings import Settings
from utils.logger import get_logger

logger = get_logger(__name__)


class EndpointType(Enum):
    """Endpoint-typer med olika rate limits"""

    PUBLIC_MARKET = "public_market"  # Ticker, candles, orderbook
    PRIVATE_ACCOUNT = "private_account"  # Wallets, positions, user info
    PRIVATE_TRADING = "private_trading"  # Orders, trades
    PRIVATE_MARGIN = "private_margin"  # Margin info, funding


@dataclass
class TokenBucket:
    """Token bucket för rate limiting"""

    capacity: int  # Max antal tokens
    refill_rate: float  # Tokens per sekund
    tokens: float = 0  # Nuvarande tokens
    last_refill: float = 0  # Senaste påfyllning

    def __post_init__(self):
        self.tokens = self.capacity
        self.last_refill = time.time()

    def refill(self) -> None:
        """Fyll på tokens baserat på tid"""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """Försök konsumera tokens. Returnerar True om tillgängliga."""
        self.refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def time_to_tokens(self, tokens: int = 1) -> float:
        """Tid tills tillräckligt tokens finns tillgängliga"""
        self.refill()
        if self.tokens >= tokens:
            return 0.0
        needed = tokens - self.tokens
        return needed / self.refill_rate


class AdvancedRateLimiter:
    """Advanced rate limiter med token-bucket och endpoint-specifika limits"""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self._buckets: dict[EndpointType, TokenBucket] = {}
        self._endpoint_mapping: dict[str, EndpointType] = {}
        self._lock = asyncio.Lock()
        # Server busy tracking (för kompatibilitet med äldre anrop)
        self._server_busy_count: int = 0
        self._last_server_busy_time: float = 0.0
        self._adaptive_backoff_multiplier: float = 1.0
        # Circuit breaker per endpoint
        self._cb_state: dict[str, dict] = {}
        self._setup_buckets()
        self._setup_endpoint_mapping()

    def _setup_buckets(self) -> None:
        """Sätt upp token buckets för olika endpoint-typer"""
        # Bitfinex officiella limits (konservativt justerade)
        bucket_configs = {
            EndpointType.PUBLIC_MARKET: {
                "capacity": 30,  # Burst capacity
                "refill_rate": 0.5,  # 30 requests per minut
            },
            EndpointType.PRIVATE_ACCOUNT: {
                "capacity": 10,  # Mindre burst för auth
                "refill_rate": 0.15,  # 9 requests per minut
            },
            EndpointType.PRIVATE_TRADING: {
                "capacity": 5,  # Mycket konservativ för orders
                "refill_rate": 0.08,  # 5 requests per minut
            },
            EndpointType.PRIVATE_MARGIN: {
                "capacity": 8,
                "refill_rate": 0.12,  # 7 requests per minut
            },
        }

        for endpoint_type, config in bucket_configs.items():
            self._buckets[endpoint_type] = TokenBucket(
                capacity=int(config["capacity"]), refill_rate=config["refill_rate"]
            )

    def _setup_endpoint_mapping(self) -> None:
        """Mappa API endpoints till endpoint-typer"""
        self._endpoint_mapping = {
            # Public endpoints
            "ticker": EndpointType.PUBLIC_MARKET,
            "candles": EndpointType.PUBLIC_MARKET,
            "book": EndpointType.PUBLIC_MARKET,
            "trades": EndpointType.PUBLIC_MARKET,
            # Private account endpoints
            "auth/r/wallets": EndpointType.PRIVATE_ACCOUNT,
            "auth/r/positions": EndpointType.PRIVATE_ACCOUNT,
            "auth/r/info/user": EndpointType.PRIVATE_ACCOUNT,
            "auth/r/ledgers": EndpointType.PRIVATE_ACCOUNT,
            # Private trading endpoints
            "auth/w/order/submit": EndpointType.PRIVATE_TRADING,
            "auth/w/order/cancel": EndpointType.PRIVATE_TRADING,
            "auth/r/orders": EndpointType.PRIVATE_TRADING,
            "auth/r/trades": EndpointType.PRIVATE_TRADING,
            # Private margin endpoints
            "auth/r/info/margin": EndpointType.PRIVATE_MARGIN,
            "auth/r/funding": EndpointType.PRIVATE_MARGIN,
        }

    def _classify_endpoint(self, endpoint: str) -> EndpointType:
        """Klassificera endpoint till typ"""
        # Exact match först
        if endpoint in self._endpoint_mapping:
            return self._endpoint_mapping[endpoint]

        # Pattern matching
        if endpoint.startswith("auth/w/"):
            return EndpointType.PRIVATE_TRADING
        elif endpoint.startswith("auth/r/info/margin"):
            return EndpointType.PRIVATE_MARGIN
        elif endpoint.startswith("auth/r/"):
            return EndpointType.PRIVATE_ACCOUNT
        else:
            return EndpointType.PUBLIC_MARKET

    async def wait_if_needed(self, endpoint: str, tokens: int = 1) -> float:
        """
        Vänta om rate limit är nått.

        Args:
            endpoint: API endpoint
            tokens: Antal tokens att konsumera

        Returns:
            Tid som väntades (sekunder)
        """
        if not self.settings.BITFINEX_RATE_LIMIT_ENABLED:
            return 0.0

        endpoint_type = self._classify_endpoint(endpoint)
        bucket = self._buckets[endpoint_type]

        async with self._lock:
            if bucket.consume(tokens):
                # Tokens tillgängliga, ingen väntan
                return 0.0

            # Beräkna väntetid
            wait_time = bucket.time_to_tokens(tokens)

            if wait_time > 0:
                logger.warning(f"Rate limit nått för {endpoint_type.value} ({endpoint}), " f"väntar {wait_time:.1f}s")
                await asyncio.sleep(wait_time)

                # Konsumera tokens efter väntan
                bucket.consume(tokens)

            return wait_time

    def get_stats(self) -> dict[str, dict]:
        """Returnerar statistik för alla buckets"""
        stats = {}
        for endpoint_type, bucket in self._buckets.items():
            bucket.refill()  # Uppdatera tokens först
            stats[endpoint_type.value] = {
                "tokens_available": bucket.tokens,
                "capacity": bucket.capacity,
                "refill_rate_per_sec": bucket.refill_rate,
                "utilization_percent": (1 - bucket.tokens / bucket.capacity) * 100,
            }
        return stats

    def force_refill(self) -> None:
        """Tvinga påfyllning av alla buckets (för testing)"""
        for bucket in self._buckets.values():
            bucket.tokens = bucket.capacity
            bucket.last_refill = time.time()

    async def handle_server_busy(self, endpoint: str = "default") -> float:  # noqa: ARG002
        """Kompatibilitets-API: hantera server busy med adaptiv backoff."""
        now = time.time()
        self._server_busy_count += 1
        # Anpassa multiplier beroende på hur tätt felen kommer
        if now - self._last_server_busy_time < 60:
            self._adaptive_backoff_multiplier = min(4.0, self._adaptive_backoff_multiplier * 1.5)
        else:
            self._adaptive_backoff_multiplier = max(1.0, self._adaptive_backoff_multiplier * 0.8)
        self._last_server_busy_time = now

        base_min = float(getattr(self.settings, "BITFINEX_SERVER_BUSY_BACKOFF_MIN_SECONDS", 10.0) or 10.0)
        base_max = float(getattr(self.settings, "BITFINEX_SERVER_BUSY_BACKOFF_MAX_SECONDS", 30.0) or 30.0)
        wait_time = random.uniform(
            base_min * self._adaptive_backoff_multiplier,
            base_max * self._adaptive_backoff_multiplier,
        )
        await asyncio.sleep(wait_time)
        return wait_time

    def reset_server_busy_count(self) -> None:
        """Kompatibilitets-API: återställ server-busy räknare."""
        self._server_busy_count = 0
        self._adaptive_backoff_multiplier = 1.0

    # --- Circuit breaker helpers ---
    def _cb_key(self, endpoint: str) -> str:
        return str(endpoint or "default")

    def time_until_open(self, endpoint: str) -> float:
        st = self._cb_state.get(self._cb_key(endpoint)) or {}
        open_until = float(st.get("open_until", 0.0) or 0.0)
        now = time.time()
        return max(0.0, open_until - now)

    def can_request(self, endpoint: str) -> bool:
        return self.time_until_open(endpoint) <= 0.0

    def note_success(self, endpoint: str) -> None:
        key = self._cb_key(endpoint)
        st = self._cb_state.get(key)
        if st:
            st["fail_count"] = 0
            st["open_until"] = 0.0
            st["last_failure"] = 0.0
            self._cb_state[key] = st

    def note_failure(self, endpoint: str, status_code: int, retry_after: str | None = None) -> float:  # noqa: ARG002
        key = self._cb_key(endpoint)
        st = self._cb_state.get(key) or {"fail_count": 0, "open_until": 0.0, "last_failure": 0.0}
        st["fail_count"] = int(st.get("fail_count", 0)) + 1
        st["last_failure"] = time.time()
        # Cooldown baserat på Retry-After eller exponentiell backoff
        ra_sec = 0.0
        try:
            if retry_after:
                ra_sec = float(retry_after)
        except Exception:
            ra_sec = 0.0
        base = 2 ** min(6, st["fail_count"])  # 2,4,8,16,32,64 max
        cooldown = max(ra_sec, float(base))
        st["open_until"] = time.time() + cooldown
        self._cb_state[key] = st
        return cooldown


# Global instans
_advanced_rate_limiter: AdvancedRateLimiter | None = None


def get_advanced_rate_limiter() -> AdvancedRateLimiter:
    """Returnerar global advanced rate limiter instans"""
    global _advanced_rate_limiter
    if _advanced_rate_limiter is None:
        _advanced_rate_limiter = AdvancedRateLimiter()
    return _advanced_rate_limiter
