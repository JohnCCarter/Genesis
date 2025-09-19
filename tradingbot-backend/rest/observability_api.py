"""
Observability API endpoints för konfigurationssystemet

Ger endpoints för metrics, events, health checks och comprehensive reporting.
"""

import time
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from services.config_observability import (
    get_config_observability,
    ConfigObservability,
    EventType,
    MetricType,
    ConfigEvent,
    ConfigMetric,
    EffectiveConfigSnapshot,
)
from rest.unified_config_api import get_user_from_token

# Router
router = APIRouter(prefix="/api/v2/observability", tags=["observability"])


# Pydantic Models
class EventFilter(BaseModel):
    """Filter för events."""

    event_type: str | None = Field(None, description="Event type filter")
    key: str | None = Field(None, description="Key filter")
    user: str | None = Field(None, description="User filter")
    success: bool | None = Field(None, description="Success filter")
    limit: int = Field(100, description="Maximum number of events to return")


class MetricFilter(BaseModel):
    """Filter för metrics."""

    metric_name: str | None = Field(None, description="Specific metric name")
    limit: int = Field(100, description="Maximum number of metrics to return")
    start_time: float | None = Field(None, description="Start timestamp filter")
    end_time: float | None = Field(None, description="End timestamp filter")


class HealthCheckResponse(BaseModel):
    """Response för health check."""

    overall_healthy: bool = Field(..., description="Overall system health")
    health_checks: dict[str, bool] = Field(..., description="Individual health checks")
    uptime: float = Field(..., description="System uptime in seconds")
    last_updated: float = Field(..., description="Last update timestamp")


class MetricsResponse(BaseModel):
    """Response för metrics."""

    counters: dict[str, float] = Field(..., description="Counter metrics")
    gauges: dict[str, float] = Field(..., description="Gauge metrics")
    operation_stats: dict[str, dict[str, float]] = Field(..., description="Operation statistics")
    cache_hit_rate: float = Field(..., description="Cache hit rate")
    avg_operation_time: float = Field(..., description="Average operation time")
    throughput: float = Field(..., description="Events per second")


class EventsResponse(BaseModel):
    """Response för events."""

    events: list[dict[str, Any]] = Field(..., description="List of events")
    total_count: int = Field(..., description="Total number of events")
    filtered_count: int = Field(..., description="Number of events after filtering")


class EffectiveConfigResponse(BaseModel):
    """Response för effective config snapshots."""

    snapshots: list[dict[str, Any]] = Field(..., description="Effective config snapshots")
    count: int = Field(..., description="Number of snapshots")
    latest_generation: int = Field(..., description="Latest configuration generation")


class ComprehensiveReportResponse(BaseModel):
    """Response för comprehensive report."""

    timestamp: float = Field(..., description="Report timestamp")
    health: HealthCheckResponse = Field(..., description="Health status")
    metrics: MetricsResponse = Field(..., description="Metrics summary")
    events: dict[str, Any] = Field(..., description="Events summary")
    effective_config: dict[str, Any] = Field(..., description="Effective config summary")
    errors: dict[str, Any] = Field(..., description="Error summary")
    performance: dict[str, float] = Field(..., description="Performance metrics")


# API Endpoints
@router.get("/health", response_model=HealthCheckResponse)
async def get_health_status(user: dict[str, Any] = Depends(get_user_from_token)):
    """Hämta hälsostatus för konfigurationssystemet."""
    observability = get_config_observability()
    health_data = observability.get_health_status()

    return HealthCheckResponse(
        overall_healthy=health_data["overall_healthy"],
        health_checks=health_data["health_checks"],
        uptime=health_data["uptime"],
        last_updated=health_data["last_updated"],
    )


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(user: dict[str, Any] = Depends(get_user_from_token)):
    """Hämta metrics för konfigurationssystemet."""
    observability = get_config_observability()

    counters = observability.get_counters()
    gauges = observability.get_gauges()
    operation_stats = observability.get_operation_stats()

    # Beräkna derived metrics
    cache_hit_rate = observability._calculate_cache_hit_rate()
    avg_operation_time = observability._calculate_avg_operation_time()
    throughput = observability._calculate_throughput()

    return MetricsResponse(
        counters=counters,
        gauges=gauges,
        operation_stats=operation_stats,
        cache_hit_rate=cache_hit_rate,
        avg_operation_time=avg_operation_time,
        throughput=throughput,
    )


@router.get("/metrics/{metric_name}")
async def get_specific_metric(
    metric_name: str,
    limit: int = Query(100, description="Maximum number of data points"),
    user: dict[str, Any] = Depends(get_user_from_token),
):
    """Hämta specifik metric med historik."""
    observability = get_config_observability()
    metric_data = observability.get_metrics(metric_name, limit)

    if not metric_data:
        raise HTTPException(status_code=404, detail=f"Metric '{metric_name}' not found")

    return metric_data


@router.post("/events", response_model=EventsResponse)
async def get_events(filter_data: EventFilter, user: dict[str, Any] = Depends(get_user_from_token)):
    """Hämta events med filtrering."""
    observability = get_config_observability()

    # Konvertera event_type string till EventType enum om specificerat
    event_type = None
    if filter_data.event_type:
        try:
            event_type = EventType(filter_data.event_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid event type: {filter_data.event_type}")

    # Hämta events
    events = observability.get_events(event_type=event_type, key=filter_data.key, limit=filter_data.limit)

    # Filtrera ytterligare baserat på user och success
    filtered_events = []
    for event in events:
        if filter_data.user and event.user != filter_data.user:
            continue
        if filter_data.success is not None and event.success != filter_data.success:
            continue

        filtered_events.append(
            {
                "event_type": event.event_type.value,
                "timestamp": event.timestamp,
                "key": event.key,
                "user": event.user,
                "source": event.source,
                "value": event.value,
                "old_value": event.old_value,
                "duration_ms": event.duration_ms,
                "success": event.success,
                "error_message": event.error_message,
                "metadata": event.metadata,
            }
        )

    return EventsResponse(
        events=filtered_events, total_count=len(observability._events), filtered_count=len(filtered_events)
    )


@router.get("/events/recent")
async def get_recent_events(
    limit: int = Query(50, description="Maximum number of recent events"),
    user: dict[str, Any] = Depends(get_user_from_token),
):
    """Hämta senaste events."""
    observability = get_config_observability()
    events = observability.get_events(limit=limit)

    return {
        "events": [
            {
                "event_type": event.event_type.value,
                "timestamp": event.timestamp,
                "key": event.key,
                "user": event.user,
                "success": event.success,
                "error_message": event.error_message,
            }
            for event in events
        ],
        "count": len(events),
    }


@router.get("/effective-config", response_model=EffectiveConfigResponse)
async def get_effective_config_snapshots(
    limit: int = Query(10, description="Maximum number of snapshots"),
    user: dict[str, Any] = Depends(get_user_from_token),
):
    """Hämta effektiva konfigurationssnapshots."""
    observability = get_config_observability()
    snapshots = observability.get_effective_config_snapshots(limit)

    # Konvertera snapshots till serializable format
    serialized_snapshots = []
    for snapshot in snapshots:
        serialized_snapshots.append(
            {
                "timestamp": snapshot.timestamp,
                "context": {
                    "priority_profile": snapshot.context.priority_profile.value,
                    "user": snapshot.context.user,
                    "source_override": snapshot.context.source_override,
                },
                "configuration": snapshot.configuration,
                "generation": snapshot.generation,
                "source_summary": snapshot.source_summary,
            }
        )

    latest_generation = snapshots[-1].generation if snapshots else 0

    return EffectiveConfigResponse(
        snapshots=serialized_snapshots, count=len(snapshots), latest_generation=latest_generation
    )


@router.get("/errors")
async def get_error_summary(user: dict[str, Any] = Depends(get_user_from_token)):
    """Hämta felsammanfattning."""
    observability = get_config_observability()
    error_summary = observability.get_error_summary()

    return error_summary


@router.get("/performance")
async def get_performance_metrics(user: dict[str, Any] = Depends(get_user_from_token)):
    """Hämta prestandametrics."""
    observability = get_config_observability()

    return {
        "cache_hit_rate": observability._calculate_cache_hit_rate(),
        "avg_operation_time": observability._calculate_avg_operation_time(),
        "throughput": observability._calculate_throughput(),
        "operation_stats": observability.get_operation_stats(),
        "timestamp": time.time(),
    }


@router.get("/report", response_model=ComprehensiveReportResponse)
async def get_comprehensive_report(user: dict[str, Any] = Depends(get_user_from_token)):
    """Hämta omfattande rapport om konfigurationssystemet."""
    observability = get_config_observability()
    report = observability.get_comprehensive_report()

    # Konvertera till response format
    health_data = report["health"]
    health_response = HealthCheckResponse(
        overall_healthy=health_data["overall_healthy"],
        health_checks=health_data["health_checks"],
        uptime=health_data["uptime"],
        last_updated=health_data["last_updated"],
    )

    metrics_data = report["metrics"]
    metrics_response = MetricsResponse(
        counters=metrics_data["counters"],
        gauges=metrics_data["gauges"],
        operation_stats=metrics_data["operation_stats"],
        cache_hit_rate=report["performance"]["cache_hit_rate"],
        avg_operation_time=report["performance"]["avg_operation_time"],
        throughput=report["performance"]["throughput"],
    )

    return ComprehensiveReportResponse(
        timestamp=report["timestamp"],
        health=health_response,
        metrics=metrics_response,
        events=report["events"],
        effective_config=report["effective_config"],
        errors=report["errors"],
        performance=report["performance"],
    )


@router.post("/metrics/custom")
async def record_custom_metric(
    name: str,
    value: float,
    metric_type: str = "gauge",
    labels: dict[str, str] = None,
    user: dict[str, Any] = Depends(get_user_from_token),
):
    """Registrera en anpassad metric."""
    try:
        metric_type_enum = MetricType(metric_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid metric type: {metric_type}")

    observability = get_config_observability()
    observability.record_metric(name, value, metric_type_enum, labels or {})

    return {
        "success": True,
        "message": f"Metric '{name}' recorded successfully",
        "metric": {"name": name, "value": value, "type": metric_type, "labels": labels or {}, "timestamp": time.time()},
    }


@router.get("/alerts")
async def get_alerts(user: dict[str, Any] = Depends(get_user_from_token)):
    """Hämta aktiva alerts baserat på metrics och events."""
    observability = get_config_observability()
    alerts = []

    # Kontrollera olika alert-villkor
    health = observability.get_health_status()
    if not health["overall_healthy"]:
        alerts.append(
            {
                "severity": "critical",
                "message": "System health check failed",
                "timestamp": time.time(),
                "details": health["health_checks"],
            }
        )

    # Kontrollera fel-rate
    error_summary = observability.get_error_summary()
    if error_summary["error_rate"] > 0.1:  # 10% fel-rate
        alerts.append(
            {
                "severity": "warning",
                "message": f"High error rate: {error_summary['error_rate']:.2%}",
                "timestamp": time.time(),
                "details": error_summary,
            }
        )

    # Kontrollera cache hit rate
    cache_hit_rate = observability._calculate_cache_hit_rate()
    if cache_hit_rate < 0.8:  # Under 80% cache hit rate
        alerts.append(
            {
                "severity": "warning",
                "message": f"Low cache hit rate: {cache_hit_rate:.2%}",
                "timestamp": time.time(),
                "details": {"cache_hit_rate": cache_hit_rate},
            }
        )

    # Kontrollera operationstider
    operation_stats = observability.get_operation_stats()
    for operation, stats in operation_stats.items():
        if stats["avg_ms"] > 1000:  # Över 1 sekund genomsnitt
            alerts.append(
                {
                    "severity": "warning",
                    "message": f"Slow operation '{operation}': {stats['avg_ms']:.2f}ms average",
                    "timestamp": time.time(),
                    "details": stats,
                }
            )

    return {"alerts": alerts, "count": len(alerts), "timestamp": time.time()}


@router.get("/dashboard")
async def get_dashboard_data(user: dict[str, Any] = Depends(get_user_from_token)):
    """Hämta dashboard-data för konfigurationsövervakning."""
    observability = get_config_observability()

    # Hämta alla relevanta data för dashboard
    health = observability.get_health_status()
    metrics = observability.get_metrics()
    recent_events = observability.get_events(limit=20)
    error_summary = observability.get_error_summary()

    # Skapa dashboard-widgets
    widgets = {
        "health_status": {
            "healthy": health["overall_healthy"],
            "checks": health["health_checks"],
            "uptime": health["uptime"],
        },
        "key_metrics": {
            "total_events": len(observability._events),
            "cache_hit_rate": observability._calculate_cache_hit_rate(),
            "error_rate": error_summary["error_rate"],
            "throughput": observability._calculate_throughput(),
        },
        "recent_activity": [
            {
                "type": event.event_type.value,
                "key": event.key,
                "timestamp": event.timestamp,
                "success": event.success,
                "user": event.user,
            }
            for event in recent_events[-10:]
        ],
        "top_errors": list(error_summary["errors_by_key"].items())[:5],
        "performance": observability.get_operation_stats(),
    }

    return {"widgets": widgets, "timestamp": time.time(), "refresh_interval": 30}  # Sekunder
