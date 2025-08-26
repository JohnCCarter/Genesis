import os
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from datetime import datetime, timedelta
from typing import Dict, List, Optional

_DB_DEFAULT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "candles.sqlite3")


class CandleCache:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or _DB_DEFAULT
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            # Skapa tabellen om den inte finns
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS candles (
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    mts INTEGER NOT NULL,
                    open REAL NOT NULL,
                    close REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    volume REAL NOT NULL,
                    cached_at INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (symbol, timeframe, mts)
                ) WITHOUT ROWID
                """
            )

            # Migration: Lägg till cached_at kolumn om den inte finns
            try:
                conn.execute("ALTER TABLE candles ADD COLUMN cached_at INTEGER NOT NULL DEFAULT 0")
                print("✅ Migrerade candle cache databas: lade till cached_at kolumn")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print("ℹ️ cached_at kolumn finns redan")
                else:
                    print(f"ℹ️ Migration noter: {e}")

            # Skapa index
            conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_candles_symbol_tf_mts "
                "ON candles(symbol, timeframe, mts)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS ix_candles_cached_at " "ON candles(cached_at)")
            conn.commit()

    def store(self, symbol: str, timeframe: str, candles: Iterable[list]) -> int:
        """Spara candles i cache. Returnerar antal upserts."""
        count = 0
        cached_at = int(datetime.now().timestamp())
        with closing(sqlite3.connect(self.db_path)) as conn:
            cur = conn.cursor()
            for c in candles:
                # Bitfinex: [MTS, OPEN, CLOSE, HIGH, LOW, VOLUME]
                try:
                    mts, o, cl, hi, lo, vol = (
                        int(c[0]),
                        float(c[1]),
                        float(c[2]),
                        float(c[3]),
                        float(c[4]),
                        float(c[5]),
                    )
                except Exception:
                    continue
                cur.execute(
                    """
                    INSERT INTO candles(symbol, timeframe, mts, open, close, high, low, volume, cached_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol, timeframe, mts) DO UPDATE SET
                        open=excluded.open,
                        close=excluded.close,
                        high=excluded.high,
                        low=excluded.low,
                        volume=excluded.volume,
                        cached_at=excluded.cached_at
                    """,
                    (symbol, timeframe, mts, o, cl, hi, lo, vol, cached_at),
                )
                count += 1
            conn.commit()
        return count

    def load(
        self, symbol: str, timeframe: str, limit: int = 100, max_age_minutes: int = 15
    ) -> list[list]:
        """
        Läs senaste N candles från cache.
        Returnerar Bitfinex-format, nyast -> äldst, som i API.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe (1m, 5m, etc.)
            limit: Max antal candles att returnera
            max_age_minutes: Max ålder för cached data i minuter (ökad från 5 till 15)
        """
        cutoff_time = int((datetime.now() - timedelta(minutes=max_age_minutes)).timestamp())

        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute(
                """
                SELECT mts, open, close, high, low, volume
                FROM candles
                WHERE symbol=? AND timeframe=? AND cached_at >= ?
                ORDER BY mts DESC
                LIMIT ?
                """,
                (symbol, timeframe, cutoff_time, int(limit)),
            ).fetchall()
        return [[r[0], r[1], r[2], r[3], r[4], r[5]] for r in rows]

    def get_last(self, symbol: str, timeframe: str, max_age_minutes: int = 15) -> list | None:
        """
        Returnera senaste candle i Bitfinex-format.
        Format: [MTS, OPEN, CLOSE, HIGH, LOW, VOLUME].

        Args:
            symbol: Trading symbol
            timeframe: Timeframe (1m, 5m, etc.)
            max_age_minutes: Max ålder för cached data i minuter (ökad från 5 till 15)
        """
        rows = self.load(symbol, timeframe, limit=1, max_age_minutes=max_age_minutes)
        if rows:
            return rows[0]
        return None

    def clear_old_data(self, max_age_hours: int = 24) -> int:
        """Rensa gammal cached data. Returnerar antal rader som togs bort."""
        cutoff_time = int((datetime.now() - timedelta(hours=max_age_hours)).timestamp())

        with closing(sqlite3.connect(self.db_path)) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM candles WHERE cached_at < ?", (cutoff_time,))
            deleted_count = cur.rowcount
            conn.commit()
        return deleted_count

    def clear_symbol(self, symbol: str, timeframe: str | None = None) -> int:
        """Rensa cached data för en specifik symbol. Returnerar antal rader som togs bort."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cur = conn.cursor()
            if timeframe:
                cur.execute(
                    "DELETE FROM candles WHERE symbol = ? AND timeframe = ?", (symbol, timeframe)
                )
            else:
                cur.execute("DELETE FROM candles WHERE symbol = ?", (symbol,))
            deleted_count = cur.rowcount
            conn.commit()
        return deleted_count

    def stats(self, limit_symbols: int = 20) -> dict:
        """Returnera enkel statistik över cacheinnehållet."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            total_rows = conn.execute("SELECT COUNT(*) FROM candles").fetchone()[0]
            rows_by_pair = conn.execute(
                """
                SELECT symbol, timeframe, COUNT(*) as n
                FROM candles
                GROUP BY symbol, timeframe
                ORDER BY n DESC
                LIMIT ?
                """,
                (int(limit_symbols),),
            ).fetchall()
        items = [
            {
                "symbol": r[0],
                "timeframe": r[1],
                "rows": int(r[2]),
            }
            for r in rows_by_pair
        ]
        return {"total_rows": int(total_rows), "top": items}

    def clear_all(self) -> int:
        """Rensa all cached data. Returnerar antal rader som togs bort."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM candles")
            deleted_count = cur.rowcount
            conn.commit()
        return deleted_count

    def clear(self, symbol: str, timeframe: str | None = None) -> int:
        """Rensa cached data för en specifik symbol. Returnerar antal rader som togs bort."""
        return self.clear_symbol(symbol, timeframe)

    def enforce_retention(self, max_days: int, max_rows_per_pair: int) -> int:
        """Ta bort gamla rader och begränsa per symbol/timeframe."""
        removed = 0
        with closing(sqlite3.connect(self.db_path)) as conn:
            # 1) Rensa äldre än max_days
            if max_days and max_days > 0:
                cutoff = int((datetime.utcnow() - timedelta(days=max_days)).timestamp() * 1000)
                cur = conn.execute(
                    "DELETE FROM candles WHERE mts < ?",
                    (cutoff,),
                )
                removed += cur.rowcount or 0
            # 2) Begränsa max_rows_per_pair
            if max_rows_per_pair and max_rows_per_pair > 0:
                # Hitta par som överskrider gränsen
                rows = conn.execute(
                    """
                    SELECT symbol, timeframe, COUNT(*) as n
                    FROM candles
                    GROUP BY symbol, timeframe
                    HAVING n > ?
                    """,
                    (int(max_rows_per_pair),),
                ).fetchall()
                for symbol, timeframe, n in rows:
                    # Ta bort äldsta raderna över gränsen
                    to_delete = int(n - max_rows_per_pair)
                    conn.execute(
                        """
                        DELETE FROM candles
                        WHERE rowid IN (
                            SELECT rowid FROM candles
                            WHERE symbol=? AND timeframe=?
                            ORDER BY mts ASC
                            LIMIT ?
                        )
                        """,
                        (symbol, timeframe, to_delete),
                    )
                    removed += to_delete
            conn.commit()
        return removed


# Global instans
candle_cache = CandleCache()
