"""
Metrics store för enkel Prometheus-export.

Utökat med enkel histogramliknande latensmetrik per endpoint: count + sum i ms
med labels för path, method och status.
"""

from __future__ import annotations

from typing import Any, Dict

# Global but in-memory store (process-lokalt). Enkel och snabb.
metrics_store: Dict[str, Any] = {
    "orders_total": 0,
    "orders_failed_total": 0,
    "rate_limited_total": 0,
    # ackumulerad summa av order-submit-latens i ms
    "order_submit_ms": 0,
    # histogramliknande struktur: key -> {"count": int, "sum_ms": int}
    "request_latency": {},
    # generiska counters med labels: name -> { label_key -> count }
    "counters": {},
    # ws pool metrics
    "ws_pool": {
        "enabled": 0,
        "max_sockets": 0,
        "max_subs": 0,
        "sockets": [],  # list of {subs:int, closed:int}
    },
}


def inc(metric_name: str, by: int = 1) -> None:
    try:
        metrics_store[metric_name] = metrics_store.get(metric_name, 0) + by
    except Exception:
        pass


def _labels_to_str(labels: Dict[str, str]) -> str:
    # Enkel label-escaping för Prometheus-formatteringen
    def esc(value: str) -> str:
        return str(value).replace("\\", "\\\\").replace("\n", " ").replace('"', '\\"')

    parts = [f'{k}="{esc(v)}"' for k, v in labels.items()]
    return "{" + ",".join(parts) + "}"


def observe_latency(path: str, method: str, status_code: int, duration_ms: int) -> None:
    """Registrera en observation för request-latens (ms)."""
    try:
        # Trimma querydel och normalisera enklare path
        path_sanitized = str(path or "").split("?", 1)[0]
        key = f"{method.upper()}|{path_sanitized}|{int(status_code)}"
        bucket = metrics_store["request_latency"].get(key)
        if not bucket:
            bucket = {"count": 0, "sum_ms": 0}
            metrics_store["request_latency"][key] = bucket
        bucket["count"] += 1
        bucket["sum_ms"] += max(int(duration_ms), 0)
    except Exception:
        # Skydda mot alla fel i metrics (ska ej påverka huvudflödet)
        pass


def inc_labeled(name: str, labels: Dict[str, str], by: int = 1) -> None:
    """Öka en etiketterad counter med 1 (eller 'by')."""
    try:
        bucket = metrics_store["counters"].setdefault(name, {})
        key = _labels_to_str(labels)
        bucket[key] = int(bucket.get(key, 0)) + int(by)
    except Exception:
        pass


def render_prometheus_text() -> str:
    lines = [
        f"tradingbot_orders_total {metrics_store.get('orders_total', 0)}",
        f"tradingbot_orders_failed_total {metrics_store.get('orders_failed_total', 0)}",
        f"tradingbot_rate_limited_total {metrics_store.get('rate_limited_total', 0)}",
        f"tradingbot_order_submit_ms_total {metrics_store.get('order_submit_ms', 0)}",
        f"tradingbot_circuit_breaker_active {1 if metrics_store.get('circuit_breaker_active') else 0}",
    ]

    # Lägg till latensmetrik per endpoint
    try:
        lat: Dict[str, Dict[str, int]] = metrics_store.get("request_latency", {})
        for key, bucket in lat.items():
            try:
                method, path, status = key.split("|", 2)
                labels = _labels_to_str(
                    {
                        "path": path,
                        "method": method,
                        "status": str(status),
                    }
                )
                lines.append(
                    f"tradingbot_request_latency_ms_count{labels} {int(bucket.get('count', 0))}"
                )
                lines.append(
                    f"tradingbot_request_latency_ms_sum{labels} {int(bucket.get('sum_ms', 0))}"
                )
            except Exception:
                continue
    except Exception:
        pass

    # Labeled counters
    try:
        ctrs: Dict[str, Dict[str, int]] = metrics_store.get("counters", {})
        for metric_name, label_map in ctrs.items():
            for label_str, value in label_map.items():
                lines.append(f"tradingbot_{metric_name}{label_str} {int(value)}")
    except Exception:
        pass

    # WS pool metrics
    try:
        pool = metrics_store.get("ws_pool", {}) or {}
        lines.append(f"tradingbot_ws_pool_enabled {1 if pool.get('enabled') else 0}")
        lines.append(
            f"tradingbot_ws_pool_max_sockets {int(pool.get('max_sockets', 0))}"
        )
        lines.append(f"tradingbot_ws_pool_max_subs {int(pool.get('max_subs', 0))}")
        # per-socket
        socks = pool.get("sockets") or []
        for idx, s in enumerate(socks):
            labels = _labels_to_str({"index": str(idx)})
            lines.append(
                f"tradingbot_ws_pool_socket_subs{labels} {int(s.get('subs', 0))}"
            )
            lines.append(
                f"tradingbot_ws_pool_socket_closed{labels} {1 if s.get('closed') else 0}"
            )
            # varningsflagga: nära max_subs (>= 90%)
            max_subs = int(pool.get("max_subs", 0) or 0)
            warn = (
                1 if (max_subs and int(s.get("subs", 0)) >= int(0.9 * max_subs)) else 0
            )
            lines.append(f"tradingbot_ws_pool_socket_near_capacity{labels} {warn}")
    except Exception:
        pass

    return "\n".join(lines) + "\n"
