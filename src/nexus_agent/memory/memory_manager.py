"""
Memory Manager — Orchestrates all memory subsystems.

Inspired by letta (MemGPT) and hermes agent's persistent memory.
The agent can autonomously read/write its own memory, retaining
context across sessions and learning from interactions.

Includes **vector/semantic search** via a local embedding engine,
merged with the existing FTS5 full-text results for hybrid retrieval.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

from nexus_agent.memory.episodic import EpisodicMemory
from nexus_agent.memory.long_term import LongTermMemory
from nexus_agent.memory.user_profile import UserProfile
from nexus_agent.memory.vector_store import VectorStore
from nexus_agent.memory.working_memory import WorkingMemory

logger = logging.getLogger(__name__)

# Retention scoring defaults
COMPACT_INTERVAL = 50
STM_PROMOTE_THRESHOLD = 5
EPISODIC_RETENTION_DAYS = 30


class MemoryManager:
    """Orchestrates all memory subsystems.

    Provides a unified interface for the agent to store and retrieve
    information across different memory types:
    - Working: Active task context (scratchpad)
    - Long-term: Persistent knowledge (SQLite FTS5 + vector embeddings)
    - Vector: Semantic similarity search via local embedding engine
    - Episodic: Session history
    - User profile: Learned user preferences

    Vector search is **hybrid**: results from FTS5 and cosine-similarity
    are merged and re-ranked for each query.  If the embedding engine
    is unavailable the system transparently falls back to FTS5-only.
    """

    def __init__(
        self,
        data_dir: str | Path | None = None,
        enable_vector: bool = True,
    ):
        self.data_dir = Path(data_dir or "~/.nexus-agent/memory").expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()
        self._enable_vector = enable_vector
        self._op_count = 0

        self.working = WorkingMemory()
        self.long_term = LongTermMemory(self.data_dir / "long_term.db")
        self.episodic = EpisodicMemory(self.data_dir / "episodic.db")
        self.user_profile = UserProfile(self.data_dir / "user_profile.yaml")

        # Vector store (lazy initialised so we can also init it post-
        # construction for tests that want to inject a custom engine).
        self.vector: VectorStore | None = None
        if enable_vector:
            try:
                self.vector = VectorStore(self.data_dir / "vector_store.db")
            except Exception as exc:
                logger.warning("VectorStore unavailable: %s", exc)
                self.vector = None

        logger.info("Memory manager initialized at %s (vector=%s)", self.data_dir, self.vector is not None)

    def __del__(self) -> None:
        try:
            self.close()
        except (OSError, RuntimeError):
            pass

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search across all memory types for relevant information.

        Uses **hybrid retrieval**:
        1. FTS5 full-text search from long-term memory
        2. Vector/semantic search from the vector store (if enabled)
        3. FTS5 from episodic memory

        Results are merged, de-duplicated, and re-ranked by score.
        """
        with self._lock:
            results: list[dict[str, Any]] = []
            seen_ids: set[str] = set()

            # 1. Vector / semantic search (highest quality)
            if self.vector is not None and query.strip():
                try:
                    vec_results = self.vector.search(query, limit=limit)
                    for r in vec_results:
                        r_id = r.get("id", "")
                        if r_id not in seen_ids:
                            seen_ids.add(r_id)
                            r["source"] = "vector"
                            results.append(r)
                except Exception as exc:
                    logger.debug("Vector search failed, using FTS5 only: %s", exc)

            # 2. FTS5 from long-term memory
            try:
                lt_results = self.long_term.search(query, limit=limit)
                for r in lt_results:
                    r = dict(r)
                    r_id = r.get("id", "")
                    if r_id not in seen_ids:
                        seen_ids.add(r_id)
                        r["source"] = "long_term"
                        results.append(r)
            except Exception as exc:
                logger.debug("FTS5 search failed: %s", exc)

            # 3. FTS5 from episodic memory
            try:
                ep_results = self.episodic.search(query, limit=limit // 2)
                for r in ep_results:
                    r = dict(r)
                    r_id = r.get("id", "")
                    if r_id not in seen_ids:
                        seen_ids.add(r_id)
                        r["source"] = "episodic"
                        results.append(r)
            except Exception as exc:
                logger.debug("Episodic search failed: %s", exc)

            # Normalise scores to 0–1 range
            max_score = max((float(r.get("score", 0.0)) for r in results), default=0.0)
            if max_score > 0.0:
                for r in results:
                    r["score"] = float(r.get("score", 0.0)) / max_score

            results.sort(key=lambda x: x.get("score", 0.0), reverse=True)

            return results[:limit]

    def store(self, content: str, category: str = "general",
              metadata: dict[str, Any] | None = None) -> str:
        """Store information in long-term memory **and** vector store.

        Args:
            content: The information to store.
            category: Category label (e.g., 'code_pattern', 'architecture', 'preference').
            metadata: Additional metadata.

        Returns:
            Memory entry ID.
        """
        with self._lock:
            entry_id = self.long_term.store(content, category=category, metadata=metadata)
            # Also store embedding in the vector store
            if self.vector is not None:
                try:
                    self.vector.store(entry_id, content, category=category)
                except Exception as exc:
                    logger.debug("Failed to store vector embedding: %s", exc)
            self._check_compact()
            return entry_id

    def update(self, entry_id: str, content: str | None = None,
               category: str | None = None) -> bool:
        """Update an existing long-term memory entry **and** its vector embedding.

        If *content* is provided, the embedding is re-computed.

        Args:
            entry_id: ID of the memory to update.
            content: New content (optional).
            category: New category (optional).

        Returns:
            True if a row was updated, False otherwise.
        """
        with self._lock:
            ok = self.long_term.update(entry_id, content=content, category=category)
            if ok and self.vector is not None and content is not None:
                try:
                    cat = category or self.long_term.get(entry_id).get("category", "general")
                    self.vector.store(entry_id, content, category=cat)
                except Exception as exc:
                    logger.debug("Failed to update vector embedding: %s", exc)
            return ok

    def forget(self, entry_id: str) -> bool:
        """Delete a long-term memory entry **and** its vector embedding.

        Args:
            entry_id: ID of the memory to forget.

        Returns:
            True if a row was deleted, False otherwise.
        """
        with self._lock:
            ok = self.long_term.delete(entry_id)
            if self.vector is not None:
                try:
                    self.vector.delete(entry_id)
                except Exception as exc:
                    logger.debug("Failed to delete vector embedding: %s", exc)
            return ok

    def get(self, entry_id: str) -> dict[str, Any] | None:
        """Look up a specific memory by ID."""
        with self._lock:
            return self.long_term.get(entry_id)

    def list_all(self, category: str | None = None, limit: int = 100,
                 offset: int = 0) -> list[dict[str, Any]]:
        """Enumerate memories, newest first.

        Args:
            category: Optional category filter.
            limit: Maximum number of entries to return.
            offset: Skip this many entries (for pagination).

        Returns:
            List of memory entries (newest first).
        """
        with self._lock:
            return self.long_term.list_all(
                category=category, limit=limit, offset=offset,
            )

    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics across all tiers."""
        with self._lock:
            lt_stats = self.long_term.get_stats()
            lt_total = lt_stats.get("total_entries", 0)
            working_summary = self.working.get_summary()
            ep_count = len(self.episodic.get_recent(limit=10000))
            vs_count = self.vector.count() if self.vector is not None else 0
            up_summary = self.user_profile.get_summary()
            up_count = 1 if up_summary else 0
            # total = unique entries across countable tiers (vector mirrors long-term, user_profile is singular)
            total = working_summary["entries"] + lt_total + ep_count
            return {
                "working": working_summary["entries"],
                "long_term": lt_total,
                "episodic": ep_count,
                "user_profile": up_count,
                "vector_store": vs_count,
                "total_entries": total,
                "categories": lt_stats.get("categories", 0),
                "db_path": lt_stats.get("db_path", str(self.data_dir)),
            }

    # ── Retention Scoring ────────────────────────────────────────────

    def get_all_scores(self) -> dict[str, list[dict[str, Any]]]:
        """Get heat scores across all memory tiers.

        Returns:
            Dict mapping tier names to list of entries with score/heat info.
        """
        with self._lock:
            scores: dict[str, list[dict[str, Any]]] = {
                "working": [],
                "long_term": [],
                "episodic": [],
            }
            # Working memory — access-count-based
            now = time.time()
            for key, entry in list(self.working._store.items()):
                age_hours = (now - entry["timestamp"]) / 3600
                scores["working"].append({
                    "id": f"wm:{key}",
                    "content_preview": entry["value"][:100],
                    "access_count": entry["access_count"],
                    "heat_score": entry["access_count"] * 2.0 + max(0, 10 - age_hours),
                    "tier": "working",
                })
            # Long-term — use existing heat score engine
            try:
                lt_scores = self.long_term.get_heat_scores(limit=500)
                for s in lt_scores:
                    s["tier"] = "long_term"
                scores["long_term"] = lt_scores
            except Exception as exc:
                logger.debug("Failed to get long-term heat scores: %s", exc)
            # Episodic — recency-based
            try:
                recent = self.episodic.get_recent(limit=500)
                for ep in recent:
                    age_days = (now - ep.get("created_at", now)) / 86400
                    scores["episodic"].append({
                        "id": str(ep.get("id", "")),
                        "content_preview": (ep.get("summary", "") or "")[:100],
                        "heat_score": max(0, 30 - age_days) / 30.0 * 10.0,
                        "tier": "episodic",
                    })
            except Exception as exc:
                logger.debug("Failed to get episodic scores: %s", exc)
            return scores

    # ── STM → MTM → LTM Promotion ───────────────────────────────────

    def promote_stm_to_ltm(self, threshold: int | None = None) -> int:
        """Promote frequently-accessed working memory entries to long-term.

        Args:
            threshold: Minimum access count to promote. Defaults to
                ``STM_PROMOTE_THRESHOLD``.

        Returns:
            Number of entries promoted.
        """
        threshold = threshold if threshold is not None else STM_PROMOTE_THRESHOLD
        with self._lock:
            promoted = 0
            keys_to_promote = [
                key for key, entry in self.working._store.items()
                if entry["access_count"] >= threshold
            ]
            for key in keys_to_promote:
                entry = self.working._store[key]
                try:
                    self.long_term.store(
                        content=entry["value"],
                        category=f"stm_promoted:{entry['category']}",
                        metadata={
                            "original_key": key,
                            "access_count": entry["access_count"],
                            "promoted_at": time.time(),
                            "source": "working_memory",
                        },
                    )
                    self.working.delete(key)
                    promoted += 1
                except Exception as exc:
                    logger.debug("Failed to promote '%s' to long-term: %s", key, exc)
            if promoted:
                logger.info("Promoted %d entries from working → long-term memory", promoted)
            return promoted

    # ── Compaction ───────────────────────────────────────────────────

    def compact(self, aggressive: bool = False) -> dict[str, int]:
        """Run compaction across all memory tiers.

        Steps:
        1. Prune low-heat long-term memories
        2. Prune old episodic memories
        3. Promote STM→LTM if eligible

        Args:
            aggressive: If True, use lower thresholds for more pruning.

        Returns:
            Dict mapping action to count of affected entries.
        """
        with self._lock:
            result: dict[str, int] = {"ltm_pruned": 0, "episodic_pruned": 0, "stm_promoted": 0}

            # 1. Prune low-heat long-term memories
            try:
                threshold = 2.0 if aggressive else None
                target = 500 if aggressive else None
                result["ltm_pruned"] = self.long_term.prune_low_heat_memories(
                    threshold=threshold, target_count=target,
                )
            except Exception as exc:
                logger.debug("Long-term compaction failed: %s", exc)

            # 2. Prune old episodic memories
            try:
                cutoff = time.time() - (EPISODIC_RETENTION_DAYS * 86400)
                if aggressive:
                    cutoff = time.time() - (14 * 86400)
                conn = self.episodic._get_conn()
                cursor = conn.execute(
                    "SELECT COUNT(*) as cnt FROM episodes WHERE created_at < ?",
                    (cutoff,),
                )
                old_count = cursor.fetchone()["cnt"]
                if old_count:
                    conn.execute(
                        "DELETE FROM episodes WHERE created_at < ?",
                        (cutoff,),
                    )
                    conn.commit()
                    result["episodic_pruned"] = old_count
                    logger.info("Pruned %d old episodic memories", old_count)
            except Exception as exc:
                logger.debug("Episodic compaction failed: %s", exc)

            # 3. Promote STM → LTM
            try:
                thresh = 3 if aggressive else None
                result["stm_promoted"] = self.promote_stm_to_ltm(threshold=thresh)
            except Exception as exc:
                logger.debug("STM promotion failed: %s", exc)

            return result

    def _check_compact(self) -> None:
        """Auto-compact if operation count exceeds threshold."""
        self._op_count += 1
        if self._op_count >= COMPACT_INTERVAL:
            self._op_count = 0
            try:
                self.compact(aggressive=False)
            except Exception as exc:
                logger.debug("Auto-compaction failed: %s", exc)

    # ── Cross-tier listing / search (for ACP) ───────────────────────

    def list_all_unified(self, tier: str | None = None, limit: int = 100,
                         offset: int = 0) -> list[dict[str, Any]]:
        """List memories across all tiers.

        Args:
            tier: Optional tier filter ('working', 'long_term', 'episodic',
                'vector', 'user_profile'). If None, returns from all.
            limit: Max entries per tier.
            offset: Skip N entries.

        Returns:
            List of memory entries with 'source' field indicating tier.
        """
        with self._lock:
            results: list[dict[str, Any]] = []

            if tier is None or tier == "working":
                for key, entry in list(self.working._store.items()):
                    results.append({
                        "id": f"wm:{key}",
                        "content": entry["value"],
                        "source": "working",
                        "category": entry["category"],
                        "created_at": entry["timestamp"],
                        "updated_at": entry["timestamp"],
                        "access_count": entry["access_count"],
                        "score": entry["access_count"] * 2.0,
                    })

            if tier is None or tier == "long_term":
                try:
                    lt_entries = self.long_term.list_all(limit=limit, offset=offset)
                    for e in lt_entries:
                        e["source"] = "long_term"
                        if "score" not in e:
                            e["score"] = float(e.get("metadata", {}).get("heat_score", 0.0)) if isinstance(e.get("metadata"), dict) else 0.0
                    results.extend(lt_entries)
                except Exception as exc:
                    logger.debug("Failed to list long-term: %s", exc)

            if tier is None or tier == "episodic":
                try:
                    ep_entries = self.episodic.get_recent(limit=limit)
                    for e in ep_entries:
                        e["source"] = "episodic"
                        e["content"] = e.pop("summary", "")
                        e["score"] = 0.0
                    results.extend(ep_entries)
                except Exception as exc:
                    logger.debug("Failed to list episodic: %s", exc)

            if tier is None or tier == "vector":
                if self.vector is not None:
                    try:
                        vec_entries = self.vector.list_all(limit=limit, offset=offset)
                        for e in vec_entries:
                            e["source"] = "vector"
                            if "id" not in e and "entry_id" in e:
                                e["id"] = e.pop("entry_id")
                            e.setdefault("score", 0.0)
                            e.setdefault("created_at", 0.0)
                            if "updated_at" not in e:
                                e["updated_at"] = 0.0
                            if "access_count" not in e:
                                e["access_count"] = 0
                        results.extend(vec_entries)
                    except Exception as exc:
                        logger.debug("Failed to list vector: %s", exc)

            if tier is None or tier == "user_profile":
                try:
                    summary = self.user_profile.get_summary()
                    if summary:
                        results.append({
                            "id": "user_profile:1",
                            "content": summary,
                            "source": "user_profile",
                            "category": "user_preferences",
                            "created_at": 0.0,
                            "updated_at": 0.0,
                            "access_count": 0,
                            "score": 10.0,
                        })
                except Exception as exc:
                    logger.debug("Failed to list profile: %s", exc)

            return results

    def remember(self, key: str) -> str | None:
        """Quick recall by key from working memory or long-term.

        First checks working memory for an exact key match, then falls
        back to a full-text semantic search across long-term memory. This
        dual lookup allows fast retrieval of scratchpad values while also
        supporting semantic recall from persistent storage.
        """
        with self._lock:
            # Check working memory first
            result = self.working.get(key)
            if result is not None:
                return result

            # Fall back to long-term search
            results = self.long_term.search(key, limit=1)
            if results:
                return results[0].get("content")

            return None

    def save_session_summary(self, session_id: str, summary: str,
                             messages_count: int = 0) -> None:
        """Save a session summary to episodic memory."""
        with self._lock:
            self.episodic.save_session(
                session_id=session_id,
                summary=summary,
                messages_count=messages_count,
            )

    def get_context_for_prompt(self, query: str = "") -> str:
        """Generate a context string for injection into the system prompt.

        Combines relevant memories (now including vector search results)
        and user preferences into a formatted context block.
        """
        with self._lock:
            parts: list[str] = []

            # User preferences
            prefs = self.user_profile.get_summary()
            if prefs:
                parts.append(f"[User Preferences]\n{prefs}")

            # Working memory scratchpad
            scratchpad = self.working.get_scratchpad()
            if scratchpad:
                parts.append(f"[Active Context]\n{scratchpad}")

            # Relevant memories (hybrid FTS5 + vector search)
            if query:
                memories = self.search(query, limit=5)
                if memories:
                    mem_lines = []
                    for m in memories:
                        src_tag = m.get("source", "memory")
                        cat = m.get("category", "general")
                        preview = m.get("content", "")[:200]
                        mem_lines.append(f"- [{src_tag}:{cat}] {preview}")
                    parts.append("[Relevant Memories]\n" + "\n".join(mem_lines))

            if not parts:
                return ""

            return "\n\n".join(parts)

    def close(self) -> None:
        """Close all memory subsystems."""
        with self._lock:
            self.working.clear()
            self.long_term.close()
            self.episodic.close()
            if self.vector is not None:
                self.vector.close()
            self.user_profile.close()
