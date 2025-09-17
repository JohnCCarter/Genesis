"""
Lightweight Server-Timing utilities.

Usage:
- Call reset() at request start (middleware)
- Use timed("metric") context manager or add("metric", ms) inside handlers/services
- At response, set header from get_header([...extra segments...])
"""

from __future__ import annotations

import time
from contextvars import ContextVar
from typing import Any

_server_timing: ContextVar[list[str] | None] = ContextVar(
    "_server_timing", default=None
)


def reset() -> None:
    """Reset timing buffer for current context/request."""
    try:
        _server_timing.set([])
    except Exception:
        pass


def add(metric: str, duration_ms: float | int) -> None:
    """Add a Server-Timing metric entry."""
    try:
        lst = list(_server_timing.get() or [])
        lst.append(f"{metric};dur={float(duration_ms):.1f}")
        _server_timing.set(lst)
    except Exception:
        pass


class _Timer:
    __slots__ = ("_metric", "_t0")

    def __init__(self, metric: str) -> None:
        self._metric = metric
        self._t0 = 0.0

    def __enter__(self) -> _Timer:
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        try:
            dt_ms = (time.perf_counter() - self._t0) * 1000.0
            add(self._metric, dt_ms)
        except Exception:
            pass


def timed(metric: str) -> _Timer:
    """Context manager to record a timing span for metric."""
    return _Timer(metric)


def get_header(extra_segments: list[str] | None = None) -> str | None:
    """Render Server-Timing header value for current context."""
    try:
        parts = list(_server_timing.get())
        if extra_segments:
            parts.extend(extra_segments)
        if not parts:
            return None
        return ", ".join(parts)
    except Exception:
        return None
