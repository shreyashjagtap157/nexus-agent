"""Tool surface for explicit scoped memory management."""
from __future__ import annotations

from typing import Any

from nexus_agent.tools.base import Tool

from nexus_agent.memory.scoped import MemoryScope, ScopedMemory


class ScopedMemoryTool(Tool):
    def __init__(self, memory: ScopedMemory):
        self.memory = memory

    @property
    def name(self) -> str:
        return "memory_scoped"

    @property
    def description(self) -> str:
        return (
            "Manage explicit memory scopes: global, user, project, workspace, "
            "agent, team and session. Search respects relevance plus scope precedence."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "action": {"type": "string", "description": "store, search, forget, stats"},
            "scope": {"type": "string", "description": "global, user, project, workspace, agent, team, session"},
            "content": {"type": "string", "description": "Memory content for store"},
            "query": {"type": "string", "description": "Search query"},
            "entry_id": {"type": "string", "description": "Memory ID for forget"},
            "category": {"type": "string", "description": "Memory category"},
            "limit": {"type": "integer", "description": "Result limit", "required": False},
        }

    @property
    def permission_level(self) -> str:
        return "read-write"

    def execute(self, action: str, scope: str = "user", content: str = "", query: str = "", entry_id: str = "", category: str = "general", limit: int = 10, **kwargs: Any) -> str:
        try:
            mode = MemoryScope(scope.lower())
        except ValueError:
            return "Error: invalid memory scope."
        action = action.strip().lower()
        try:
            if action == "store":
                if not content.strip():
                    return "Error: content is required."
                return self.memory.store(content.strip(), scope=mode, category=category)
            if action == "search":
                scopes = [mode] if scope else None
                rows = self.memory.search(query, scopes=scopes, limit=max(1, min(limit, 100)))
                return "\n".join(
                    f"[{item['scope']}] {item.get('id', '')}: {(item.get('content') or '')[:1000]}"
                    for item in rows
                ) or "No matching memories."
            if action == "forget":
                if not entry_id:
                    return "Error: entry_id is required."
                return "Forgot." if self.memory.forget(entry_id, mode) else "Error: memory not found."
            if action == "stats":
                return str(self.memory.stats())
            return "Error: action must be store, search, forget or stats."
        except (OSError, RuntimeError, ValueError) as exc:
            return f"Error: {exc}"
