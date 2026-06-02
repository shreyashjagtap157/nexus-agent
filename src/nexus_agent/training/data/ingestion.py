"""WAL-enabled SQLite database for high-performance training data ingestion.

Provides thread-safe, WAL-mode SQLite connections with relational schema
tracking sample IDs, datasets, categories, token counts, and processing statuses.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_uid TEXT UNIQUE NOT NULL,
    dataset_name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'pretrain',
    content TEXT NOT NULL,
    token_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'unprocessed',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    metadata TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_samples_category ON samples(category);
CREATE INDEX IF NOT EXISTS idx_samples_status ON samples(status);
CREATE INDEX IF NOT EXISTS idx_samples_dataset ON samples(dataset_name);
CREATE INDEX IF NOT EXISTS idx_samples_token_count ON samples(token_count);
CREATE INDEX IF NOT EXISTS idx_samples_created_at ON samples(created_at);
"""


class WALDatabase:
    """Thread-safe SQLite database with WAL mode for concurrent reads/writes.

    Args:
        db_path: Path to the SQLite database file.
        max_retries: Maximum number of retries on lock contention.
    """

    def __init__(self, db_path: str | Path, max_retries: int = 10):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._max_retries = max_retries
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database with WAL mode and schema."""
        self._conn = sqlite3.connect(
            str(self._path),
            check_same_thread=False,
            timeout=30.0,
        )
        self._conn.row_factory = sqlite3.Row
        # Enable WAL mode for concurrent reads/writes
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        self._conn.execute("PRAGMA busy_timeout=10000")
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()
        logger.info(f"Initialized WAL database at {self._path}")

    @property
    def connection(self) -> sqlite3.Connection:
        """Get the database connection."""
        if self._conn is None:
            raise RuntimeError("Database not initialized")
        return self._conn

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a query with retry logic for lock contention."""
        for attempt in range(self._max_retries):
            try:
                with self._lock:
                    cursor = self._conn.execute(query, params)
                    return cursor
            except sqlite3.OperationalError as e:
                if "locked" in str(e) and attempt < self._max_retries - 1:
                    time.sleep(0.01 * (attempt + 1))
                    continue
                raise
        raise RuntimeError("Database locked after max retries")

    def executemany(self, query: str, params_list: list[tuple]) -> sqlite3.Cursor:
        """Execute a query with multiple parameter sets."""
        for attempt in range(self._max_retries):
            try:
                with self._lock:
                    cursor = self._conn.executemany(query, params_list)
                    return cursor
            except sqlite3.OperationalError as e:
                if "locked" in str(e) and attempt < self._max_retries - 1:
                    time.sleep(0.01 * (attempt + 1))
                    continue
                raise
        raise RuntimeError("Database locked after max retries")

    def commit(self) -> None:
        """Commit the current transaction."""
        with self._lock:
            self._conn.commit()

    def vacuum(self) -> None:
        """Reclaim database space."""
        with self._lock:
            self._conn.execute("VACUUM")

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> WALDatabase:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
