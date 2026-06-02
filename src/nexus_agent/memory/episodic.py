"""
Episodic Memory — Session and conversation history storage.

Stores summaries of past interactions for cross-session recall.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from typing import Any

from nexus_agent.core.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


class EpisodicMemory(SQLiteStore):
    """SQLite-backed episodic memory for session history."""

    SCHEMA_SQL = """
        CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    messages_count INTEGER DEFAULT 0,
                    metadata TEXT DEFAULT '{}',
                    created_at REAL NOT NULL
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts USING fts5(
                    summary,
                    content='episodes',
                    content_rowid='id'
                );

                CREATE TRIGGER IF NOT EXISTS episodes_ai AFTER INSERT ON episodes BEGIN
                    INSERT INTO episodes_fts(rowid, summary) VALUES (new.id, new.summary);
                END;

                CREATE TRIGGER IF NOT EXISTS episodes_ad AFTER DELETE ON episodes BEGIN
                    INSERT INTO episodes_fts(episodes_fts, rowid, summary)
                    VALUES ('delete', old.id, old.summary);
                END;

                CREATE INDEX IF NOT EXISTS idx_episodes_session ON episodes(session_id);
                CREATE INDEX IF NOT EXISTS idx_episodes_created ON episodes(created_at);
            """

    def save_session(self, session_id: str, summary: str,
                     messages_count: int = 0,
                     metadata: dict[str, Any] | None = None) -> None:
        """Save a session summary."""
        if not session_id or not summary:
            return
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO episodes (session_id, summary, messages_count, metadata, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, summary, max(0, messages_count), json.dumps(metadata or {}), time.time()),
            )
            conn.commit()

    def _sanitize_query(self, query: str) -> str:
        """Sanitize search query for safe FTS5 MATCH queries."""
        terms = []
        for term in query.split():
            clean_term = term.replace('"', '').replace("'", "''")
            if clean_term:
                terms.append(f'"{clean_term}"')
        return " AND ".join(terms) if terms else ""

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search episodic memory."""
        if not query:
            return []
        with self._lock:
            conn = self._get_conn()
            safe_query = self._sanitize_query(query)

            try:
                cursor = conn.execute(
                    """
                    SELECT e.*, rank
                    FROM episodes_fts fts
                    JOIN episodes e ON e.id = fts.rowid
                    WHERE episodes_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (safe_query, limit),
                )
            except sqlite3.OperationalError:
                escaped = query.replace('%', '\\%').replace('_', '\\_')
                cursor = conn.execute(
                    "SELECT *, 0 as rank FROM episodes WHERE summary LIKE ? ESCAPE '\\' LIMIT ?",
                    (f"%{escaped}%", limit),
                )

            results = []
            for row in cursor:
                entry = dict(row)
                entry["content"] = entry.pop("summary", "") or ""
                entry["score"] = entry.get("rank", 0)
                results.append(entry)

            return results

    def get_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent session summaries."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT * FROM episodes ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor]


