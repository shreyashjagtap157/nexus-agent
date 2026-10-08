"""Hierarchical scoped memory over the existing MemoryManager."""
from __future__ import annotations

import threading
from enum import Enum
from pathlib import Path
from typing import Any

from nexus_agent.memory.memory_manager import MemoryManager
from nexus_agent.storage.layout import StorageLayout


class MemoryScope(str, Enum):
    GLOBAL = "global"
    USER = "user"
    PROJECT = "project"
    WORKSPACE = "workspace"
    AGENT = "agent"
    TEAM = "team"
    SESSION = "session"


class ScopedMemory:
    """Maintain independent memory stores with explicit scope and precedence."""

    SEARCH_PRECEDENCE = (
        MemoryScope.WORKSPACE,
        MemoryScope.PROJECT,
        MemoryScope.USER,
        MemoryScope.GLOBAL,
        MemoryScope.AGENT,
        MemoryScope.TEAM,
        MemoryScope.SESSION,
    )

    def __init__(
        self,
        layout: StorageLayout,
        *,
        agent_id: str | None = None,
        team_id: str | None = None,
        session_id: str | None = None,
    ):
        self.layout = layout
        self.agent_id = agent_id
        self.team_id = team_id
        self.session_id = session_id
        self._lock = threading.RLock()
        self._managers: dict[MemoryScope, MemoryManager] = {}

    def _path(self, scope: MemoryScope) -> Path:
        if scope == MemoryScope.GLOBAL:
            return self.layout.global_root / "memory"
        if scope == MemoryScope.USER:
            return self.layout.user_memory
        if scope == MemoryScope.PROJECT:
            return self.layout.project_memory
        if scope == MemoryScope.WORKSPACE:
            return self.layout.workspace_memory
        if scope == MemoryScope.AGENT:
            if not self.agent_id:
                raise ValueError("agent_id is required for agent-scoped memory.")
            return self.layout.workspace_runtime / "agents" / self.agent_id / "memory"
        if scope == MemoryScope.TEAM:
            if not self.team_id:
                raise ValueError("team_id is required for team-scoped memory.")
            return self.layout.workspace_runtime / "teams" / self.team_id / "memory"
        if scope == MemoryScope.SESSION:
            if not self.session_id:
                raise ValueError("session_id is required for session-scoped memory.")
            return self.layout.workspace_runtime / "sessions" / self.session_id / "memory"
        raise ValueError(f"Unsupported memory scope: {scope}")

    def manager(self, scope: MemoryScope) -> MemoryManager:
        with self._lock:
            if scope not in self._managers:
                path = self._path(scope)
                path.mkdir(parents=True, exist_ok=True)
                self._managers[scope] = MemoryManager(path)
            return self._managers[scope]

    def store(
        self,
        content: str,
        *,
        scope: MemoryScope = MemoryScope.USER,
        category: str = "general",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        payload = dict(metadata or {})
        payload["memory_scope"] = scope.value
        return self.manager(scope).store(content, category=category, metadata=payload)

    def search(
        self,
        query: str,
        *,
        scopes: list[MemoryScope] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        selected = scopes or list(self.SEARCH_PRECEDENCE)
        results: list[dict[str, Any]] = []
        for scope in selected:
            try:
                matches = self.manager(scope).search(query, limit=limit)
            except (OSError, RuntimeError, ValueError):
                continue
            for item in matches:
                row = dict(item)
                row["scope"] = scope.value
                row["scope_rank"] = len(selected) - selected.index(scope)
                results.append(row)
        # Scope precedence is a tiebreaker after relevance.
        results.sort(
            key=lambda item: (
                float(item.get("score", 0.0)),
                int(item.get("scope_rank", 0)),
            ),
            reverse=True,
        )
        unique: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in results:
            key = (str(item.get("scope")), str(item.get("id")))
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
            if len(unique) >= limit:
                break
        return unique

    def forget(self, entry_id: str, scope: MemoryScope) -> bool:
        return self.manager(scope).forget(entry_id)

    def stats(self) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for scope in MemoryScope:
            try:
                output[scope.value] = self.manager(scope).get_stats()
            except ValueError:
                output[scope.value] = {"available": False}
        return output

    def close(self) -> None:
        with self._lock:
            for manager in self._managers.values():
                manager.close()
            self._managers.clear()
