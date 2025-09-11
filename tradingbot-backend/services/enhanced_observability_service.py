"""
Enhanced Observability Service - Utökad observability för TradingBot.

Konsoliderar:
- Performance metrics (CPU, RAM, Disk)
- Rate limiter metrics (tokens, utilization)
- Exchange metrics (API calls, errors, latency)
- Circuit breaker status
- WebSocket metrics
- Trading metrics

Löser problem med:
- Spridda metrics över olika services
- Inkonsistenta observability-data
- Svår att debugga prestanda-problem
- Olika refresh-intervall för metrics
"""

from __future__ import annotations

import asyncio
import psutil
from datetime import datetime, timedelta
from typing import Any

from config.settings import Settings
from services.metrics import metrics_store
from utils.advanced_rate_limiter import get_advanced_rate_limiter
from utils.logger import get_logger

logger = get_logger(__name__)


class SystemMetrics:
    """System-resurser (CPU, RAM, Disk)."""

    def __init__(self):
        self.timestamp = datetime.now()
        self.cpu_percent = 0.0
        self.memory_percent = 0.0
        self.memory_used_gb = 0.0
        self.memory_total_gb = 0.0
        self.disk_percent = 0.0
        self.disk_used_gb = 0.0
        self.disk_total_gb = 0.0
        self.load_average = [0.0, 0.0, 0.0]


class RateLimiterMetrics:
    """Rate limiter metrics."""

    def __init__(self):
        self.timestamp = datetime.now()
        self.tokens_available = {}
        self.utilization_percent = {}
        self.requests_per_second = {}
        self.blocked_requests = {}
        self.endpoint_patterns = {}


class ExchangeMetrics:
    """Exchange API metrics."""

    def __init__(self):
        self.timestamp = datetime.now()
        self.total_requests = 0
        self.failed_requests = 0
        self.rate_limited_requests = 0
        self.average_latency_ms = 0.0
        self.p95_latency_ms = 0.0
        self.p99_latency_ms = 0.0
        self.requests_per_minute = 0.0
        self.error_rate_percent = 0.0


class CircuitBreakerMetrics:
    """Circuit breaker metrics."""

    def __init__(self):
        self.timestamp = datetime.now()
        self.trading_circuit_breaker_open = False
        self.transport_circuit_breaker_open = False
        self.trading_errors_count = 0
        self.transport_errors_count = 0
        self.last_trading_error = None
        self.last_transport_error = None


class WebSocketMetrics:
    """WebSocket metrics."""

    def __init__(self):
        self.timestamp = datetime.now()
        self.connected_sockets = 0
        self.max_sockets = 0
        self.active_subscriptions = 0
        self.max_subscriptions = 0
        self.messages_per_second = 0.0
        self.reconnect_count = 0
        self.last_reconnect = None


class TradingMetrics:
    """Trading metrics."""

    def __init__(self):
        self.timestamp = datetime.now()
        self.total_orders = 0
        self.successful_orders = 0
        self.failed_orders = 0
        self.order_success_rate = 0.0
        self.average_order_latency_ms = 0.0
        self.orders_per_minute = 0.0
        self.total_volume_usd = 0.0
        self.total_fees_usd = 0.0


class EnhancedObservabilityService:
    """
    Enhetlig service för all observability i systemet.

    Konsoliderar metrics från:
    - System resources (CPU, RAM, Disk)
    - Rate limiters
    - Exchange APIs
    - Circuit breakers
    - WebSocket connections
    - Trading operations
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.rate_limiter = get_advanced_rate_limiter()

        # Cache för metrics
        self._metrics_cache: dict[str, Any] = {}
        self._cache_ttl = timedelta(seconds=30)  # Kort cache för realtidsdata
        self._last_update: datetime | None = None

        logger.info("📊 EnhancedObservabilityService initialiserad - enhetlig observability")

    async def get_system_metrics(self) -> SystemMetrics:
        """Hämta system-resurser."""
        try:
            metrics = SystemMetrics()

            # CPU usage (non-blocking)
            metrics.cpu_percent = psutil.cpu_percent(interval=None)

            # Memory usage
            memory = psutil.virtual_memory()
            metrics.memory_percent = memory.percent
            metrics.memory_used_gb = memory.used / (1024**3)
            metrics.memory_total_gb = memory.total / (1024**3)

            # Disk usage
            disk = psutil.disk_usage("/")
            metrics.disk_percent = (disk.used / disk.total) * 100
            metrics.disk_used_gb = disk.used / (1024**3)
            metrics.disk_total_gb = disk.total / (1024**3)

            # Load average (Unix only)
            try:
                metrics.load_average = list(psutil.getloadavg())
            except AttributeError:
                metrics.load_average = [0.0, 0.0, 0.0]  # Windows fallback

            logger.debug(f"📊 System metrics: CPU {metrics.cpu_percent}%, RAM {metrics.memory_percent}%")
            return metrics

        except Exception as e:
            logger.error(f"❌ Fel vid hämtning av system metrics: {e}")
            return SystemMetrics()

    async def get_rate_limiter_metrics(self) -> RateLimiterMetrics:
        """Hämta rate limiter metrics."""
        try:
            metrics = RateLimiterMetrics()

            # Hämta rate limiter status
            if hasattr(self.rate_limiter, "get_status"):
                status = self.rate_limiter.get_status()
                metrics.tokens_available = status.get("tokens_available", {})
                metrics.utilization_percent = status.get("utilization_percent", {})
                metrics.requests_per_second = status.get("requests_per_second", {})
                metrics.blocked_requests = status.get("blocked_requests", {})
                metrics.endpoint_patterns = status.get("endpoint_patterns", {})

            logger.debug(f"📊 Rate limiter metrics: {len(metrics.tokens_available)} patterns")
            return metrics

        except Exception as e:
            logger.error(f"❌ Fel vid hämtning av rate limiter metrics: {e}")
            return RateLimiterMetrics()

    async def get_exchange_metrics(self) -> ExchangeMetrics:
        """Hämta exchange API metrics."""
        try:
            metrics = ExchangeMetrics()

            # Hämta från metrics store
            metrics.total_requests = metrics_store.get("orders_total", 0)
            metrics.failed_requests = metrics_store.get("orders_failed_total", 0)
            metrics.rate_limited_requests = metrics_store.get("rate_limited_total", 0)

            # Beräkna latens-metrics från request_latency_samples
            latency_samples = metrics_store.get("request_latency_samples", {})
            all_latencies = []
            for samples in latency_samples.values():
                all_latencies.extend(samples)

            if all_latencies:
                all_latencies.sort()
                metrics.average_latency_ms = sum(all_latencies) / len(all_latencies)
                metrics.p95_latency_ms = all_latencies[int(len(all_latencies) * 0.95)]
                metrics.p99_latency_ms = all_latencies[int(len(all_latencies) * 0.99)]

            # Beräkna error rate
            if metrics.total_requests > 0:
                metrics.error_rate_percent = (metrics.failed_requests / metrics.total_requests) * 100

            logger.debug(
                f"📊 Exchange metrics: {metrics.total_requests} requests, {metrics.error_rate_percent:.1f}% error rate"
            )
            return metrics

        except Exception as e:
            logger.error(f"❌ Fel vid hämtning av exchange metrics: {e}")
            return ExchangeMetrics()

    async def get_circuit_breaker_metrics(self) -> CircuitBreakerMetrics:
        """Hämta circuit breaker metrics."""
        try:
            metrics = CircuitBreakerMetrics()

            # Hämta från metrics store eller direkt från services
            # Detta är en förenklad implementation - i verkligheten skulle vi
            # hämta från de faktiska circuit breaker services

            # Simulera circuit breaker status
            metrics.trading_circuit_breaker_open = False
            metrics.transport_circuit_breaker_open = False
            metrics.trading_errors_count = 0
            metrics.transport_errors_count = 0

            logger.debug("📊 Circuit breaker metrics: Alla stängda")
            return metrics

        except Exception as e:
            logger.error(f"❌ Fel vid hämtning av circuit breaker metrics: {e}")
            return CircuitBreakerMetrics()

    async def get_websocket_metrics(self) -> WebSocketMetrics:
        """Hämta WebSocket metrics."""
        try:
            metrics = WebSocketMetrics()

            # Hämta från metrics store
            ws_pool = metrics_store.get("ws_pool", {})
            metrics.connected_sockets = len(ws_pool.get("sockets", []))
            metrics.max_sockets = ws_pool.get("max_sockets", 0)
            metrics.active_subscriptions = sum(s.get("subs", 0) for s in ws_pool.get("sockets", []))
            metrics.max_subscriptions = ws_pool.get("max_subs", 0)

            logger.debug(
                f"📊 WebSocket metrics: {metrics.connected_sockets} sockets, {metrics.active_subscriptions} subs"
            )
            return metrics

        except Exception as e:
            logger.error(f"❌ Fel vid hämtning av WebSocket metrics: {e}")
            return WebSocketMetrics()

    async def get_trading_metrics(self) -> TradingMetrics:
        """Hämta trading metrics."""
        try:
            metrics = TradingMetrics()

            # Hämta från metrics store
            metrics.total_orders = metrics_store.get("orders_total", 0)
            metrics.successful_orders = metrics.total_orders - metrics_store.get("orders_failed_total", 0)
            metrics.failed_orders = metrics_store.get("orders_failed_total", 0)

            # Beräkna success rate
            if metrics.total_orders > 0:
                metrics.order_success_rate = (metrics.successful_orders / metrics.total_orders) * 100

            # Beräkna genomsnittlig latens
            order_submit_ms = metrics_store.get("order_submit_ms", 0)
            if metrics.total_orders > 0:
                metrics.average_order_latency_ms = order_submit_ms / metrics.total_orders

            logger.debug(
                f"📊 Trading metrics: {metrics.total_orders} orders, {metrics.order_success_rate:.1f}% success rate"
            )
            return metrics

        except Exception as e:
            logger.error(f"❌ Fel vid hämtning av trading metrics: {e}")
            return TradingMetrics()

    async def get_comprehensive_metrics(self) -> dict[str, Any]:
        """Hämta alla metrics i en enhetlig struktur."""
        try:
            # Kontrollera cache
            if (
                self._last_update
                and datetime.now() - self._last_update < self._cache_ttl
                and "comprehensive_metrics" in self._metrics_cache
            ):
                logger.debug("📋 Använder cached comprehensive metrics")
                return self._metrics_cache["comprehensive_metrics"]

            # Hämta alla metrics parallellt
            system_task = asyncio.create_task(self.get_system_metrics())
            rate_limiter_task = asyncio.create_task(self.get_rate_limiter_metrics())
            exchange_task = asyncio.create_task(self.get_exchange_metrics())
            circuit_breaker_task = asyncio.create_task(self.get_circuit_breaker_metrics())
            websocket_task = asyncio.create_task(self.get_websocket_metrics())
            trading_task = asyncio.create_task(self.get_trading_metrics())

            # Vänta på alla tasks
            results = await asyncio.gather(
                system_task,
                rate_limiter_task,
                exchange_task,
                circuit_breaker_task,
                websocket_task,
                trading_task,
                return_exceptions=True,
            )

            # Hantera exceptions
            system_metrics = results[0] if not isinstance(results[0], Exception) else SystemMetrics()
            rate_limiter_metrics = results[1] if not isinstance(results[1], Exception) else RateLimiterMetrics()
            exchange_metrics = results[2] if not isinstance(results[2], Exception) else ExchangeMetrics()
            circuit_breaker_metrics = results[3] if not isinstance(results[3], Exception) else CircuitBreakerMetrics()
            websocket_metrics = results[4] if not isinstance(results[4], Exception) else WebSocketMetrics()
            trading_metrics = results[5] if not isinstance(results[5], Exception) else TradingMetrics()

            # Skapa comprehensive metrics
            comprehensive_metrics = {
                "timestamp": datetime.now().isoformat(),
                "system": {
                    "cpu_percent": system_metrics.cpu_percent,
                    "memory_percent": system_metrics.memory_percent,
                    "memory_used_gb": system_metrics.memory_used_gb,
                    "memory_total_gb": system_metrics.memory_total_gb,
                    "disk_percent": system_metrics.disk_percent,
                    "disk_used_gb": system_metrics.disk_used_gb,
                    "disk_total_gb": system_metrics.disk_total_gb,
                    "load_average": system_metrics.load_average,
                },
                "rate_limiter": {
                    "tokens_available": rate_limiter_metrics.tokens_available,
                    "utilization_percent": rate_limiter_metrics.utilization_percent,
                    "requests_per_second": rate_limiter_metrics.requests_per_second,
                    "blocked_requests": rate_limiter_metrics.blocked_requests,
                    "endpoint_patterns": rate_limiter_metrics.endpoint_patterns,
                },
                "exchange": {
                    "total_requests": exchange_metrics.total_requests,
                    "failed_requests": exchange_metrics.failed_requests,
                    "rate_limited_requests": exchange_metrics.rate_limited_requests,
                    "average_latency_ms": exchange_metrics.average_latency_ms,
                    "p95_latency_ms": exchange_metrics.p95_latency_ms,
                    "p99_latency_ms": exchange_metrics.p99_latency_ms,
                    "error_rate_percent": exchange_metrics.error_rate_percent,
                },
                "circuit_breaker": {
                    "trading_open": circuit_breaker_metrics.trading_circuit_breaker_open,
                    "transport_open": circuit_breaker_metrics.transport_circuit_breaker_open,
                    "trading_errors_count": circuit_breaker_metrics.trading_errors_count,
                    "transport_errors_count": circuit_breaker_metrics.transport_errors_count,
                },
                "websocket": {
                    "connected_sockets": websocket_metrics.connected_sockets,
                    "max_sockets": websocket_metrics.max_sockets,
                    "active_subscriptions": websocket_metrics.active_subscriptions,
                    "max_subscriptions": websocket_metrics.max_subscriptions,
                    "messages_per_second": websocket_metrics.messages_per_second,
                    "reconnect_count": websocket_metrics.reconnect_count,
                },
                "trading": {
                    "total_orders": trading_metrics.total_orders,
                    "successful_orders": trading_metrics.successful_orders,
                    "failed_orders": trading_metrics.failed_orders,
                    "order_success_rate": trading_metrics.order_success_rate,
                    "average_order_latency_ms": trading_metrics.average_order_latency_ms,
                    "orders_per_minute": trading_metrics.orders_per_minute,
                },
                "summary": {
                    "overall_health": self._calculate_overall_health(
                        system_metrics,
                        exchange_metrics,
                        circuit_breaker_metrics,
                        trading_metrics,
                    ),
                    "critical_alerts": self._get_critical_alerts(
                        system_metrics, exchange_metrics, circuit_breaker_metrics
                    ),
                },
            }

            # Spara i cache
            self._metrics_cache["comprehensive_metrics"] = comprehensive_metrics
            self._last_update = datetime.now()

            logger.info("📊 Comprehensive metrics genererade")
            return comprehensive_metrics

        except Exception as e:
            logger.error(f"❌ Fel vid hämtning av comprehensive metrics: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "overall_health": "error",
            }

    def _calculate_overall_health(
        self,
        system: SystemMetrics,
        exchange: ExchangeMetrics,
        circuit_breaker: CircuitBreakerMetrics,
        trading: TradingMetrics,
    ) -> str:
        """Beräkna övergripande hälsostatus."""
        try:
            # Kontrollera kritiska faktorer
            if circuit_breaker.trading_circuit_breaker_open or circuit_breaker.transport_circuit_breaker_open:
                return "critical"

            if system.cpu_percent > 90 or system.memory_percent > 90:
                return "warning"

            if exchange.error_rate_percent > 10:
                return "warning"

            if trading.order_success_rate < 80 and trading.total_orders > 10:
                return "warning"

            return "healthy"

        except Exception:
            return "unknown"

    def _get_critical_alerts(
        self,
        system: SystemMetrics,
        exchange: ExchangeMetrics,
        circuit_breaker: CircuitBreakerMetrics,
    ) -> list[str]:
        """Hämta kritiska alerts."""
        alerts = []

        try:
            if circuit_breaker.trading_circuit_breaker_open:
                alerts.append("Trading circuit breaker är öppen")

            if circuit_breaker.transport_circuit_breaker_open:
                alerts.append("Transport circuit breaker är öppen")

            if system.cpu_percent > 95:
                alerts.append(f"CPU usage kritisk: {system.cpu_percent:.1f}%")

            if system.memory_percent > 95:
                alerts.append(f"Memory usage kritisk: {system.memory_percent:.1f}%")

            if exchange.error_rate_percent > 20:
                alerts.append(f"Exchange error rate kritisk: {exchange.error_rate_percent:.1f}%")

        except Exception as e:
            alerts.append(f"Fel vid kontroll av alerts: {e}")

        return alerts

    def clear_cache(self) -> None:
        """Rensa metrics cache."""
        self._metrics_cache.clear()
        self._last_update = None
        logger.info("🗑️ Observability cache rensad")


# Global instans för enhetlig åtkomst
enhanced_observability_service = EnhancedObservabilityService()
