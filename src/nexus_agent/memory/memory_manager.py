"""
Memory Manager — Orchestrates all memory subsystems.

Inspired by letta (MemGPT) and hermes agent's persistent memory.
The agent can autonomously read/write its own memory, retaining
context across sessions and learning from interactions.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from nexus_agent.memory.episodic import EpisodicMemory
from nexus_agent.memory.long_term import LongTermMemory
from nexus_agent.memory.user_profile import UserProfile
from nexus_agent.memory.working_memory import WorkingMemory

logger = logging.getLogger(__name__)


class MemoryManager:
    """Orchestrates all memory subsystems.

    Provides a unified interface for the agent to store and retrieve
    information across different memory types:
    - Working: Active task context (scratchpad)
    - Long-term: Persistent knowledge (SQLite FTS5)
    - Episodic: Session history
    - User profile: Learned user preferences
    """

    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir or "~/.nexus-agent/memory").expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()

        self.working = WorkingMemory()
        self.long_term = LongTermMemory(self.data_dir / "long_term.db")
        self.episodic = EpisodicMemory(self.data_dir / "episodic.db")
        self.user_profile = UserProfile(self.data_dir / "user_profile.yaml")

        logger.info(f"Memory manager initialized at {self.data_dir}")

    def __del__(self) -> None:
        try:
            self.close()
        except (OSError, RuntimeError):
            pass

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search across all memory types for relevant information.

        Returns results from long-term and episodic memory,
        ranked by relevance.
        """
        with self._lock:
            results: list[dict[str, Any]] = []
            seen_ids: set[str] = set()

            # Search long-term memory (FTS5)
            lt_results = self.long_term.search(query, limit=limit)
            for r in lt_results:
                r = dict(r)
                r["source"] = "long_term"
                r_id = r.get("id", "")
                if r_id not in seen_ids:
                    seen_ids.add(r_id)
                    results.append(r)

            # Search episodic memory
            ep_results = self.episodic.search(query, limit=limit // 2)
            for r in ep_results:
                r = dict(r)
                r["source"] = "episodic"
                r_id = r.get("id", "")
                if r_id not in seen_ids:
                    seen_ids.add(r_id)
                    results.append(r)

            # Normalize score and Sort by relevance score
            max_score = max((float(r.get("score", 0.0)) for r in results), default=0.0)
            if max_score > 0.0:
                for r in results:
                    r["score"] = float(r.get("score", 0.0)) / max_score

            results.sort(key=lambda x: x.get("score", 0.0), reverse=True)

            return results[:limit]

    def store(self, content: str, category: str = "general",
              metadata: dict[str, Any] | None = None) -> str:
        """Store information in long-term memory.

        Args:
            content: The information to store.
            category: Category label (e.g., 'code_pattern', 'architecture', 'preference').
            metadata: Additional metadata.

        Returns:
            Memory entry ID.
        """
        with self._lock:
            return self.long_term.store(content, category=category, metadata=metadata)

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

        Combines relevant memories and user preferences into a
        formatted context block.
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

            # Relevant long-term memories
            if query:
                memories = self.search(query, limit=5)
                if memories:
                    mem_lines = []
                    for m in memories:
                        mem_lines.append(f"- [{m.get('category', 'general')}] {m.get('content', '')[:200]}")
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
            self.user_profile.close()
