"""
Advanced Rate Limiter - TradingBot Backend

Token-bucket baserad rate limiting med separata limits för olika endpoint-typer.
"""

import asyncio
import contextlib
import random
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, ParamSpec, TypeVar

from config.settings import settings
from services.metrics import _labels_to_str, metrics_store
from services.metrics_client import get_metrics_client
from utils.logger import get_logger
from services.unified_circuit_breaker_service import unified_circuit_breaker_service

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
    """
    Advanced rate limiter med token-bucket, concurrency‑semaforer och enkel
    transport‑nivå circuit breaker per endpoint.

    _cb_state struktur per endpoint‑nyckel (str):
      {
        "fail_count": int,      # antal på varandra följande fel (ökar i note_failure, nollas i note_success)
        "open_until": float,    # epoch‑sek tills breaker är öppen (can_request==False om now < open_until)
        "last_failure": float,  # epoch‑sek för senaste felet (observationsvärde)
      }

    Semantik:
      - can_request(endpoint): True om nuvarande tid >= open_until
      - time_until_open(endpoint): sekunder kvar tills closed/half‑open
      - note_failure(endpoint, status_code, retry_after):
          * ökar fail_count och sätter open_until enligt Retry‑After om finns,
            annars exponentiell backoff (2^min(6, fail_count)).
          * signalerar även UnifiedCircuitBreakerService (transport‑källa)
      - note_success(endpoint): nollar fail_count/open_until/last_failure och
            signalerar UnifiedCircuitBreakerService om återhämtning.

    Användning: Exponeras via get_advanced_rate_limiter().
    För felsökning: se `/api/v2/debug/rate_limiter` som visar nyckelvärden samt
    `time_until_open` för utvalda endpoints.
    """

    def __init__(self, settings_override: Settings | None = None):
        self.settings = settings_override or settings
        self._buckets: dict[EndpointType, TokenBucket] = {}
        self._endpoint_mapping: dict[str, EndpointType] = {}
        # Per-event-loop locks: asyncio.Lock är loop-bundet
        self._locks_by_loop: dict[int, asyncio.Lock] = {}
        # Concurrency caps per endpoint-typ
        # OBS: asyncio.Semaphore är loop-bundet. Håll per-loop map.
        self._semaphores: dict[int, dict[EndpointType, asyncio.Semaphore]] = {}
        # Server busy tracking (för kompatibilitet med äldre anrop)
        self._server_busy_count: int = 0
        self._last_server_busy_time: float = 0.0
        self._adaptive_backoff_multiplier: float = 1.0
        # Circuit breaker per endpoint
        self._cb_state: dict[str, dict] = {}
        self._setup_buckets()
        self._setup_endpoint_mapping()

    def _get_lock(self) -> asyncio.Lock:
        """Hämta ett asyncio.Lock bundet till aktuell event loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None  # type: ignore[assignment]
        loop_id = id(loop)
        lock = self._locks_by_loop.get(loop_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks_by_loop[loop_id] = lock
        return lock

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

    def _setup_semaphores(self) -> None:
        """Init default-konfig; faktiska semaforer skapas per event loop vid behov."""
        # Inget att göra här längre; behåll metoden för bakåtkompatibilitet
        pass

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

        # Valfri mönsterbaserad mapping via settings (format: "regex=>TYPE;regex=>TYPE")
        patterns = getattr(self.settings, "RATE_LIMIT_PATTERNS", None)
        self._pattern_map: list[tuple[re.Pattern[str], EndpointType]] = []
        if patterns:
            for mapping_part in str(patterns).split(";"):
                mapping_part_stripped = mapping_part.strip()
                if not mapping_part_stripped or "=>" not in mapping_part_stripped:
                    continue
                rx, typ = (x.strip() for x in mapping_part_stripped.split("=>", 1))
                try:
                    et = EndpointType[typ]
                except Exception:
                    # tillåt även värden (PUBLIC_MARKET...) direkt
                    try:
                        et = EndpointType(typ.lower())  # type: ignore[arg-type]
                    except Exception:
                        continue
                try:
                    self._pattern_map.append((re.compile(rx), et))
                except re.error:
                    continue

    def _classify_endpoint(self, endpoint: str) -> EndpointType:
        """Klassificera endpoint till typ"""
        # Exact match först
        if endpoint in self._endpoint_mapping:
            return self._endpoint_mapping[endpoint]

        # Pattern matching
        for rx, et in getattr(self, "_pattern_map", []) or []:
            try:
                if rx.search(endpoint):
                    return et
            except Exception:
                continue
        if endpoint.startswith("auth/w/"):
            return EndpointType.PRIVATE_TRADING
        elif endpoint.startswith("auth/r/info/margin"):
            return EndpointType.PRIVATE_MARGIN
        elif endpoint.startswith("auth/r/"):
            return EndpointType.PRIVATE_ACCOUNT
        else:
            return EndpointType.PUBLIC_MARKET

    def _get_bucket(self, endpoint: str) -> TokenBucket:
        et = self._classify_endpoint(endpoint)
        return self._buckets[et]

    def _get_semaphore(self, endpoint: str) -> asyncio.Semaphore:
        et = self._classify_endpoint(endpoint)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None  # type: ignore
        loop_id = id(loop)
        semaphores = self._semaphores.get(loop_id)
        if semaphores is None:
            pub = max(1, int(getattr(self.settings, "PUBLIC_REST_CONCURRENCY", 2) or 1))
            prv = max(1, int(getattr(self.settings, "PRIVATE_REST_CONCURRENCY", 1) or 1))
            semaphores = {
                EndpointType.PUBLIC_MARKET: asyncio.Semaphore(pub),
                EndpointType.PRIVATE_ACCOUNT: asyncio.Semaphore(prv),
                EndpointType.PRIVATE_TRADING: asyncio.Semaphore(prv),
                EndpointType.PRIVATE_MARGIN: asyncio.Semaphore(prv),
            }
            self._semaphores[loop_id] = semaphores
        return semaphores[et]

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

        async with self._get_lock():
            if bucket.consume(tokens):
                # Tokens tillgängliga, ingen väntan
                return 0.0

            # Beräkna väntetid
            wait_time = bucket.time_to_tokens(tokens)

            if wait_time > 0:
                logger.warning(f"Rate limit nått för {endpoint_type.value} ({endpoint}), väntar {wait_time:.1f}s")
                await asyncio.sleep(wait_time)

                # Konsumera tokens efter väntan
                bucket.consume(tokens)

            return wait_time

    def has_capacity(self, endpoint: str, tokens: int = 1) -> bool:
        """True om token-bucket just nu har utrymme utan väntan."""
        bucket = self._get_bucket(endpoint)
        bucket.refill()
        return bucket.tokens >= tokens

    @contextlib.asynccontextmanager
    async def limit(self, endpoint: str):
        """Concurrency-guard som begränsar samtidiga REST-anrop per endpoint-typ."""
        sem = self._get_semaphore(endpoint)
        await sem.acquire()
        try:
            yield
        finally:
            sem.release()

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

    def export_metrics(self) -> None:
        """Skicka limiter-stats till metrics_store för Prometheus-export."""
        stats = self.get_stats()
        counters: dict[str, dict[str, float]] = metrics_store.get("counters", {}) or {}
        tokens_map = counters.setdefault("limiter_bucket_tokens", {})
        util_map = counters.setdefault("limiter_bucket_utilization_percent", {})
        for et, s in stats.items():
            labels = _labels_to_str({"endpoint_type": str(et)})
            tokens_map[labels] = float(s.get("tokens_available", 0.0))
            util_map[labels] = float(s.get("utilization_percent", 0.0))
        counters["limiter_bucket_tokens"] = tokens_map
        counters["limiter_bucket_utilization_percent"] = util_map
        metrics_store["counters"] = counters

    def force_refill(self) -> None:
        """Tvinga påfyllning av alla buckets (för testing)"""
        for bucket in self._buckets.values():
            bucket.tokens = bucket.capacity
            bucket.last_refill = time.time()

    async def handle_server_busy(self, _endpoint: str = "default") -> float:
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
        """Sekunder kvar tills circuit för endpoint är closed.

        Returnerar 0 när closed (eller ej öppnad). Bygger på `open_until` i
        `_cb_state` (epoch‑sek)."""
        st = self._cb_state.get(self._cb_key(endpoint)) or {}
        open_until = float(st.get("open_until", 0.0) or 0.0)
        now = time.time()
        return max(0.0, open_until - now)

    def can_request(self, endpoint: str) -> bool:
        """True om endpoint‑circuit är closed (dvs `time_until_open` är 0)."""
        return self.time_until_open(endpoint) <= 0.0

    def note_success(self, endpoint: str) -> None:
        """Notera framgång och återställ transport‑CB för endpoint.

        Nollställer fail_count/open_until/last_failure och signalerar Unified
        CB om återhämtning. Idempotent om state saknas."""
        key = self._cb_key(endpoint)
        st = self._cb_state.get(key)
        if st:
            st["fail_count"] = 0
            st["open_until"] = 0.0
            st["last_failure"] = 0.0
            self._cb_state[key] = st
        # Signalera unified CB
        try:
            unified_circuit_breaker_service.on_event(source="transport", endpoint=endpoint, success=True)
        except Exception:
            pass

    def note_failure(self, endpoint: str, status_code: int, retry_after: str | None = None) -> float:
        """Notera fel och öppna transport‑CB för endpoint enligt backoff.

        - Om `retry_after` kan tolkas som sekunder används det som minsta
          cooldown. Annars används exponentiell backoff 2^min(6, fail_count).
        - Uppdaterar `_cb_state` och returnerar aktuell cooldown i sekunder.
        - Signal skickas till UnifiedCircuitBreakerService (source="transport")."""
        key = self._cb_key(endpoint)
        st = self._cb_state.get(key) or {
            "fail_count": 0,
            "open_until": 0.0,
            "last_failure": 0.0,
        }
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

        # Namngiven loggning för transport/circuit breaker (REST-transportnivå)
        try:
            logger.warning(
                "🚦 TransportCircuitBreaker: %s status=%s cooldown=%.1fs",
                endpoint,
                status_code,
                cooldown,
            )
        except Exception:
            pass
        # Signalera unified CB
        try:
            unified_circuit_breaker_service.on_event(
                source="transport",
                endpoint=endpoint,
                status_code=status_code,
                success=False,
                retry_after=retry_after,
            )
        except Exception:
            pass
        return cooldown


# Global instans
_advanced_rate_limiter: AdvancedRateLimiter | None = None


def get_advanced_rate_limiter() -> AdvancedRateLimiter:
    """Returnerar global advanced rate limiter instans"""
    global _advanced_rate_limiter
    if _advanced_rate_limiter is None:
        _advanced_rate_limiter = AdvancedRateLimiter(settings)
    return _advanced_rate_limiter


P = ParamSpec("P")
R = TypeVar("R")


# Hjälp-dekoratorer/context managers för enkel användning
def limit_endpoint(
    endpoint: str,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Async-dekorator som begränsar concurrency och respekterar token bucket för endpoint."""

    def _decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            limiter = get_advanced_rate_limiter()
            # Vänta om rate limit kräver
            await limiter.wait_if_needed(endpoint)
            async with limiter.limit(endpoint):
                return await func(*args, **kwargs)

        return _wrapper

    return _decorator


# (duplikat borttaget; se tidigare global instans och funktion ovan)
