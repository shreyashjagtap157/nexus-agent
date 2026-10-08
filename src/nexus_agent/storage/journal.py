"""Durable audit journal for NexusAgent file mutations."""
from __future__ import annotations

import hashlib
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


class FileJournal:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS file_changes (
        change_id TEXT PRIMARY KEY,
        operation TEXT NOT NULL,
        path TEXT NOT NULL,
        previous_hash TEXT,
        new_hash TEXT,
        actor TEXT NOT NULL DEFAULT 'agent',
        details_json TEXT NOT NULL DEFAULT '{}',
        created_at REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_file_changes_path_time
    ON file_changes(path, created_at);
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), timeout=30)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=30000")
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()

    @staticmethod
    def digest_file(path: Path) -> str | None:
        try:
            data = path.read_bytes()
        except (OSError, ValueError):
            return None
        return hashlib.sha256(data).hexdigest()

    def record(
        self,
        operation: str,
        path: str,
        previous_hash: str | None = None,
        new_hash: str | None = None,
        actor: str = "agent",
        details: dict[str, Any] | None = None,
    ) -> str:
        change_id = uuid.uuid4().hex[:20]
        import json
        self._conn.execute(
            """INSERT INTO file_changes(
                change_id,operation,path,previous_hash,new_hash,actor,details_json,created_at
            ) VALUES(?,?,?,?,?,?,?,?)""",
            (
                change_id,
                operation,
                path,
                previous_hash,
                new_hash,
                actor,
                json.dumps(details or {}, ensure_ascii=False, default=str),
                time.time(),
            ),
        )
        self._conn.commit()
        return change_id

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT change_id,operation,path,previous_hash,new_hash,actor,details_json,created_at
               FROM file_changes ORDER BY created_at DESC LIMIT ?""",
            (max(1, min(int(limit), 5000)),),
        ).fetchall()
        import json
        return [
            {
                "change_id": row[0],
                "operation": row[1],
                "path": row[2],
                "previous_hash": row[3],
                "new_hash": row[4],
                "actor": row[5],
                "details": json.loads(row[6] or "{}"),
                "created_at": row[7],
            }
            for row in rows
        ]

    def close(self) -> None:
        self._conn.close()
