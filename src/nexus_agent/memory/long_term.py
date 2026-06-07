"""
Long-Term Memory — SQLite-backed persistent memory with FTS5 full-text search.

Inspired by hermes agent's FTS5 memory system. Stores learned patterns,
code conventions, architecture decisions, and other persistent knowledge.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from typing import Any

from nexus_agent.core.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


class LongTermMemory(SQLiteStore):
    """SQLite-backed long-term memory with full-text search.

    Uses SQLite FTS5 for fast keyword-based search across stored
    memories, without requiring external vector databases.
    """

    SCHEMA_SQL = """
        CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    metadata TEXT DEFAULT '{}',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    access_count INTEGER DEFAULT 0
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    content,
                    category,
                    content='memories',
                    content_rowid='rowid'
                );

                -- Triggers to keep FTS in sync
                CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, content, category)
                    VALUES (new.rowid, new.content, new.category);
                END;

                CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content, category)
                    VALUES ('delete', old.rowid, old.content, old.category);
                END;

                CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content, category)
                    VALUES ('delete', old.rowid, old.content, old.category);
                    INSERT INTO memories_fts(rowid, content, category)
                    VALUES (new.rowid, new.content, new.category);
                END;

                CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
                CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);
            """

    def store(self, content: str, category: str = "general",
              metadata: dict[str, Any] | None = None) -> str:
        """Store a memory entry.

        Args:
            content: The information to remember.
            category: Category (e.g., 'code_pattern', 'architecture', 'preference').
            metadata: Additional metadata.

        Returns:
            The memory entry ID.

        Raises:
            ValueError: If content is empty or whitespace-only.
        """
        if not content or not content.strip():
            raise ValueError("Memory content must not be empty")
        with self._lock:
            entry_id = uuid.uuid4().hex
            now = time.time()

            conn = self._get_conn()
            conn.execute(
                "INSERT INTO memories (id, content, category, metadata, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (entry_id, content, category, json.dumps(metadata or {}), now, now),
            )
            conn.commit()

            logger.debug("Stored memory [%s]: %.80s...", category, content)
            return entry_id

    def _sanitize_query(self, query: str) -> str:
        """Sanitize search query for safe FTS5 MATCH queries."""
        terms = []
        for term in query.split():
            clean_term = term.replace('"', '').replace("'", "''")
            if clean_term:
                terms.append(f'"{clean_term}"')
        return " AND ".join(terms) if terms else ""

    def search(self, query: str, category: str | None = None,
               limit: int = 10) -> list[dict[str, Any]]:
        """Search memories using FTS5 full-text search.

        Args:
            query: Search query.
            category: Filter by category.
            limit: Maximum results.

        Returns:
            List of matching memory entries with relevance scores.
        """
        with self._lock:
            conn = self._get_conn()

            # Build FTS5 query
            # Escape special FTS5 characters and sanitize query safely
            safe_query = self._sanitize_query(query)

            try:
                if category:
                    cursor = conn.execute(
                        """
                        SELECT m.*, rank
                        FROM memories_fts fts
                        JOIN memories m ON m.rowid = fts.rowid
                        WHERE memories_fts MATCH ?
                        AND m.category = ?
                        ORDER BY rank
                        LIMIT ?
                        """,
                        (safe_query, category, limit),
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT m.*, rank
                        FROM memories_fts fts
                        JOIN memories m ON m.rowid = fts.rowid
                        WHERE memories_fts MATCH ?
                        ORDER BY rank
                        LIMIT ?
                        """,
                        (safe_query, limit),
                    )
            except sqlite3.OperationalError:
                # FTS query syntax error — fall back to LIKE
                escaped = query.replace('%', '\\%').replace('_', '\\_')
                like_query = f"%{escaped}%"
                if category:
                    cursor = conn.execute(
                        "SELECT *, 0 as rank FROM memories WHERE content LIKE ? ESCAPE '\\' AND category = ? LIMIT ?",
                        (like_query, category, limit),
                    )
                else:
                    cursor = conn.execute(
                        "SELECT *, 0 as rank FROM memories WHERE content LIKE ? ESCAPE '\\' LIMIT ?",
                        (like_query, limit),
                    )

            results = []
            for row in cursor:
                entry = dict(row)
                entry["score"] = -entry.get("rank", 0)
                if "metadata" in entry:
                    try:
                        entry["metadata"] = json.loads(entry["metadata"])
                    except json.JSONDecodeError:
                        entry["metadata"] = {}
                results.append(entry)

            # Update access counts
            for r in results:
                conn.execute(
                    "UPDATE memories SET access_count = access_count + 1 WHERE id = ?",
                    (r["id"],),
                )
            conn.commit()

            return results

    def get(self, entry_id: str) -> dict[str, Any] | None:
        """Get a specific memory by ID."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("SELECT * FROM memories WHERE id = ?", (entry_id,))
            row = cursor.fetchone()
            if row:
                entry = dict(row)
                entry["metadata"] = json.loads(entry.get("metadata", "{}"))
                return entry
            return None

    def update(self, entry_id: str, content: str | None = None,
               category: str | None = None) -> bool:
        """Update an existing memory entry."""
        with self._lock:
            conn = self._get_conn()
            updates: list[str] = []
            params: list[Any] = []

            if content is not None:
                updates.append("content = ?")
                params.append(content)
            if category is not None:
                updates.append("category = ?")
                params.append(category)

            if not updates:
                return False

            updates.append("updated_at = ?")
            params.append(time.time())
            params.append(entry_id)

            cursor = conn.execute(
                f"UPDATE memories SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete(self, entry_id: str) -> bool:
        """Delete a memory entry."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (entry_id,))
            conn.commit()
            return cursor.rowcount > 0

    def list_categories(self) -> list[dict[str, Any]]:
        """List all memory categories with counts."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT category, COUNT(*) as count FROM memories GROUP BY category ORDER BY count DESC"
            )
            return [dict(row) for row in cursor]

    def list_all(self, category: str | None = None, limit: int = 100,
                 offset: int = 0) -> list[dict[str, Any]]:
        """Enumerate memories, newest first.

        Args:
            category: Optional category filter.
            limit: Maximum entries to return (default 100).
            offset: Skip this many entries (for pagination).

        Returns:
            List of memory entries (newest first).
        """
        with self._lock:
            conn = self._get_conn()
            if category:
                cursor = conn.execute(
                    "SELECT * FROM memories WHERE category = ? "
                    "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (category, limit, offset),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM memories ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            results: list[dict[str, Any]] = []
            for row in cursor:
                entry = dict(row)
                try:
                    entry["metadata"] = json.loads(entry.get("metadata", "{}"))
                except (TypeError, json.JSONDecodeError):
                    entry["metadata"] = {}
                results.append(entry)
            return results

    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("SELECT COUNT(*) as total FROM memories")
            row = cursor.fetchone()
            total = row["total"] if row else 0

            cursor = conn.execute("SELECT COUNT(DISTINCT category) as categories FROM memories")
            row = cursor.fetchone()
            categories = row["categories"] if row else 0

            return {
                "total_entries": total,
                "categories": categories,
                "db_path": str(self.db_path),
            }


