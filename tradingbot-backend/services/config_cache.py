"""
Config Cache för snabb åtkomst till konfigurationsvärden

Hanterar per-process cache med invalidation och fallback-logik.
"""

import time
import threading
import logging
from typing import Any, Set, Callable
from dataclasses import dataclass
from .config_store import ConfigStore

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """En cache-post med metadata."""

    value: Any
    source: str
    generation: int
    timestamp: float
    ttl: float | None = None  # Time-to-live i sekunder

    def is_expired(self) -> bool:
        """Kontrollera om cache-posten är utgången."""
        if self.ttl is None:
            return False
        return time.time() - self.timestamp > self.ttl


class ConfigCache:
    """
    Per-process cache för konfigurationsvärden med invalidation.
    """

    def __init__(self, config_store: ConfigStore, default_ttl: float = 300.0):
        """
        Initiera config cache.

        Args:
            config_store: ConfigStore att använda för fallback
            default_ttl: Standard TTL för cache-poster i sekunder
        """
        self.config_store = config_store
        self.default_ttl = default_ttl
        self._cache: dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._invalidated_keys: set[str] = set()
        self._last_generation = 0
        self._invalidation_callbacks: list[callable[[str, int], None]] = []

        # Registrera callback för cache invalidation från store
        self._setup_store_callbacks()

    def get(self, key: str) -> Any | None:
        """
        Hämta värde från cache eller fallback till store.

        Args:
            key: Konfigurationsnyckel att hämta

        Returns:
            Konfigurationsvärde eller None om inte hittat
        """
        with self._lock:
            # Kontrollera cache först
            entry = self._cache.get(key)
            if entry and not entry.is_expired() and key not in self._invalidated_keys:
                return entry.value

            # Fallback till store
            store_value = self.config_store.get(key)
            if store_value is not None:
                self._set_cache_entry(key, store_value.value, store_value.source, store_value.generation)

            return store_value.value if store_value else None

    def set(self, key: str, value: Any, source: str, generation: int, ttl: float | None = None) -> None:
        """
        Sätt värde i cache.

        Args:
            key: Konfigurationsnyckel
            value: Värde att cacha
            source: Källa för värdet
            generation: Generationsnummer
            ttl: TTL för denna post (None för default)
        """
        with self._lock:
            self._set_cache_entry(key, value, source, generation, ttl)
            self._invalidated_keys.discard(key)

    def _set_cache_entry(self, key: str, value: Any, source: str, generation: int, ttl: float | None = None) -> None:
        """Intern metod för att sätta cache-post."""
        entry = CacheEntry(
            value=value, source=source, generation=generation, timestamp=time.time(), ttl=ttl or self.default_ttl
        )
        self._cache[key] = entry

    def invalidate(self, key: str) -> None:
        """
        Invalidera cache för en specifik nyckel.

        Args:
            key: Nyckel att invalidera
        """
        with self._lock:
            self._invalidated_keys.add(key)
            self._cache.pop(key, None)

    def invalidate_all(self) -> None:
        """Invalidera hela cachen."""
        with self._lock:
            self._invalidated_keys.clear()
            self._cache.clear()

    def invalidate_old_generations(self, min_generation: int) -> None:
        """
        Invalidera alla poster med generation < min_generation.

        Args:
            min_generation: Minsta generation att behålla
        """
        with self._lock:
            keys_to_remove = []
            for key, entry in self._cache.items():
                if entry.generation < min_generation:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                self._cache.pop(key, None)
                self._invalidated_keys.add(key)

    def get_stats(self) -> dict[str, Any]:
        """
        Hämta cache-statistik.

        Returns:
            Dictionary med cache-statistik
        """
        with self._lock:
            total_entries = len(self._cache)
            expired_entries = sum(1 for entry in self._cache.values() if entry.is_expired())
            invalidated_entries = len(self._invalidated_keys)

            return {
                "total_entries": total_entries,
                "expired_entries": expired_entries,
                "invalidated_entries": invalidated_entries,
                "active_entries": total_entries - expired_entries,
                "cache_hit_ratio": self._calculate_hit_ratio(),
                "last_generation": self._last_generation,
            }

    def _calculate_hit_ratio(self) -> float:
        """Beräkna cache hit-ratio (förenklad version)."""
        # I en riktig implementation skulle vi spåra hits/misses
        # För nu returnerar vi en placeholder
        return 0.0

    def cleanup_expired(self) -> int:
        """
        Rensa utgångna cache-poster.

        Returns:
            Antal poster som rensades
        """
        with self._lock:
            keys_to_remove = []
            for key, entry in self._cache.items():
                if entry.is_expired():
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                self._cache.pop(key, None)

            return len(keys_to_remove)

    def get_all_cached_keys(self) -> Set[str]:
        """
        Hämta alla nycklar som finns i cache.

        Returns:
            Set med alla cacha nycklar
        """
        with self._lock:
            return set(self._cache.keys())

    def is_cached(self, key: str) -> bool:
        """
        Kontrollera om en nyckel finns i cache och inte är utgången.

        Args:
            key: Nyckel att kontrollera

        Returns:
            True om nyckeln finns i cache och är giltig
        """
        with self._lock:
            entry = self._cache.get(key)
            return entry is not None and not entry.is_expired() and key not in self._invalidated_keys

    def _setup_store_callbacks(self):
        """Sätt upp callbacks för cache invalidation från store."""
        # Registrera callback i store för att få notifieringar om invalidation
        if hasattr(self.config_store, '_notify_cache_invalidation'):
            # Override store's callback för att hantera invalidation
            self.config_store._notify_cache_invalidation = self._handle_store_invalidation

    def _handle_store_invalidation(self, key: str, generation: int):
        """Hantera cache invalidation från store."""
        with self._lock:
            if key in self._cache:
                cached_entry = self._cache[key]
                if cached_entry.generation < generation:
                    # Invalidera cache-posten
                    self._invalidated_keys.add(key)
                    logger.debug(f"Invalidated cache for key {key} due to generation {generation}")

                    # Anropa invalidation callbacks
                    for callback in self._invalidation_callbacks:
                        try:
                            callback(key, generation)
                        except Exception as e:
                            logger.error(f"Error in invalidation callback: {e}")

    def register_invalidation_callback(self, callback: Callable[[str, int], None]):
        """
        Registrera callback för cache invalidation.

        Args:
            callback: Funktion som anropas vid invalidation (key, generation)
        """
        with self._lock:
            self._invalidation_callbacks.append(callback)

    def invalidate_by_generation(self, generation: int):
        """
        Invalidera alla cache-poster med lägre generation.

        Args:
            generation: Generationsnummer att invalidera mot
        """
        with self._lock:
            keys_to_invalidate = []
            for key, entry in self._cache.items():
                if entry.generation < generation:
                    keys_to_invalidate.append(key)

            for key in keys_to_invalidate:
                self._invalidated_keys.add(key)
                logger.debug(f"Invalidated cache for key {key} due to generation {generation}")

    def invalidate_pattern(self, pattern: str):
        """
        Invalidera cache-poster baserat på mönster.

        Args:
            pattern: Mönster att matcha mot nycklar (enkel string matching)
        """
        with self._lock:
            keys_to_invalidate = []
            for key in self._cache.keys():
                if pattern in key:
                    keys_to_invalidate.append(key)

            for key in keys_to_invalidate:
                self._invalidated_keys.add(key)
                logger.debug(f"Invalidated cache for key {key} matching pattern {pattern}")

    def get_cache_consistency_report(self) -> dict[str, Any]:
        """
        Hämta rapport om cache-konsistens.

        Returns:
            Dictionary med cache-konsistensinformation
        """
        with self._lock:
            total_entries = len(self._cache)
            invalidated_count = len(self._invalidated_keys)
            expired_count = 0
            generation_stats = {}

            for entry in self._cache.values():
                if entry.is_expired():
                    expired_count += 1

                gen = entry.generation
                generation_stats[gen] = generation_stats.get(gen, 0) + 1

            return {
                "total_entries": total_entries,
                "invalidated_count": invalidated_count,
                "expired_count": expired_count,
                "valid_entries": total_entries - invalidated_count - expired_count,
                "generation_distribution": generation_stats,
                "last_store_generation": self._last_generation,
                "callbacks_registered": len(self._invalidation_callbacks),
            }

    def force_refresh_from_store(self, key: str) -> Any | None:
        """
        Tvinga refresh av cache från store, oavsett cache-status.

        Args:
            key: Nyckel att refresha

        Returns:
            Värde från store eller None
        """
        with self._lock:
            # Ta bort från cache och invalidated keys
            self._cache.pop(key, None)
            self._invalidated_keys.discard(key)

            # Hämta från store
            store_value = self.config_store.get(key)
            if store_value:
                # Lägg tillbaka i cache
                entry = CacheEntry(
                    value=store_value.value,
                    source=store_value.source,
                    generation=store_value.generation,
                    timestamp=time.time(),
                    ttl=self.default_ttl,
                )
                self._cache[key] = entry
                self._last_generation = max(self._last_generation, store_value.generation)
                return store_value.value

            return None
