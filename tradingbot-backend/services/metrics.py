"""
Metrics store för enkel Prometheus-export.
"""

from __future__ import annotations

from typing import Dict


metrics_store: Dict[str, int] = {
    "orders_total": 0,
    "orders_failed_total": 0,
}


def inc(metric_name: str, by: int = 1) -> None:
    try:
        metrics_store[metric_name] = metrics_store.get(metric_name, 0) + by
    except Exception:
        pass


def render_prometheus_text() -> str:
    lines = [
        f"tradingbot_orders_total {metrics_store.get('orders_total', 0)}",
        f"tradingbot_orders_failed_total {metrics_store.get('orders_failed_total', 0)}",
    ]
    return "\n".join(lines) + "\n"


