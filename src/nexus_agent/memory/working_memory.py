"""
Working Memory — Active task context scratchpad.

Holds the current task state, active file contents, recent tool results,
and temporary notes. This is the agent's "short-term" memory.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any

_DEFAULT_MAX_ENTRIES = 100


class WorkingMemory:
    """In-memory scratchpad for active task context.

    Stores key-value pairs with timestamps and automatic eviction
    when capacity is exceeded.
    """

    def __init__(self, max_entries: int = _DEFAULT_MAX_ENTRIES):
        self.max_entries = max(max_entries, 1)
        self._store: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._scratchpad: list[str] = []
        self._lock = threading.Lock()

    def set(self, key: str, value: str, category: str = "general") -> None:
        """Store a value in working memory."""
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)

            self._store[key] = {
                "value": value,
                "category": category,
                "timestamp": time.time(),
                "access_count": 0,
            }

            # Evict oldest if over capacity
            if len(self._store) > self.max_entries:
                self._store.popitem(last=False)

    def get(self, key: str) -> str | None:
        """Retrieve a value from working memory."""
        with self._lock:
            entry = self._store.get(key)
            if entry:
                entry["access_count"] += 1
                self._store.move_to_end(key)
                return entry["value"]
            return None

    def delete(self, key: str) -> bool:
        """Remove a key from working memory."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def list_keys(self, category: str | None = None) -> list[str]:
        """List all keys, optionally filtered by category."""
        with self._lock:
            if category:
                return [k for k, v in self._store.items() if v["category"] == category]
            return list(self._store.keys())

    def add_note(self, note: str) -> None:
        """Add a note to the scratchpad."""
        with self._lock:
            self._scratchpad.append(f"[{time.strftime('%H:%M:%S')}] {note}")
            # Keep scratchpad manageable
            if len(self._scratchpad) > 50:
                self._scratchpad = self._scratchpad[-40:]

    def get_scratchpad(self) -> str:
        """Get the current scratchpad contents."""
        with self._lock:
            return "\n".join(self._scratchpad) if self._scratchpad else ""

    def clear_scratchpad(self) -> None:
        """Clear the scratchpad."""
        with self._lock:
            self._scratchpad.clear()

    def clear(self) -> None:
        """Clear all working memory."""
        with self._lock:
            self._store.clear()
            self._scratchpad.clear()

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of working memory contents."""
        with self._lock:
            return {
                "entries": len(self._store),
                "categories": list(dict.fromkeys(v["category"] for v in self._store.values())),
                "scratchpad_lines": len(self._scratchpad),
                "max_entries": self.max_entries,
            }
