"""Vector Store — SQLite-backed semantic memory with vector embeddings.

Stores embedding vectors as serialised BLOBs in a dedicated SQLite
database alongside the existing ``LongTermMemory`` FTS5 store.
Provides ``search()`` via in-memory cosine similarity — no external
vector-database extension required.
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
import struct
import threading
import time
from pathlib import Path
from typing import Any

from nexus_agent.core.sqlite_store import SQLiteStore
from nexus_agent.memory.vector_embedding import EmbeddingEngine, cosine_similarity

logger = logging.getLogger(__name__)


class VectorStore(SQLiteStore):
    """SQLite-backed vector store for embedding-based semantic search.

    Each entry stores:
    - ``entry_id`` — matching the ``LongTermMemory.memories.id``
    - ``content`` — original text (denormalised for display / debugging)
    - ``embedding`` — 384-dimensional float vector packed as BLOB
    - ``category`` — category label
    - ``updated_at`` — timestamp

    Search: compute the query embedding, load *all* stored embeddings
    into memory, score each with cosine similarity, return top-k.
    Since the stored memory count is typically small (hundreds, not
    millions), the full-scan approach is fast and avoids any external
    vector-index dependency.
    """

    SCHEMA_SQL = """
        CREATE TABLE IF NOT EXISTS embeddings (
            entry_id  TEXT PRIMARY KEY,
            content   TEXT NOT NULL DEFAULT '',
            embedding BLOB NOT NULL,
            category  TEXT DEFAULT 'general',
            updated_at REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_embeddings_category
            ON embeddings(category);
    """

    def __init__(
        self,
        db_path: str | Path,
        embedding_engine: EmbeddingEngine | None = None,
    ):
        self._engine = embedding_engine or EmbeddingEngine()
        self._dimensions = self._engine.dimensions
        super().__init__(db_path)

    # ── Public API ───────────────────────────────────────────────────

    def store(
        self,
        entry_id: str,
        content: str,
        category: str = "general",
    ) -> None:
        """Generate an embedding for *content* and persist it.

        If *content* is empty the call is a no-op.
        """
        if not content or not content.strip():
            return

        vec = self._engine.embed(content)
        blob = self._pack(vec)

        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """
                INSERT INTO embeddings (entry_id, content, embedding, category, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(entry_id) DO UPDATE SET
                    content   = excluded.content,
                    embedding = excluded.embedding,
                    category  = excluded.category,
                    updated_at = excluded.updated_at
                """,
                (entry_id, content, blob, category, time.time()),
            )
            conn.commit()

    def store_batch(
        self,
        entries: list[dict[str, Any]],
    ) -> None:
        """Batch-store multiple entries.

        Each dict must have keys ``entry_id``, ``content``, and
        optionally ``category``.
        """
        if not entries:
            return
        texts = [e["content"] for e in entries if e.get("content")]
        if not texts:
            return
        vectors = self._engine.embed_many(texts)

        with self._lock:
            conn = self._get_conn()
            now = time.time()
            for entry, vec in zip(entries, vectors):
                if not entry.get("content", "").strip():
                    continue
                conn.execute(
                    """
                    INSERT INTO embeddings (entry_id, content, embedding, category, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(entry_id) DO UPDATE SET
                        content   = excluded.content,
                        embedding = excluded.embedding,
                        category  = excluded.category,
                        updated_at = excluded.updated_at
                    """,
                    (
                        entry["entry_id"],
                        entry["content"],
                        self._pack(vec),
                        entry.get("category", "general"),
                        now,
                    ),
                )
            conn.commit()

    def search(
        self,
        query: str,
        limit: int = 10,
        min_score: float = 0.15,
    ) -> list[dict[str, Any]]:
        """Search memories by semantic similarity to *query*.

        Returns entries with a ``score`` field (0–1, higher = more
        similar), sorted descending.
        """
        if not query or not query.strip():
            return []

        query_vec = self._engine.embed(query)

        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT entry_id, content, embedding, category, updated_at FROM embeddings",
            )

            scored: list[tuple[float, dict[str, Any]]] = []
            for row in cursor:
                vec = self._unpack(row["embedding"])
                score = cosine_similarity(query_vec, vec)
                if score >= min_score:
                    scored.append((
                        score,
                        {
                            "id": row["entry_id"],
                            "content": row["content"],
                            "category": row["category"],
                            "source": "vector",
                            "score": score,
                            "updated_at": row["updated_at"],
                        },
                    ))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def delete(self, entry_id: str) -> bool:
        """Remove the embedding for *entry_id*.

        Returns ``True`` if a row was deleted.
        """
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "DELETE FROM embeddings WHERE entry_id = ?",
                (entry_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get(self, entry_id: str) -> dict[str, Any] | None:
        """Look up a stored embedding by *entry_id*."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT * FROM embeddings WHERE entry_id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def count(self) -> int:
        """Return the total number of stored embeddings."""
        with self._lock:
            conn = self._get_conn()
            row = conn.execute("SELECT COUNT(*) as n FROM embeddings").fetchone()
            return row["n"] if row else 0

    def list_all(self, limit: int = 50, offset: int = 0,
                  category: str | None = None) -> list[dict[str, Any]]:
        """Enumerate stored embeddings, newest first.

        Args:
            limit: Maximum entries (default 50).
            offset: Skip this many entries (for pagination).
            category: Optional category filter (case-sensitive exact match).

        Returns:
            List of vector entries (newest first).
        """
        with self._lock:
            conn = self._get_conn()
            if category:
                cursor = conn.execute(
                    "SELECT entry_id, content, category, updated_at FROM embeddings "
                    "WHERE category = ? COLLATE NOCASE ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (category, limit, offset),
                )
            else:
                cursor = conn.execute(
                    "SELECT entry_id, content, category, updated_at FROM embeddings "
                    "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            return [dict(row) for row in cursor]

    def categories(self) -> list[dict[str, Any]]:
        """Return all unique categories with entry counts.

        Returns:
            List of ``{"category": str, "count": int}`` sorted by count descending.
        """
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT category, COUNT(*) as count FROM embeddings "
                "GROUP BY category ORDER BY count DESC",
            )
            return [{"category": row["category"], "count": row["count"]} for row in cursor]

    def clear(self) -> int:
        """Delete all embeddings from the vector store.

        This wipes the vector index for a fresh start while leaving the
        FTS5 long-term memory store intact. Re-populate via
        ``/memory vector migrate`` or ``store()`` calls.

        Returns the number of deleted rows.
        """
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("SELECT COUNT(*) as n FROM embeddings")
            count = cursor.fetchone()["n"]
            conn.execute("DELETE FROM embeddings")
            conn.commit()
            logger.info("VectorStore: cleared %d embeddings", count)
            return count

    def rebuild(self) -> int:
        """Recompute all embeddings from stored content.

        Useful after changing the embedding model or on first run.
        Returns the number of embeddings (re-)stored.
        """
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT entry_id, content, category FROM embeddings",
            )
            rows = list(cursor)

        if not rows:
            return 0

        texts = [r["content"] for r in rows]
        vectors = self._engine.embed_many(texts)

        with self._lock:
            conn = self._get_conn()
            now = time.time()
            count = 0
            for row, vec in zip(rows, vectors):
                if not row["content"].strip():
                    continue
                conn.execute(
                    "UPDATE embeddings SET embedding = ?, updated_at = ? WHERE entry_id = ?",
                    (self._pack(vec), now, row["entry_id"]),
                )
                count += 1
            conn.commit()

        logger.info("VectorStore: rebuilt %d embeddings", count)
        return count

    # ── Serialisation helpers ────────────────────────────────────────

    @staticmethod
    def _pack(vec: list[float]) -> bytes:
        """Pack a list of N floats into a ``struct`` BLOB."""
        return struct.pack(f"<{len(vec)}f", *vec)

    @staticmethod
    def _unpack(blob: bytes) -> list[float]:
        """Unpack a ``struct`` BLOB back into a list of floats."""
        n = len(blob) // 4
        return list(struct.unpack(f"<{n}f", blob))
