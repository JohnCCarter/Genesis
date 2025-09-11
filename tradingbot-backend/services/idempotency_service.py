# AI Change: Add IdempotencyService for centralized request idempotency (Agent: Codex, Date: 2025-09-11)
from __future__ import annotations

import threading
import time
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)


class IdempotencyService:
    """Enkel TTL-baserad idempotenscache för request-responser.

    - check_and_register: returnerar tidigare svar om nyckeln finns och inte är utgången,
      annars registrerar nyckeln som 'in-flight' och låter uppringaren fortsätta.
    - store_response: sparar svar för nyckeln med tidsstämpel.
    - get: hämtar svar om tillgängligt.
    """

    def __init__(self, default_ttl_seconds: int = 60) -> None:
        self.default_ttl_seconds = max(1, int(default_ttl_seconds))
        self._lock = threading.Lock()
        self._entries: dict[str, dict[str, Any]] = {}

    def _now(self) -> int:
        return int(time.time())

    def _expired(self, ts: int, ttl: int | None) -> bool:
        ttl_use = int(ttl) if ttl is not None else self.default_ttl_seconds
        return (self._now() - int(ts)) >= max(1, ttl_use)

    def get(self, key: str, ttl_seconds: int | None = None) -> Any | None:
        try:
            k = (key or "").strip()
            if not k:
                return None
            with self._lock:
                entry = self._entries.get(k)
                if not entry:
                    return None
                if self._expired(int(entry.get("ts", 0)), ttl_seconds):
                    # Rensa utgången post
                    try:
                        del self._entries[k]
                    except Exception:
                        pass
                    return None
                return entry.get("resp")
        except Exception as e:
            logger.debug(f"IdempotencyService.get fel: {e}")
            return None

    def check_and_register(self, key: str, ttl_seconds: int | None = None) -> Any | None:
        """Returnera tidigare svar om giltigt, annars registrera placeholder och returnera None."""
        try:
            k = (key or "").strip()
            if not k:
                return None
            with self._lock:
                entry = self._entries.get(k)
                if entry and not self._expired(int(entry.get("ts", 0)), ttl_seconds):
                    return entry.get("resp")
                # registrera placeholder
                self._entries[k] = {"ts": self._now(), "resp": None}
                return None
        except Exception as e:
            logger.debug(f"IdempotencyService.check_and_register fel: {e}")
            return None

    def store_response(self, key: str, response: Any) -> None:
        try:
            k = (key or "").strip()
            if not k:
                return
            with self._lock:
                self._entries[k] = {"ts": self._now(), "resp": response}
        except Exception as e:
            logger.debug(f"IdempotencyService.store_response fel: {e}")


_idempotency_singleton: IdempotencyService | None = None


def get_idempotency_service() -> IdempotencyService:
    global _idempotency_singleton
    if _idempotency_singleton is None:
        _idempotency_singleton = IdempotencyService()
    return _idempotency_singleton
