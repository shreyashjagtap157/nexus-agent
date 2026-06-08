"""
Long-Term Memory — SQLite-backed persistent memory with FTS5 full-text search
and **heat-score retention** (inspired by MemoryOS).

Heat score algorithm:
    Heat = α · N_visit + β · L_interaction + γ · exp(-Δt / μ)

Where:
- N_visit: Number of times the memory has been accessed
- L_interaction: Length of the memorized content (interaction scale)
- Δt: Time since last access (seconds)
- μ: Time decay constant (default: 7 days in seconds)
- α, β, γ: Configurable weighting coefficients

Memories with low heat scores are automatically pruned when storage
limits are reached, keeping only the most relevant content.

Stores learned patterns, code conventions, architecture decisions,
and other persistent knowledge.
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
import time
import uuid
from typing import Any

from nexus_agent.core.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


# ── Heat Score Configuration ──────────────────────────────────────────

# Default coefficients for heat score calculation
HEAT_ALPHA: float = 1.0      # Weight for access count (N_visit)
HEAT_BETA: float = 0.01      # Weight for content length (L_interaction)
HEAT_GAMMA: float = 2.0      # Weight for recency (time decay)
HEAT_MU: float = 604800.0    # Time decay constant: 7 days in seconds
HEAT_PROMOTE_THRESHOLD: float = 50.0   # Heat score above which → promote to long-term
HEAT_PRUNE_THRESHOLD: float = 1.0      # Heat score below which → eligible for pruning

# Maximum number of memories before pruning is triggered
MAX_MEMORIES_BEFORE_PRUNE: int = 5000
# Target count after pruning (aggressive cleanup to avoid frequent pruning)
TARGET_MEMORIES_AFTER_PRUNE: int = 3000


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

    # ── Heat Score Calculation ──────────────────────────────────────

    def calculate_heat(
        self,
        access_count: int,
        content_length: int,
        last_access_time: float,
    ) -> float:
        """Calculate heat score for a memory entry.

        Implements the MemoryOS heat score algorithm:
            Heat = α · N_visit + β · L_interaction + γ · exp(-Δt / μ)

        Args:
            access_count: Number of times accessed.
            content_length: Length of the memory content in characters.
            last_access_time: Unix timestamp of last access.

        Returns:
            Heat score (higher = more important to retain).
        """
        recency = math.exp(-(time.time() - last_access_time) / HEAT_MU)
        return (
            HEAT_ALPHA * max(0, access_count)
            + HEAT_BETA * max(0, content_length)
            + HEAT_GAMMA * recency
        )

    def refresh_heat_scores(self) -> dict[str, float]:
        """Recalculate and update heat scores for all memories.

        Returns:
            Dict mapping memory ID to computed heat score.
        """
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT id, content, access_count, updated_at FROM memories"
            )
            scores: dict[str, float] = {}
            for row in cursor:
                mid = row["id"]
                content = row["content"] or ""
                heat = self.calculate_heat(
                    access_count=row["access_count"] or 0,
                    content_length=len(content),
                    last_access_time=row["updated_at"] or time.time(),
                )
                scores[mid] = heat

            # Persist heat scores in metadata
            for mid, heat in scores.items():
                existing_meta = {}
                try:
                    meta_cursor = conn.execute(
                        "SELECT metadata FROM memories WHERE id = ?", (mid,)
                    )
                    meta_row = meta_cursor.fetchone()
                    if meta_row and meta_row["metadata"]:
                        existing_meta = json.loads(meta_row["metadata"])
                except (json.JSONDecodeError, TypeError):
                    existing_meta = {}

                existing_meta["heat_score"] = round(heat, 2)
                conn.execute(
                    "UPDATE memories SET metadata = ? WHERE id = ?",
                    (json.dumps(existing_meta), mid),
                )
            conn.commit()
            return scores

    def get_heat_scores(
        self,
        min_heat: float | None = None,
        max_heat: float | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get memory entries with their heat scores, ordered by heat (lowest first).

        Args:
            min_heat: Optional minimum heat threshold filter.
            max_heat: Optional maximum heat threshold filter.
            limit: Maximum entries to return.

        Returns:
            List of dicts with 'id', 'content_preview', 'heat_score', and 'category'.
        """
        self.refresh_heat_scores()

        with self._lock:
            conn = self._get_conn()

            # Since heat score is stored in metadata JSON, we filter in Python
            cursor = conn.execute(
                "SELECT id, content, category, metadata, access_count, updated_at FROM memories "
                "ORDER BY updated_at DESC LIMIT ?",
                (limit * 2,),  # Fetch extra for Python-side filtering
            )

            results = []
            for row in cursor:
                meta = {}
                try:
                    if row["metadata"]:
                        meta = json.loads(row["metadata"])
                except (json.JSONDecodeError, TypeError):
                    meta = {}

                heat = meta.get("heat_score", 0.0)
                if min_heat is not None and heat < min_heat:
                    continue
                if max_heat is not None and heat > max_heat:
                    continue

                content = row["content"] or ""
                results.append({
                    "id": row["id"],
                    "content_preview": content[:100] + "..." if len(content) > 100 else content,
                    "heat_score": heat,
                    "category": row["category"],
                    "access_count": row["access_count"] or 0,
                })

            results.sort(key=lambda x: x["heat_score"])
            return results[:limit]

    def prune_low_heat_memories(
        self,
        threshold: float | None = None,
        target_count: int | None = None,
    ) -> int:
        """Remove memories with heat scores below the threshold.

        Also triggers if total memory count exceeds ``MAX_MEMORIES_BEFORE_PRUNE``,
        in which case the lowest-heat entries are removed until count drops to
        ``target_count``.

        Args:
            threshold: Heat score threshold. Memories below this are removed.
                Defaults to ``HEAT_PRUNE_THRESHOLD``.
            target_count: If total count exceeds this, prune aggressively.
                Defaults to ``TARGET_MEMORIES_AFTER_PRUNE``.

        Returns:
            Number of memories pruned.
        """
        threshold = threshold if threshold is not None else HEAT_PRUNE_THRESHOLD
        target_count = target_count if target_count is not None else TARGET_MEMORIES_AFTER_PRUNE

        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("SELECT COUNT(*) as count FROM memories")
            total = cursor.fetchone()["count"]

            if total <= target_count:
                # Only prune if threshold-based pruning finds candidates
                pass

            scores = self.refresh_heat_scores()

            # Find entries below threshold
            to_prune = [mid for mid, heat in scores.items() if heat < threshold]

            # If total count exceeds max, also prune lowest-heat entries
            if total > MAX_MEMORIES_BEFORE_PRUNE:
                above_threshold = [(mid, heat) for mid, heat in scores.items() if heat >= threshold]
                above_threshold.sort(key=lambda x: x[1])  # Sort by heat ascending
                excess = total - target_count
                extra_prune = above_threshold[:excess]
                to_prune.extend(mid for mid, _ in extra_prune)

            if not to_prune:
                return 0

            # Delete in batch
            placeholders = ",".join("?" for _ in to_prune)
            conn.execute(
                f"DELETE FROM memories WHERE id IN ({placeholders})",
                to_prune,
            )
            conn.commit()

            logger.info(
                "Pruned %d low-heat memories (total was %d, now %d)",
                len(to_prune), total, max(0, total - len(to_prune)),
            )
            return len(to_prune)

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


