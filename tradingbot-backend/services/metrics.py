"""
Metrics store för enkel Prometheus-export.

Utökat med enkel histogramliknande latensmetrik per endpoint: count + sum i ms
med labels för path, method och status.
"""

from __future__ import annotations

import bisect
from typing import Any

# Global but in-memory store (process-lokalt). Enkel och snabb.
metrics_store: dict[str, Any] = {
    "orders_total": 0,
    "orders_failed_total": 0,
    "rate_limited_total": 0,
    # ackumulerad summa av order-submit-latens i ms
    "order_submit_ms": 0,
    # histogramliknande struktur: key -> {"count": int, "sum_ms": int}
    "request_latency": {},
    # begränsad provtagning per endpoint för kvantiler
    "request_latency_samples": {},  # key -> List[int] (ms), kapad till 200
    # HTTP-felräknare
    "http_errors": {},  # key -> count (key == method|path|status)
    # HTTP-fel events per status (för fönster-beräkningar)
    "http_error_events": {},  # status(str) -> list[int(epoch_sec)]
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


def _samples_key(path: str, method: str, status_code: int) -> str:
    path_sanitized = str(path or "").split("?", 1)[0]
    return f"{method.upper()}|{path_sanitized}|{int(status_code)}"


def record_http_result(
    path: str, method: str, status_code: int, duration_ms: int, _retry_after: str | None = None
) -> None:
    """Registrera latens och felstatistik för ett HTTP-anrop.

    - Lagrar count/sum
    - Lagrar begränsad provmängd för kvantilestimat
    - Ökar felräknare för 429/503/5xx
    """
    try:
        observe_latency(path, method, status_code, duration_ms)
        key = _samples_key(path, method, status_code)
        samples = metrics_store["request_latency_samples"].get(key) or []
        # håll listan sorterad (insätt sorterat) och kapa längden
        val = max(int(duration_ms), 0)
        bisect.insort(samples, val)
        if len(samples) > 200:
            # ta bort äldsta/lägsta för att hålla storleken i schack
            samples.pop(0)
        metrics_store["request_latency_samples"][key] = samples

        # felräknare
        if int(status_code) >= 400:
            err_bucket = metrics_store["http_errors"].get(key, 0)
            metrics_store["http_errors"][key] = int(err_bucket) + 1
            # registrera enkel timestamp per status
            try:
                import time as _t

                ts = int(_t.time())
                st_key = str(int(status_code))
                lst = metrics_store["http_error_events"].get(st_key) or []
                lst.append(ts)
                if len(lst) > 2000:
                    # trimma äldsta
                    lst = lst[-2000:]
                metrics_store["http_error_events"][st_key] = lst
            except Exception:
                pass
    except Exception:
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
    # Ny: separerad export för Trading vs Transport circuit breakers
    tcb = 1 if metrics_store.get("trading_circuit_breaker_active") else 0
    lines.append(f"tradingbot_trading_circuit_breaker_active {tcb}")
    xcb = 1 if metrics_store.get("transport_circuit_breaker_active") else 0
    lines.append(f"tradingbot_transport_circuit_breaker_active {xcb}")

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
                # kvantiler p50/p95/p99 från samples om tillgängligt
                samples_map = metrics_store.get("request_latency_samples", {})
                samples = samples_map.get(key) or []
                if samples:

                    def q(p: float, arr: list[int] = samples) -> int:
                        if not arr:
                            return 0
                        idx = int(max(0, min(len(arr) - 1, round((p / 100.0) * (len(arr) - 1)))))
                        return int(arr[idx])

                    lines.append(f"tradingbot_request_latency_ms_p50{labels} {q(50)}")
                    lines.append(f"tradingbot_request_latency_ms_p95{labels} {q(95)}")
                    lines.append(f"tradingbot_request_latency_ms_p99{labels} {q(99)}")
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

    # HTTP error totals (labeled)
    try:
        errs: dict[str, int] = metrics_store.get("http_errors", {})
        for key, val in errs.items():
            try:
                method, path, status = key.split("|", 2)
                labels = _labels_to_str({"path": path, "method": method, "status": status})
                lines.append(f"tradingbot_http_errors_total{labels} {int(val)}")
            except Exception:
                continue
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
                    l_vals = [float(x.get("logloss")) for x in series if x.get("logloss") is not None]
                    labels = _labels_to_str({"window": str(window_key)})
                    if b_vals:
                        lines.append(f"tradingbot_prob_brier_window{labels} {sum(b_vals) / max(1, len(b_vals))}")
                    if l_vals:
                        lines.append(f"tradingbot_prob_logloss_window{labels} {sum(l_vals) / max(1, len(l_vals))}")
                    lines.append(f"tradingbot_prob_validate_samples_window{labels} {len(series)}")
                except Exception:
                    continue
        except Exception:
            pass
    except Exception:
        pass

    return "\n".join(lines) + "\n"


# ---- Helpers för JSON-sammanfattning ----
def _flatten_samples_for_path_contains(substr: str) -> list[int]:
    try:
        subs = str(substr or "")
        samples_map = metrics_store.get("request_latency_samples", {})
        out: list[int] = []
        for key, vals in samples_map.items():
            try:
                method, path, status = key.split("|", 2)
            except Exception:
                continue
            if subs and subs not in path:
                continue
            out.extend(int(v) for v in vals or [])
        out.sort()
        return out
    except Exception:
        return []


def _quantiles(arr: list[int], ps: list[float]) -> dict[str, int]:
    if not arr:
        return {f"p{int(p)}": 0 for p in ps}
    out: dict[str, int] = {}
    n = len(arr)
    for p in ps:
        idx = int(max(0, min(n - 1, round((p / 100.0) * (n - 1)))))
        out[f"p{int(p)}"] = int(arr[idx])
    return out


def get_recent_error_counts(window_seconds: int = 3600, statuses: list[int] | None = None) -> dict[str, int]:
    try:
        import time as _t

        now = int(_t.time())
        if statuses is None:
            statuses = [429, 503]
        res: dict[str, int] = {}
        events: dict[str, list[int]] = metrics_store.get("http_error_events", {}) or {}
        for st in statuses:
            key = str(int(st))
            lst = events.get(key) or []
            cnt = 0
            if lst:
                cutoff = now - int(window_seconds)
                # listan är redan trimmas; enkel linjär filtrering duger
                for ts in lst:
                    if int(ts) >= cutoff:
                        cnt += 1
            res[key] = cnt
        return res
    except Exception:
        return {"429": 0, "503": 0}


def get_metrics_summary() -> dict[str, Any]:
    try:
        candles_samples = _flatten_samples_for_path_contains("/candles")
        q = _quantiles(candles_samples, [50, 95, 99])
        err_total = {}
        # summera totals per status från http_errors
        try:
            errs: dict[str, int] = metrics_store.get("http_errors", {}) or {}
            agg: dict[str, int] = {}
            for key, val in errs.items():
                try:
                    _, _, status = key.split("|", 2)
                    agg[status] = int(agg.get(status, 0)) + int(val)
                except Exception:
                    continue
            err_total = {k: int(v) for k, v in agg.items() if k in ("429", "503")}
        except Exception:
            err_total = {}
        err_recent = get_recent_error_counts(3600, [429, 503])
        return {
            "latency": {"candles_ms": q, "samples": len(candles_samples)},
            "errors": {"last_hour": err_recent, "total": err_total},
        }
    except Exception:
        return {
            "latency": {"candles_ms": {"p50": 0, "p95": 0, "p99": 0}, "samples": 0},
            "errors": {"last_hour": {}, "total": {}},
        }
