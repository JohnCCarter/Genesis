"""
Config Observability v2 med metrics, events och effective config monitoring

Ger fullständig observability för konfigurationssystemet med real-time metrics,
events och effektiv konfigurationsövervakning.
"""

import time
import threading
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum

from services.unified_config_manager import UnifiedConfigManager, ConfigContext
from services.config_validator import ValidationResult, ValidationSeverity
from config.priority_profiles import PriorityProfile


class EventType(Enum):
    """Typer av konfigurationshändelser."""

    CONFIG_SET = "config_set"
    CONFIG_GET = "config_get"
    CONFIG_VALIDATE = "config_validate"
    CONFIG_ERROR = "config_error"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    CACHE_INVALIDATE = "cache_invalidate"
    STORE_UPDATE = "store_update"
    VALIDATION_FAILURE = "validation_failure"
    PERMISSION_DENIED = "permission_denied"
    API_REQUEST = "api_request"
    BATCH_OPERATION = "batch_operation"


class MetricType(Enum):
    """Typer av metrics."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class ConfigEvent:
    """En konfigurationshändelse."""

    event_type: EventType
    timestamp: float
    key: str
    user: str | None = None
    source: str | None = None
    value: Any = None
    old_value: Any = None
    duration_ms: float | None = None
    success: bool = True
    error_message: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfigMetric:
    """En konfigurationsmetric."""

    name: str
    metric_type: MetricType
    value: float
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class EffectiveConfigSnapshot:
    """En snapshot av effektiv konfiguration."""

    timestamp: float
    context: ConfigContext
    configuration: Dict[str, Any]
    generation: int
    source_summary: Dict[str, int] = field(default_factory=dict)


class ConfigObservability:
    """
    Observability-system för konfigurationshantering.

    Samlar metrics, events och effective config snapshots för fullständig
    övervakning av konfigurationssystemet.
    """

    def __init__(self, config_manager: UnifiedConfigManager):
        """Initiera observability-system."""
        self.config_manager = config_manager
        self._lock = threading.RLock()
        self._start_time = time.time()

        # Events
        self._events: deque = deque(maxlen=10000)  # Håller senaste 10k events
        self._events_by_type: Dict[EventType, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._events_by_key: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

        # Metrics
        self._metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = defaultdict(float)

        # Effective config snapshots
        self._snapshots: deque = deque(maxlen=100)  # Håller senaste 100 snapshots
        self._snapshot_interval = 60.0  # Sekunder mellan snapshots
        self._last_snapshot = 0.0

        # Performance tracking
        self._operation_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._error_counts: Dict[str, int] = defaultdict(int)

        # Starta bakgrundstråd för snapshots
        self._start_background_tasks()

    def _start_background_tasks(self):
        """Starta bakgrundstrådar för observability."""

        def snapshot_worker():
            while True:
                try:
                    time.sleep(self._snapshot_interval)
                    self._capture_effective_config_snapshot()
                except Exception as e:
                    self._record_error("snapshot_worker", str(e))

        def metrics_cleanup_worker():
            while True:
                try:
                    time.sleep(300)  # 5 minuter
                    self._cleanup_old_metrics()
                except Exception as e:
                    self._record_error("metrics_cleanup", str(e))

        # Starta trådar
        threading.Thread(target=snapshot_worker, daemon=True).start()
        threading.Thread(target=metrics_cleanup_worker, daemon=True).start()

    def record_event(self, event: ConfigEvent):
        """Registrera en konfigurationshändelse."""
        with self._lock:
            self._events.append(event)
            self._events_by_type[event.event_type].append(event)
            self._events_by_key[event.key].append(event)

            # Uppdatera räknare
            self._counters[f"events_total_{event.event_type.value}"] += 1
            if event.success:
                self._counters[f"events_success_{event.event_type.value}"] += 1
            else:
                self._counters[f"events_failure_{event.event_type.value}"] += 1
                self._error_counts[event.key] += 1

    def record_metric(self, name: str, value: float, metric_type: MetricType, labels: Dict[str, str] = None):
        """Registrera en metric."""
        with self._lock:
            metric = ConfigMetric(
                name=name, metric_type=metric_type, value=value, timestamp=time.time(), labels=labels or {}
            )

            self._metrics[name].append(metric)

            if metric_type == MetricType.COUNTER:
                self._counters[name] += value
            elif metric_type == MetricType.GAUGE:
                self._gauges[name] = value

    def record_operation_time(self, operation: str, duration_ms: float):
        """Registrera operationstid."""
        with self._lock:
            self._operation_times[operation].append(duration_ms)
            self.record_metric(f"{operation}_duration_ms", duration_ms, MetricType.HISTOGRAM)

    def _record_error(self, component: str, error_message: str):
        """Registrera ett fel."""
        event = ConfigEvent(
            event_type=EventType.CONFIG_ERROR,
            timestamp=time.time(),
            key=component,
            error_message=error_message,
            success=False,
        )
        self.record_event(event)

    def _capture_effective_config_snapshot(self):
        """Fånga en snapshot av effektiv konfiguration."""
        try:
            current_time = time.time()
            if current_time - self._last_snapshot < self._snapshot_interval:
                return

            # Skapa snapshot för olika kontexter
            contexts = [
                ConfigContext(priority_profile=PriorityProfile.GLOBAL),
                ConfigContext(priority_profile=PriorityProfile.DOMAIN_POLICY),
            ]

            for context in contexts:
                config = self.config_manager.get_effective_config(context)
                generation = self.config_manager.config_store._generation

                # Räkna källor
                source_summary = defaultdict(int)
                from config.key_registry import KEY_REGISTRY

                for key_name in KEY_REGISTRY.keys():
                    try:
                        value = self.config_manager.get(key_name, context)
                        # Hitta källan (förenklad logik)
                        store_value = self.config_manager.config_store.get(key_name)
                        if store_value:
                            source_summary[store_value.source] += 1
                        else:
                            source_summary["default"] += 1
                    except Exception:
                        source_summary["error"] += 1

                snapshot = EffectiveConfigSnapshot(
                    timestamp=current_time,
                    context=context,
                    configuration=config,
                    generation=generation,
                    source_summary=dict(source_summary),
                )

                self._snapshots.append(snapshot)

            self._last_snapshot = current_time
            self.record_metric("effective_config_snapshots", 1, MetricType.COUNTER)

        except Exception as e:
            self._record_error("snapshot_capture", str(e))

    def _cleanup_old_metrics(self):
        """Rensa gamla metrics för att hålla minnesanvändning nere."""
        with self._lock:
            cutoff_time = time.time() - 3600  # 1 timme

            for metric_name, metrics in self._metrics.items():
                # Ta bort metrics äldre än 1 timme
                while metrics and metrics[0].timestamp < cutoff_time:
                    metrics.popleft()

    def get_events(
        self, event_type: EventType | None = None, key: str | None = None, limit: int = 100
    ) -> list[ConfigEvent]:
        """Hämta events med filtrering."""
        with self._lock:
            if event_type:
                events = list(self._events_by_type[event_type])
            elif key:
                events = list(self._events_by_key[key])
            else:
                events = list(self._events)

            return events[-limit:] if limit else events

    def get_metrics(self, metric_name: str | None = None, limit: int = 100) -> dict[str, Any]:
        """Hämta metrics."""
        with self._lock:
            if metric_name:
                metrics = list(self._metrics[metric_name])
                return {
                    "name": metric_name,
                    "metrics": metrics[-limit:] if limit else metrics,
                    "latest_value": metrics[-1].value if metrics else None,
                    "count": len(metrics),
                }
            else:
                # Returnera alla metrics
                result = {}
                for name, metrics_list in self._metrics.items():
                    if metrics_list:
                        result[name] = {
                            "latest_value": metrics_list[-1].value,
                            "count": len(metrics_list),
                            "latest_timestamp": metrics_list[-1].timestamp,
                        }
                return result

    def get_counters(self) -> dict[str, float]:
        """Hämta alla räknare."""
        with self._lock:
            return dict(self._counters)

    def get_gauges(self) -> dict[str, float]:
        """Hämta alla gauge-värden."""
        with self._lock:
            return dict(self._gauges)

    def get_operation_stats(self) -> dict[str, dict[str, float]]:
        """Hämta operationestatistik."""
        with self._lock:
            stats = {}
            for operation, times in self._operation_times.items():
                if times:
                    stats[operation] = {
                        "count": len(times),
                        "avg_ms": sum(times) / len(times),
                        "min_ms": min(times),
                        "max_ms": max(times),
                        "p95_ms": sorted(times)[int(len(times) * 0.95)] if times else 0,
                        "p99_ms": sorted(times)[int(len(times) * 0.99)] if times else 0,
                    }
            return stats

    def get_effective_config_snapshots(self, limit: int = 10) -> list[EffectiveConfigSnapshot]:
        """Hämta effektiva konfigurationssnapshots."""
        with self._lock:
            return list(self._snapshots)[-limit:] if limit else list(self._snapshots)

    def get_error_summary(self) -> dict[str, Any]:
        """Hämta felsammanfattning."""
        with self._lock:
            total_errors = sum(self._error_counts.values())
            recent_errors = []

            # Hitta senaste fel-events
            error_events = list(self._events_by_type[EventType.CONFIG_ERROR])
            for event in error_events[-10:]:  # Senaste 10 felen
                recent_errors.append(
                    {"timestamp": event.timestamp, "key": event.key, "error_message": event.error_message}
                )

            return {
                "total_errors": total_errors,
                "errors_by_key": dict(self._error_counts),
                "recent_errors": recent_errors,
                "error_rate": total_errors / max(len(self._events), 1),
            }

    def get_health_status(self) -> dict[str, Any]:
        """Hämta hälsostatus för konfigurationssystemet."""
        with self._lock:
            # Kontrollera olika komponenter
            health_checks = {
                "config_manager": self._check_config_manager_health(),
                "config_store": self._check_config_store_health(),
                "config_cache": self._check_config_cache_health(),
                "events_system": self._check_events_health(),
            }

            overall_healthy = all(health_checks.values())

            return {
                "overall_healthy": overall_healthy,
                "health_checks": health_checks,
                "uptime": time.time() - self._start_time if hasattr(self, '_start_time') else 0,
                "last_updated": time.time(),
            }

    def _check_config_manager_health(self) -> bool:
        """Kontrollera hälsa för config manager."""
        try:
            # Testa att hämta en konfiguration
            self.config_manager.get("DRY_RUN_ENABLED")
            return True
        except Exception:
            return False

    def _check_config_store_health(self) -> bool:
        """Kontrollera hälsa för config store."""
        try:
            stats = self.config_manager.config_store.get_stats()
            return stats.get("active_configs_count", 0) >= 0
        except Exception:
            return False

    def _check_config_cache_health(self) -> bool:
        """Kontrollera hälsa för config cache."""
        try:
            stats = self.config_manager.cache.get_stats()
            return stats.get("cache_size", 0) >= 0
        except Exception:
            return False

    def _check_events_health(self) -> bool:
        """Kontrollera hälsa för events-system."""
        try:
            # Kontrollera att events kan registreras
            test_event = ConfigEvent(event_type=EventType.CONFIG_GET, timestamp=time.time(), key="health_check")
            self.record_event(test_event)
            return True
        except Exception:
            return False

    def get_comprehensive_report(self) -> dict[str, Any]:
        """Hämta omfattande rapport om konfigurationssystemet."""
        with self._lock:
            return {
                "timestamp": time.time(),
                "health": self.get_health_status(),
                "metrics": {
                    "counters": self.get_counters(),
                    "gauges": self.get_gauges(),
                    "operation_stats": self.get_operation_stats(),
                },
                "events": {
                    "total_events": len(self._events),
                    "events_by_type": {
                        event_type.value: len(events) for event_type, events in self._events_by_type.items()
                    },
                    "recent_events": [
                        {
                            "type": event.event_type.value,
                            "key": event.key,
                            "timestamp": event.timestamp,
                            "success": event.success,
                        }
                        for event in list(self._events)[-10:]
                    ],
                },
                "effective_config": {
                    "snapshots_count": len(self._snapshots),
                    "latest_snapshot": self._snapshots[-1].timestamp if self._snapshots else None,
                    "generation": self.config_manager.config_store._generation,
                },
                "errors": self.get_error_summary(),
                "performance": {
                    "cache_hit_rate": self._calculate_cache_hit_rate(),
                    "avg_operation_time": self._calculate_avg_operation_time(),
                    "throughput": self._calculate_throughput(),
                },
            }

    def _calculate_cache_hit_rate(self) -> float:
        """Beräkna cache hit rate."""
        cache_hits = self._counters.get("events_total_cache_hit", 0)
        cache_misses = self._counters.get("events_total_cache_miss", 0)
        total = cache_hits + cache_misses
        return cache_hits / total if total > 0 else 0.0

    def _calculate_avg_operation_time(self) -> float:
        """Beräkna genomsnittlig operationstid."""
        all_times = []
        for times in self._operation_times.values():
            all_times.extend(times)
        return sum(all_times) / len(all_times) if all_times else 0.0

    def _calculate_throughput(self) -> float:
        """Beräkna genomströmning (events per sekund)."""
        if not self._events:
            return 0.0

        first_event_time = self._events[0].timestamp
        last_event_time = self._events[-1].timestamp
        duration = last_event_time - first_event_time

        return len(self._events) / duration if duration > 0 else 0.0


# Global observability instans
_observability: ConfigObservability | None = None


def get_config_observability(config_manager: UnifiedConfigManager = None) -> ConfigObservability:
    """Hämta global ConfigObservability-instans."""
    global _observability
    if _observability is None:
        if config_manager is None:
            from services.unified_config_manager import get_unified_config_manager

            config_manager = get_unified_config_manager()
        _observability = ConfigObservability(config_manager)
    return _observability


def record_config_event(event_type: EventType, key: str, **kwargs):
    """Konvenience-funktion för att registrera events."""
    event = ConfigEvent(event_type=event_type, timestamp=time.time(), key=key, **kwargs)
    get_config_observability().record_event(event)


def record_config_metric(name: str, value: float, metric_type: MetricType, labels: dict[str, str] = None):
    """Konvenience-funktion för att registrera metrics."""
    get_config_observability().record_metric(name, value, metric_type, labels)


def record_operation_time(operation: str, duration_ms: float):
    """Konvenience-funktion för att registrera operationstid."""
    get_config_observability().record_operation_time(operation, duration_ms)
