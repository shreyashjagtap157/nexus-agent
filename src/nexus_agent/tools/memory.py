"""
Memory Tool — Self-editing the agent's own memory.

The agent uses this tool to:
- list all stored memories (with optional category filter)
- view a specific memory by ID
- store a new memory
- update an existing memory's content or category
- forget a memory by ID
- view aggregate stats (totals + per-category counts)

The tool is read-write but operates only on the agent's own SQLite
memory database — it never touches user files.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from nexus_agent.tools.base import Tool

if TYPE_CHECKING:
    from nexus_agent.memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)


def _coerce_limit(value: Any, default: int = 10) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, min(n, 1000))


class MemoryTool(Tool):
    """Self-manage the agent's long-term memory."""

    def __init__(self, memory_manager: "MemoryManager | None" = None) -> None:
        self._memory = memory_manager

    def set_memory(self, memory_manager: "MemoryManager") -> None:
        """Bind (or rebind) the memory manager — useful for late init."""
        self._memory = memory_manager

    @property
    def name(self) -> str:
        return "memory"

    @property
    def description(self) -> str:
        return (
            "Manage the agent's persistent memory. Actions: list, get, store, "
            "update, forget, stats. Use 'store' to remember a fact, 'forget' "
            "to remove one, 'list' to see what's known, 'update' to revise, "
            "and 'stats' for aggregate counts."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "action": {
                "type": "string",
                "description": "One of: list, get, store, update, forget, stats.",
            },
            "entry_id": {"type": "string", "description": "Memory ID (for get/update/forget).", "required": False},
            "content": {"type": "string", "description": "Memory content (for store/update).", "required": False},
            "category": {"type": "string", "description": "Category label (for store/update/list filter).", "required": False},
            "limit": {"type": "integer", "description": "Max entries to return (list). Default 10, max 1000.", "required": False},
            "offset": {"type": "integer", "description": "Skip this many entries (list). Default 0.", "required": False},
        }

    @property
    def required_params(self) -> list[str]:
        return ["action"]

    @property
    def permission_level(self) -> str:
        return "read-write"

    @property
    def timeout(self) -> int:
        return 5

    def execute(
        self,
        action: str,
        entry_id: str | None = None,
        content: str | None = None,
        category: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        **kwargs: Any,
    ) -> str:
        if self._memory is None:
            return "Error: memory manager not configured."

        action = (action or "").strip().lower().replace("-", "_")
        if not action:
            return "Error: 'action' is required."

        if action == "list":
            return self._list(category=category, limit=limit, offset=offset)
        if action == "get":
            return self._get(entry_id)
        if action == "store":
            return self._store(content, category)
        if action == "update":
            return self._update(entry_id, content, category)
        if action == "forget":
            return self._forget(entry_id)
        if action == "stats":
            return self._stats()
        return f"Error: unknown action {action!r}."

    # --- actions ---

    def _list(
        self, category: str | None, limit: int | None, offset: int | None,
    ) -> str:
        items = self._memory.list_all(
            category=category,
            limit=_coerce_limit(limit, default=10),
            offset=max(0, int(offset or 0)),
        )
        if not items:
            scope = f" in category {category!r}" if category else ""
            return f"(no memories stored{scope})"
        lines: list[str] = []
        for m in items:
            ts = m.get("created_at", 0)
            preview = (m.get("content") or "").replace("\n", " ")[:120]
            cat = m.get("category", "general")
            lines.append(
                f"  [{m['id'][:8]}] ({cat}, ts={ts:.0f}) {preview}"
            )
        header = f"{len(items)} memor{'y' if len(items) == 1 else 'ies'}"
        if category:
            header += f" in category {category!r}"
        return header + ":\n" + "\n".join(lines)

    def _get(self, entry_id: str | None) -> str:
        if not entry_id:
            return "Error: 'entry_id' is required for action=get."
        m = self._memory.get(entry_id)
        if m is None:
            return f"Error: no memory with id {entry_id!r}."
        return (
            f"[{m['id']}] category={m.get('category', 'general')!r} "
            f"created={m.get('created_at', 0):.0f} "
            f"updated={m.get('updated_at', 0):.0f} "
            f"access_count={m.get('access_count', 0)}\n"
            f"{m.get('content', '')}"
        )

    def _store(self, content: str | None, category: str | None) -> str:
        if not content or not content.strip():
            return "Error: 'content' is required for action=store."
        cat = (category or "general").strip()
        try:
            entry_id = self._memory.store(content.strip(), category=cat)
        except (ValueError, OSError) as e:
            return f"Error: failed to store memory: {e}"
        return f"Stored memory [{entry_id}] in category {cat!r}."

    def _update(
        self, entry_id: str | None, content: str | None, category: str | None,
    ) -> str:
        if not entry_id:
            return "Error: 'entry_id' is required for action=update."
        if content is None and category is None:
            return "Error: must provide 'content' or 'category' to update."
        if content is not None and not content.strip():
            return "Error: 'content' cannot be empty."
        ok = self._memory.update(
            entry_id,
            content=content.strip() if content else None,
            category=category.strip() if category else None,
        )
        if not ok:
            return f"Error: no memory with id {entry_id!r}."
        return f"Updated memory [{entry_id}]."

    def _forget(self, entry_id: str | None) -> str:
        if not entry_id:
            return "Error: 'entry_id' is required for action=forget."
        ok = self._memory.forget(entry_id)
        if not ok:
            return f"Error: no memory with id {entry_id!r}."
        return f"Forgot memory [{entry_id}]."

    def _stats(self) -> str:
        stats = self._memory.get_stats()
        cats = self._memory.long_term.list_categories()
        lines: list[str] = [
            f"Total memories: {stats.get('total_entries', 0)}",
            f"Categories: {stats.get('categories', 0)}",
            f"DB path: {stats.get('db_path', '?')}",
        ]
        if cats:
            cat_lines = ", ".join(
                f"{c['category']}={c['count']}" for c in cats
            )
            lines.append(f"By category: {cat_lines}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        if self._memory is None:
            return "<Tool:memory (unbound)>"
        return f"<Tool:memory bound>"
