"""Canonical filesystem layout for NexusAgent state."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import platformdirs

from nexus_agent.core.config import APP_NAME, get_data_dir


@dataclass(frozen=True)
class StorageLayout:
    """Resolve every persistent NexusAgent surface to an explicit scope."""

    workspace: Path
    project_root: Path | None = None

    @property
    def user_root(self) -> Path:
        return get_data_dir()

    @property
    def global_root(self) -> Path:
        return Path(platformdirs.site_data_dir(APP_NAME)).resolve()

    @property
    def project(self) -> Path:
        if self.project_root is not None:
            return self.project_root.resolve()
        current = self.workspace.resolve()
        for candidate in (current, *current.parents):
            if (candidate / ".git").exists() or (candidate / "pyproject.toml").exists():
                return candidate
        return current

    @property
    def workspace_root(self) -> Path:
        return self.workspace.resolve()

    @property
    def user_agents(self) -> Path:
        return self.user_root / "agents"

    @property
    def global_agents(self) -> Path:
        return self.global_root / "agents"

    @property
    def project_agents(self) -> Path:
        return self.project / "agents"

    @property
    def workspace_agents(self) -> Path:
        return self.workspace_root / ".nexus-agent" / "agents"

    @property
    def user_memory(self) -> Path:
        return self.user_root / "memory"

    @property
    def project_memory(self) -> Path:
        return self.project / ".nexus-agent" / "memory"

    @property
    def workspace_memory(self) -> Path:
        return self.workspace_root / ".nexus-agent" / "workspace-memory"

    @property
    def sessions(self) -> Path:
        return self.user_root / "sessions"

    @property
    def auth_file(self) -> Path:
        return self.user_root / "auth.json"

    @property
    def caches(self) -> Path:
        return self.user_root / "cache"

    @property
    def logs(self) -> Path:
        return self.user_root / "logs"

    @property
    def workspace_runtime(self) -> Path:
        return self.workspace_root / ".nexus-agent" / "runtime"

    @property
    def team_db(self) -> Path:
        return self.workspace_runtime / "teams.db"

    @property
    def research_db(self) -> Path:
        return self.workspace_runtime / "research.db"

    @property
    def artifacts(self) -> Path:
        return self.workspace_runtime / "artifacts"

    @property
    def trash(self) -> Path:
        return self.workspace_runtime / "trash"

    @property
    def todos(self) -> Path:
        return self.workspace_runtime / "todos.json"

    def ensure(self) -> None:
        for path in (
            self.user_root,
            self.user_agents,
            self.user_memory,
            self.sessions,
            self.caches,
            self.logs,
            self.workspace_runtime,
            self.workspace_agents,
            self.workspace_memory,
            self.artifacts,
            self.trash,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def describe(self) -> dict[str, str]:
        return {
            "global": str(self.global_root),
            "user": str(self.user_root),
            "project": str(self.project),
            "workspace": str(self.workspace_root),
            "user_agents": str(self.user_agents),
            "global_agents": str(self.global_agents),
            "project_agents": str(self.project_agents),
            "workspace_agents": str(self.workspace_agents),
            "user_memory": str(self.user_memory),
            "project_memory": str(self.project_memory),
            "workspace_memory": str(self.workspace_memory),
            "sessions": str(self.sessions),
            "auth": str(self.auth_file),
            "runtime": str(self.workspace_runtime),
            "artifacts": str(self.artifacts),
            "trash": str(self.trash),
        }
