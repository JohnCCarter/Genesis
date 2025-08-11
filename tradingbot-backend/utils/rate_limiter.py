"""
Enkel in-process rate limiter (per nyckel) för att skydda känsliga endpoints.

Implementerar en sliding window med tidsstämplar i minne. Inte distribuerad.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, Dict


class _RateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events_by_key: Dict[str, Deque[float]] = {}

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """Returnerar True om anropet tillåts för given nyckel inom fönstret."""
        if max_requests <= 0 or window_seconds <= 0:
            return True
        now = time.monotonic()
        cutoff = now - float(window_seconds)
        with self._lock:
            q = self._events_by_key.setdefault(key, deque())
            # Prune
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= max_requests:
                return False
            q.append(now)
            return True


_singleton: _RateLimiter | None = None
_singleton_lock = threading.Lock()


def get_rate_limiter() -> _RateLimiter:
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = _RateLimiter()
    return _singleton
