# AI Change: Add MetricsClient wrapper (Agent: Codex, Date: 2025-09-11)
from __future__ import annotations

from typing import Any

from services.metrics import (
    metrics_store as _store,
    inc as _inc,
    inc_labeled as _inc_labeled,
    observe_latency as _observe_latency,
    record_http_result as _record_http_result,
    render_prometheus_text as _render_prom,
    get_metrics_summary as _get_summary,
)


class MetricsClient:
    """Tunn wrapper för att standardisera metrics-anrop.

    Använder befintlig in-memory store och funktioner.
    """

    @property
    def store(self) -> dict[str, Any]:
        return _store

    def inc(self, name: str, by: int = 1) -> None:
        _inc(name, by)

    def inc_labeled(self, name: str, labels: dict[str, str], by: int = 1) -> None:
        _inc_labeled(name, labels, by)

    def observe_latency(
        self, path: str, method: str, status_code: int, duration_ms: int
    ) -> None:
        _observe_latency(path, method, status_code, duration_ms)

    def record_http_result(
        self,
        path: str,
        method: str,
        status_code: int,
        duration_ms: int,
        retry_after: str | None = None,
    ) -> None:
        _record_http_result(path, method, status_code, duration_ms, retry_after)

    def render_prometheus_text(self) -> str:
        return _render_prom()

    def summary(self) -> dict[str, Any]:
        return _get_summary()


_metrics_client_singleton: MetricsClient | None = None


def get_metrics_client() -> MetricsClient:
    global _metrics_client_singleton
    if _metrics_client_singleton is None:
        _metrics_client_singleton = MetricsClient()
    return _metrics_client_singleton
