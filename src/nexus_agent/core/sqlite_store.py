"""Base class for SQLite-backed storage with threading safety.

Thread safety: subclasses must ensure all public methods acquire self._lock
before accessing the database connection. Each connection is single-threaded.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


class SQLiteStore:
    """Thread-safe base for SQLite-backed stores.

    Subclasses must define SCHEMA_SQL (str) and may override _init_db.
    """

    SCHEMA_SQL: str = ""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self) -> None:
        if self.SCHEMA_SQL:
            with self._lock:
                conn = self._get_conn()
                conn.executescript(self.SCHEMA_SQL)

    def close(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
