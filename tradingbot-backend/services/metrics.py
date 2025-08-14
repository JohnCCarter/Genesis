"""
Metrics store för enkel Prometheus-export.

Utökat med enkel histogramliknande latensmetrik per endpoint: count + sum i ms
med labels för path, method och status.
"""

from __future__ import annotations

from typing import Any, Dict

# Global but in-memory store (process-lokalt). Enkel och snabb.
metrics_store: dict[str, Any] = {
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
    # rolling validation snapshot
    "prob_validation": {
        # aggregate latest values
        "brier": None,
        "logloss": None,
        # optional per symbol/tf latest
        "by": {},  # key: "tPAIR|tf" -> {"brier": x, "logloss": y, "ts": epoch}
        # rolling windows (per size)
        "rolling": {},  # key: "window_min" -> list of {ts,brier,logloss}
    },
    # retraining status
    "prob_retrain": {
        "last_success": None,
        "last_error": None,
        "events": 0,
    },
}


def inc(metric_name: str, by: int = 1) -> None:
    try:
        metrics_store[metric_name] = metrics_store.get(metric_name, 0) + by
    except Exception:
        pass


def _labels_to_str(labels: dict[str, str]) -> str:
    # Enkel label-escaping för Prometheus-formatteringen
    def esc(value: str) -> str:
        v = str(value).replace("\\", "\\\\")
        v = v.replace("\n", " ")
        return v.replace('"', '\\"')

    parts = []
    for k, v in labels.items():
        parts.append(f'{k}="{esc(v)}"')
    return "{" + ",".join(parts) + "}"


def observe_latency(path: str, method: str, status_code: int, duration_ms: int) -> None:
    """Registrera en observation för request-latens (ms)."""
    try:
        # Trimma querydel och normalisera enklare path
        path_sanitized = str(path or "").split("?", 1)[0]
        method_u = method.upper()
        status_i = int(status_code)
        key = f"{method_u}|{path_sanitized}|{status_i}"
        bucket = metrics_store["request_latency"].get(key)
        if not bucket:
            bucket = {"count": 0, "sum_ms": 0}
            metrics_store["request_latency"][key] = bucket
        bucket["count"] += 1
        bucket["sum_ms"] += max(int(duration_ms), 0)
    except Exception:
        # Skydda mot alla fel i metrics (ska ej påverka huvudflödet)
        pass


def inc_labeled(name: str, labels: dict[str, str], by: int = 1) -> None:
    """Öka en etiketterad counter med 1 (eller 'by')."""
    try:
        bucket = metrics_store["counters"].setdefault(name, {})
        key = _labels_to_str(labels)
        bucket[key] = int(bucket.get(key, 0)) + int(by)
    except Exception:
        pass


def render_prometheus_text() -> str:
    lines = []
    orders_total = metrics_store.get("orders_total", 0)
    lines.append(f"tradingbot_orders_total {orders_total}")
    orders_failed = metrics_store.get("orders_failed_total", 0)
    lines.append(f"tradingbot_orders_failed_total {orders_failed}")
    rate_limited = metrics_store.get("rate_limited_total", 0)
    lines.append(f"tradingbot_rate_limited_total {rate_limited}")
    submit_ms = metrics_store.get("order_submit_ms", 0)
    lines.append(f"tradingbot_order_submit_ms_total {submit_ms}")
    cb_active = 1 if metrics_store.get("circuit_breaker_active") else 0
    lines.append(f"tradingbot_circuit_breaker_active {cb_active}")

    # Lägg till latensmetrik per endpoint
    try:
        lat: dict[str, dict[str, int]] = metrics_store.get("request_latency", {})
        for key, bucket in lat.items():
            try:
                method, path, status = key.split("|", 2)
                label_map = {"path": path, "method": method, "status": str(status)}
                labels = _labels_to_str(label_map)
                cnt = int(bucket.get("count", 0))
                metric = "tradingbot_request_latency_ms_count"
                lines.append(f"{metric}{labels} {cnt}")
                sum_ms = int(bucket.get("sum_ms", 0))
                metric = "tradingbot_request_latency_ms_sum"
                lines.append(f"{metric}{labels} {sum_ms}")
            except Exception:
                continue
    except Exception:
        pass

    # Labeled counters
    try:
        ctrs: dict[str, dict[str, int]] = metrics_store.get("counters", {})
        for metric_name, label_map in ctrs.items():
            for label_str, value in label_map.items():
                val_int = int(value)
                lines.append(f"tradingbot_{metric_name}{label_str} {val_int}")
    except Exception:
        pass

    # WS pool metrics
    try:
        pool = metrics_store.get("ws_pool", {}) or {}
        enabled_flag = 1 if pool.get("enabled") else 0
        lines.append(f"tradingbot_ws_pool_enabled {enabled_flag}")
        max_sockets = int(pool.get("max_sockets", 0))
        lines.append(f"tradingbot_ws_pool_max_sockets {max_sockets}")
        max_subs_total = int(pool.get("max_subs", 0))
        lines.append(f"tradingbot_ws_pool_max_subs {max_subs_total}")
        # per-socket
        socks = pool.get("sockets") or []
        for idx, s in enumerate(socks):
            labels = _labels_to_str({"index": str(idx)})
            subs_val = int(s.get("subs", 0))
            lines.append(f"tradingbot_ws_pool_socket_subs{labels} {subs_val}")
            closed_flag = 1 if s.get("closed") else 0
            lines.append(f"tradingbot_ws_pool_socket_closed{labels} {closed_flag}")
            # varningsflagga: nära max_subs (>= 90%)
            max_subs = int(pool.get("max_subs", 0) or 0)
            near = int(0.9 * max_subs) if max_subs else 0
            subs_now = int(s.get("subs", 0))
            warn = 1 if (max_subs and subs_now >= near) else 0
            lines.append(f"tradingbot_ws_pool_socket_near_capacity{labels} {warn}")
    except Exception:
        pass

    # Probability validation snapshot
    try:
        pv_any = metrics_store.get("prob_validation", {}) or {}
        pv: dict[str, Any] = pv_any  # typing aid
        brier = pv.get("brier")
        logloss = pv.get("logloss")
        if brier is not None:
            try:
                val = float(brier or 0.0)
                lines.append(f"tradingbot_prob_brier {val}")
            except Exception:
                pass
        if logloss is not None:
            try:
                val = float(logloss or 0.0)
                lines.append(f"tradingbot_prob_logloss {val}")
            except Exception:
                pass
        by_any = pv.get("by") or {}
        by_map: dict[str, dict[str, Any]] = by_any
        for key, vals in by_map.items():
            try:
                sym, tf = key.split("|", 1)
            except Exception:
                sym, tf = key, ""
            labels = _labels_to_str({"symbol": sym, "tf": tf})
            if isinstance(vals, dict):
                if vals.get("brier") is not None:
                    try:
                        metric_name = "tradingbot_prob_brier_latest"
                        metric_val = float(vals.get("brier") or 0.0)
                        lines.append(f"{metric_name}{labels} {metric_val}")
                    except Exception:
                        pass
                if vals.get("logloss") is not None:
                    try:
                        metric_name = "tradingbot_prob_logloss_latest"
                        metric_val = float(vals.get("logloss") or 0.0)
                        lines.append(f"{metric_name}{labels} {metric_val}")
                    except Exception:
                        pass
        # Rolling window aggregates (exponera nuvarande medel per fönster)
        try:
            rolling_any = pv.get("rolling") or {}
            rolling: dict[str, Any] = rolling_any
            for window_key, series in rolling.items():
                try:
                    if not isinstance(series, list) or not series:
                        continue
                    # Enkelt medel av senaste N (redan trimmas i scheduler)
                    b_vals = [float(x.get("brier")) for x in series if x.get("brier") is not None]
                    l_vals = [
                        float(x.get("logloss")) for x in series if x.get("logloss") is not None
                    ]
                    labels = _labels_to_str({"window": str(window_key)})
                    if b_vals:
                        lines.append(
                            f"tradingbot_prob_brier_window{labels} {sum(b_vals) / max(1, len(b_vals))}"
                        )
                    if l_vals:
                        lines.append(
                            f"tradingbot_prob_logloss_window{labels} {sum(l_vals) / max(1, len(l_vals))}"
                        )
                    lines.append(f"tradingbot_prob_validate_samples_window{labels} {len(series)}")
                except Exception:
                    continue
        except Exception:
            pass
    except Exception:
        pass

    return "\n".join(lines) + "\n"
