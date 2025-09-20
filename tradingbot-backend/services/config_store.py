"""
Config Store med Central DB/Redis för kluster-konsistens

Hanterar central lagring av konfigurationsvärden med pub/sub och atomic updates.
"""

import json
import time
import threading
from typing import Any
from dataclasses import dataclass, asdict
import sqlite3
import os
from pathlib import Path

# Placeholder för Redis - i en riktig implementation skulle vi använda redis-py
try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None  # type: ignore

import logging

logger = logging.getLogger(__name__)


@dataclass
class ConfigValue:
    """En konfigurationsvärde med metadata."""

    key: str
    value: Any
    source: str
    generation: int
    created_at: float
    updated_at: float
    user: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Konvertera till dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ConfigValue':
        """Skapa från dictionary."""
        return cls(**data)


class ConfigStore:
    """
    Central store för konfigurationsvärden med DB/Redis backend och kluster-konsistens.
    """

    def __init__(self, db_path: str = "config_store.db", redis_url: str | None = None):
        """
        Initiera config store.

        Args:
            db_path: Sökväg till SQLite-databas
            redis_url: Redis URL (optional)
        """
        self.db_path = db_path
        self.redis_url = redis_url
        self.redis_client = None
        self.pubsub = None
        self._lock = threading.RLock()
        self._generation = 0
        self._subscribers: set[str] = set()
        self._pending_updates: dict[str, Any] = {}  # För atomic updates
        self._redis_channel = "config_updates"
        self._redis_subscription_thread = None

        # Initiera databas
        self._init_database()

        # Initiera Redis om tillgänglig
        if redis_url and REDIS_AVAILABLE:
            self._init_redis()

    def _init_database(self):
        """Initiera SQLite-databas."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS config_values (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    source TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    user TEXT
                )
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS config_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    source TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    user TEXT,
                    action TEXT NOT NULL
                )
            """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_config_generation ON config_values(generation)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_history_key ON config_history(key)")
            conn.commit()

    def _init_redis(self):
        """Initiera Redis-klient med pub/sub."""
        if not REDIS_AVAILABLE or not self.redis_url:
            return

        try:
            self.redis_client = redis.from_url(self.redis_url)
            self.redis_client.ping()  # Test connection

            # Sätt upp pub/sub
            self.pubsub = self.redis_client.pubsub()
            self.pubsub.subscribe(self._redis_channel)

            # Starta subscription thread
            self._start_redis_subscription()

            logger.info("Redis connection and pub/sub established")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}")
            self.redis_client = None

    def _get_next_generation(self) -> int:
        """Hämta nästa generationsnummer."""
        with self._lock:
            self._generation += 1
            return self._generation

    def _start_redis_subscription(self):
        """Starta Redis subscription thread för pub/sub."""
        if not self.pubsub or not REDIS_AVAILABLE:
            return

        def subscription_worker():
            try:
                for message in self.pubsub.listen():
                    if message['type'] == 'message':
                        self._handle_redis_message(message['data'])
            except Exception as e:
                logger.error(f"Redis subscription error: {e}")

        self._redis_subscription_thread = threading.Thread(target=subscription_worker, daemon=True)
        self._redis_subscription_thread.start()
        logger.info("Redis subscription thread started")

    def _handle_redis_message(self, data: bytes):
        """Hantera Redis pub/sub meddelanden."""
        try:
            import json

            message = json.loads(data.decode('utf-8'))

            if message.get('type') == 'config_update':
                # Hantera konfigurationsuppdatering från annan nod
                key = message.get('key')
                generation = message.get('generation')

                if key and generation > self._generation:
                    # Invalidera cache för denna nyckel
                    self._notify_cache_invalidation(key, generation)

        except Exception as e:
            logger.error(f"Error handling Redis message: {e}")

    def _publish_update(self, key: str, generation: int):
        """Publicera uppdatering till Redis channel."""
        if not self.redis_client or not REDIS_AVAILABLE:
            return

        try:
            import json

            message = {'type': 'config_update', 'key': key, 'generation': generation, 'timestamp': time.time()}

            self.redis_client.publish(self._redis_channel, json.dumps(message))
        except Exception as e:
            logger.error(f"Failed to publish Redis update: {e}")

    def _notify_cache_invalidation(self, key: str, generation: int):
        """Notifiera om cache invalidation."""
        # Detta kommer att anropas av cache-klassen
        pass

    def set(self, key: str, value: Any, source: str, user: str | None = None) -> ConfigValue:
        """
        Sätt konfigurationsvärde med atomic update.

        Args:
            key: Konfigurationsnyckel
            value: Värde att sätta
            source: Källa för värdet
            user: Användare som gjorde ändringen

        Returns:
            ConfigValue som skapades
        """
        generation = self._get_next_generation()
        now = time.time()

        config_value = ConfigValue(
            key=key, value=value, source=source, generation=generation, created_at=now, updated_at=now, user=user
        )

        with self._lock:
            # Sätt i SQLite
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO config_values
                    (key, value, source, generation, created_at, updated_at, user)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        key,
                        json.dumps(value),
                        source,
                        generation,
                        config_value.created_at,
                        config_value.updated_at,
                        user,
                    ),
                )

                # Logga till historik
                conn.execute(
                    """
                    INSERT INTO config_history
                    (key, value, source, generation, created_at, user, action)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (key, json.dumps(value), source, generation, now, user, "SET"),
                )
                conn.commit()

            # Sätt i Redis om tillgänglig
            if self.redis_client:
                try:
                    self.redis_client.hset("config:values", key, json.dumps(config_value.to_dict()))
                    self.redis_client.set(f"config:generation", generation)

                    # Pub/Sub för cache invalidation
                    self._publish_update(key, generation)
                except Exception as e:
                    print(f"Warning: Redis operation failed: {e}")

        return config_value

    def get(self, key: str) -> ConfigValue | None:
        """
        Hämta konfigurationsvärde.

        Args:
            key: Konfigurationsnyckel att hämta

        Returns:
            ConfigValue om hittat, None annars
        """
        # Försök Redis först om tillgänglig
        if self.redis_client:
            try:
                value_json = self.redis_client.hget("config:values", key)
                if value_json:
                    data = json.loads(value_json)
                    return ConfigValue.from_dict(data)
            except Exception as e:
                print(f"Warning: Redis get failed: {e}")

        # Fallback till SQLite
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT key, value, source, generation, created_at, updated_at, user
                FROM config_values WHERE key = ?
            """,
                (key,),
            )

            row = cursor.fetchone()
            if row:
                return ConfigValue(
                    key=row[0],
                    value=json.loads(row[1]),
                    source=row[2],
                    generation=row[3],
                    created_at=row[4],
                    updated_at=row[5],
                    user=row[6],
                )

        return None

    def get_all(self) -> dict[str, ConfigValue]:
        """
        Hämta alla konfigurationsvärden.

        Returns:
            Dictionary med alla konfigurationsvärden
        """
        # Försök Redis först om tillgänglig
        if self.redis_client:
            try:
                values = self.redis_client.hgetall("config:values")
                result = {}
                for key, value_json in values.items():
                    data = json.loads(value_json)
                    result[key] = ConfigValue.from_dict(data)
                return result
            except Exception as e:
                print(f"Warning: Redis get_all failed: {e}")

        # Fallback till SQLite
        result = {}
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT key, value, source, generation, created_at, updated_at, user
                FROM config_values
            """
            )

            for row in cursor.fetchall():
                result[row[0]] = ConfigValue(
                    key=row[0],
                    value=json.loads(row[1]),
                    source=row[2],
                    generation=row[3],
                    created_at=row[4],
                    updated_at=row[5],
                    user=row[6],
                )

        return result

    def delete(self, key: str, user: str | None = None) -> bool:
        """
        Ta bort konfigurationsvärde.

        Args:
            key: Konfigurationsnyckel att ta bort
            user: Användare som gjorde ändringen

        Returns:
            True om borttaget, False om inte hittat
        """
        now = time.time()

        with self._lock:
            # Ta bort från SQLite
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("DELETE FROM config_values WHERE key = ?", (key,))
                if cursor.rowcount > 0:
                    # Logga till historik
                    conn.execute(
                        """
                        INSERT INTO config_history
                        (key, value, source, generation, created_at, user, action)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                        (key, json.dumps(None), "deleted", 0, now, user, "DELETE"),
                    )
                    conn.commit()

            # Ta bort från Redis om tillgänglig
            if self.redis_client:
                try:
                    self.redis_client.hdel("config:values", key)
                    generation = self._get_next_generation()
                    self.redis_client.set(f"config:generation", generation)

                    # Pub/Sub för cache invalidation
                    self.redis_client.publish(
                        "config:changes",
                        json.dumps({"key": key, "generation": generation, "action": "DELETE", "timestamp": now}),
                    )
                except Exception as e:
                    print(f"Warning: Redis delete failed: {e}")

            return cursor.rowcount > 0

    def get_history(self, key: str, limit: int = 100) -> list[ConfigValue]:
        """
        Hämta historik för en konfigurationsnyckel.

        Args:
            key: Konfigurationsnyckel
            limit: Max antal poster att returnera

        Returns:
            Lista med historiska värden
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT key, value, source, generation, created_at, user, action
                FROM config_history
                WHERE key = ?
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (key, limit),
            )

            result = []
            for row in cursor.fetchall():
                result.append(
                    ConfigValue(
                        key=row[0],
                        value=json.loads(row[1]) if row[1] != 'null' else None,
                        source=row[2],
                        generation=row[3],
                        created_at=row[4],
                        updated_at=row[4],  # Historik har bara created_at
                        user=row[5],
                    )
                )

            return result

    def get_current_generation(self) -> int:
        """Hämta aktuellt generationsnummer."""
        if self.redis_client:
            try:
                return int(self.redis_client.get("config:generation") or 0)
            except Exception:
                pass

        # Fallback till SQLite
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT MAX(generation) FROM config_values")
            row = cursor.fetchone()
            return row[0] or 0

    def subscribe_to_changes(self, callback):
        """
        Prenumerera på konfigurationsändringar (Redis pub/sub).

        Args:
            callback: Funktion som anropas vid ändringar
        """
        if not self.redis_client:
            return

        try:
            pubsub = self.redis_client.pubsub()
            pubsub.subscribe("config:changes")

            for message in pubsub.listen():
                if message['type'] == 'message':
                    data = json.loads(message['data'])
                    callback(data)
        except Exception as e:
            print(f"Warning: Redis subscription failed: {e}")

    def get_stats(self) -> dict[str, Any]:
        """
        Hämta store-statistik.

        Returns:
            Dictionary med statistik
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM config_values")
            total_configs = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM config_history")
            total_history = cursor.fetchone()[0]

            cursor = conn.execute("SELECT MAX(generation) FROM config_values")
            max_generation = cursor.fetchone()[0] or 0

        return {
            "total_configs": total_configs,
            "total_history": total_history,
            "current_generation": max_generation,
            "redis_available": self.redis_client is not None,
            "db_path": self.db_path,
        }

    def get_store_stats(self) -> dict[str, Any]:
        """Alias för get_stats för kompatibilitet med tester."""
        return self.get_stats()

    def batch_set(self, updates: dict[str, Any], source: str, user: str | None = None) -> dict[str, ConfigValue]:
        """
        Atomic batch update av flera konfigurationsvärden.

        Args:
            updates: Dictionary med nycklar och värden att uppdatera
            source: Källa för uppdateringarna
            user: Användare som gjorde ändringarna

        Returns:
            Dictionary med uppdaterade ConfigValue-objekt
        """
        if not updates:
            return {}

        generation = self._get_next_generation()
        now = time.time()
        results = {}

        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    # Börja transaktion
                    conn.execute("BEGIN TRANSACTION")

                    for key, value in updates.items():
                        config_value = ConfigValue(
                            key=key,
                            value=value,
                            source=source,
                            generation=generation,
                            created_at=now,
                            updated_at=now,
                            user=user,
                        )

                        # Sätt i SQLite
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO config_values
                            (key, value, source, generation, created_at, updated_at, user)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                key,
                                json.dumps(value),
                                source,
                                generation,
                                config_value.created_at,
                                config_value.updated_at,
                                user,
                            ),
                        )

                        # Logga till historik
                        conn.execute(
                            """
                            INSERT INTO config_history
                            (key, value, source, generation, created_at, user, action)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                            (key, json.dumps(value), source, generation, now, user, "BATCH_SET"),
                        )

                        results[key] = config_value

                    # Committa transaktion
                    conn.commit()

                # Sätt i Redis om tillgängligt
                if self.redis_client:
                    try:
                        # Batch update i Redis
                        pipe = self.redis_client.pipeline()
                        for key, config_value in results.items():
                            pipe.hset("config:values", key, json.dumps(config_value.to_dict()))
                        pipe.set(f"config:generation", generation)
                        pipe.execute()

                        # Publicera batch uppdatering
                        self._publish_batch_update(list(results.keys()), generation)

                    except Exception as e:
                        logger.warning(f"Failed Redis batch update: {e}")

            except Exception as e:
                logger.error(f"Failed batch atomic update: {e}")
                raise

        return results

    def _publish_batch_update(self, keys: list[str], generation: int):
        """Publicera batch uppdatering till Redis channel."""
        if not self.redis_client:
            return

        try:
            import json

            message = {'type': 'config_batch_update', 'keys': keys, 'generation': generation, 'timestamp': time.time()}

            self.redis_client.publish(self._redis_channel, json.dumps(message))
        except Exception as e:
            logger.error(f"Failed to publish Redis batch update: {e}")

    def atomic_compare_and_set(
        self, key: str, expected_value: Any, new_value: Any, source: str, user: str | None = None
    ) -> bool:
        """
        Atomic compare-and-set operation.

        Args:
            key: Konfigurationsnyckel
            expected_value: Förväntat värde (None för "inte satt")
            new_value: Nya värdet att sätta
            source: Källa för ändringen
            user: Användare som gjorde ändringen

        Returns:
            True om operationen lyckades, False annars
        """
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    # Börja transaktion
                    conn.execute("BEGIN TRANSACTION")

                    # Hämta aktuellt värde
                    cursor = conn.execute("SELECT value FROM config_values WHERE key = ?", (key,))
                    row = cursor.fetchone()
                    current_value = json.loads(row[0]) if row and row[0] else None

                    # Kontrollera om förväntat värde stämmer
                    if current_value != expected_value:
                        conn.execute("ROLLBACK")
                        return False

                    # Sätt nya värdet
                    generation = self._get_next_generation()
                    now = time.time()

                    config_value = ConfigValue(
                        key=key,
                        value=new_value,
                        source=source,
                        generation=generation,
                        created_at=now,
                        updated_at=now,
                        user=user,
                    )

                    # Sätt i SQLite
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO config_values
                        (key, value, source, generation, created_at, updated_at, user)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            key,
                            json.dumps(new_value),
                            source,
                            generation,
                            config_value.created_at,
                            config_value.updated_at,
                            user,
                        ),
                    )

                    # Logga till historik
                    conn.execute(
                        """
                        INSERT INTO config_history
                        (key, value, source, generation, created_at, user, action)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                        (key, json.dumps(new_value), source, generation, now, user, "COMPARE_AND_SET"),
                    )

                    # Committa transaktion
                    conn.commit()

                # Sätt i Redis om tillgängligt
                if self.redis_client:
                    try:
                        self.redis_client.hset("config:values", key, json.dumps(config_value.to_dict()))
                        self.redis_client.set(f"config:generation", generation)

                        # Publicera uppdatering
                        self._publish_update(key, generation)

                    except Exception as e:
                        logger.warning(f"Failed Redis CAS update: {e}")

                return True

            except Exception as e:
                logger.error(f"Failed compare-and-set for key {key}: {e}")
                return False
