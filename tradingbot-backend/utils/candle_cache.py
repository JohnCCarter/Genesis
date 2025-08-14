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
                    PRIMARY KEY (symbol, timeframe, mts)
                ) WITHOUT ROWID
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_candles_symbol_tf_mts "
                "ON candles(symbol, timeframe, mts)"
            )
            conn.commit()

    def store(self, symbol: str, timeframe: str, candles: Iterable[list]) -> int:
        """Spara candles i cache. Returnerar antal upserts."""
        count = 0
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
                    INSERT INTO candles(symbol, timeframe, mts, open, close, high, low, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol, timeframe, mts) DO UPDATE SET
                        open=excluded.open,
                        close=excluded.close,
                        high=excluded.high,
                        low=excluded.low,
                        volume=excluded.volume
                    """,
                    (symbol, timeframe, mts, o, cl, hi, lo, vol),
                )
                count += 1
            conn.commit()
        return count

    def load(self, symbol: str, timeframe: str, limit: int = 100) -> list[list]:
        """
        Läs senaste N candles från cache.
        Returnerar Bitfinex-format, nyast -> äldst, som i API.
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute(
                """
                SELECT mts, open, close, high, low, volume
                FROM candles
                WHERE symbol=? AND timeframe=?
                ORDER BY mts DESC
                LIMIT ?
                """,
                (symbol, timeframe, int(limit)),
            ).fetchall()
        return [[r[0], r[1], r[2], r[3], r[4], r[5]] for r in rows]

    def get_last(self, symbol: str, timeframe: str) -> list | None:
        """
        Returnera senaste candle i Bitfinex-format.
        Format: [MTS, OPEN, CLOSE, HIGH, LOW, VOLUME].
        """
        rows = self.load(symbol, timeframe, limit=1)
        if rows:
            return rows[0]
        return None

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
        with closing(sqlite3.connect(self.db_path)) as conn:
            cur = conn.execute("DELETE FROM candles")
            conn.commit()
            return cur.rowcount if cur.rowcount is not None else 0

    def clear(self, symbol: str, timeframe: str | None = None) -> int:
        with closing(sqlite3.connect(self.db_path)) as conn:
            if timeframe:
                cur = conn.execute(
                    "DELETE FROM candles WHERE symbol=? AND timeframe=?",
                    (symbol, timeframe),
                )
            else:
                cur = conn.execute(
                    "DELETE FROM candles WHERE symbol=?",
                    (symbol,),
                )
            conn.commit()
            return cur.rowcount if cur.rowcount is not None else 0

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


candle_cache = CandleCache()
