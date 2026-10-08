"""Hierarchical agent registry with explicit scope precedence."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import platformdirs
import yaml

from nexus_agent.core.config import APP_NAME, get_data_dir

from .format import parse_agent_file, write_agent_file
from .models import AgentScope, AgentSpec

logger = logging.getLogger(__name__)

_PRECEDENCE = [
    AgentScope.BUILTIN,
    AgentScope.GLOBAL,
    AgentScope.USER,
    AgentScope.PROJECT,
    AgentScope.WORKSPACE,
]


class AgentRegistry:
    """Load, resolve, persist and remove Markdown agent definitions."""

    def __init__(
        self,
        workspace: Path | None = None,
        project_root: Path | None = None,
        global_root: Path | None = None,
        user_root: Path | None = None,
    ) -> None:
        self.workspace = (workspace or Path.cwd()).resolve()
        self.project_root = (project_root or self._discover_project(self.workspace)).resolve()
        self.roots: dict[AgentScope, Path] = {
            AgentScope.BUILTIN: Path(__file__).parent / "builtin",
            AgentScope.GLOBAL: Path(global_root or platformdirs.site_data_dir(APP_NAME)) / "agents",
            AgentScope.USER: Path(user_root or get_data_dir()) / "agents",
            AgentScope.PROJECT: self.project_root / "agents",
            AgentScope.WORKSPACE: self.workspace / ".nexus-agent" / "agents",
        }

    @staticmethod
    def _discover_project(workspace: Path) -> Path:
        current = workspace
        for candidate in (current, *current.parents):
            if (candidate / ".git").exists() or (candidate / "pyproject.toml").exists():
                return candidate
        return workspace

    def roots_info(self) -> dict[str, str]:
        return {scope.value: str(path) for scope, path in self.roots.items()}

    def _iter_files(self, scope: AgentScope) -> Iterable[Path]:
        root = self.roots[scope]
        if not root.exists():
            return ()
        return sorted(root.glob("*.md"), key=lambda p: p.name.lower())

    def load(self, include_disabled: bool = False) -> list[AgentSpec]:
        merged: dict[str, AgentSpec] = {}
        for scope in _PRECEDENCE:
            for path in self._iter_files(scope):
                try:
                    spec = parse_agent_file(path, scope)
                except (OSError, ValueError, yaml.YAMLError) as exc:
                    logger.warning("Skipping invalid agent file %s: %s", path, exc)
                    continue
                if include_disabled or spec.enabled:
                    merged[spec.id] = spec
                elif spec.id in merged:
                    del merged[spec.id]
        return list(sorted(merged.values(), key=lambda item: (item.name.lower(), item.id)))

    def get(self, agent_id: str) -> AgentSpec | None:
        normalized = agent_id.strip().lower()
        return next((spec for spec in self.load(include_disabled=True) if spec.id == normalized and spec.enabled), None)

    def save(self, spec: AgentSpec, scope: AgentScope) -> Path:
        if scope == AgentScope.BUILTIN:
            raise ValueError("Built-in agent profiles are immutable.")
        root = self.roots[scope]
        spec.scope = scope
        path = root / f"{spec.id}.md"
        return write_agent_file(path, spec)

    def delete(self, agent_id: str, scope: AgentScope | None = None) -> list[str]:
        removed: list[str] = []
        mutable_scopes = [AgentScope.GLOBAL, AgentScope.USER, AgentScope.PROJECT, AgentScope.WORKSPACE]
        scopes = [scope] if scope is not None else list(reversed(mutable_scopes))
        if scope == AgentScope.BUILTIN:
            raise ValueError("Built-in agent profiles are immutable.")
        for item_scope in scopes:
            path = self.roots[item_scope] / f"{agent_id.strip().lower()}.md"
            try:
                path.unlink()
                removed.append(str(path))
            except FileNotFoundError:
                pass
        return removed

    def resolve_tool_categories(self, agent: AgentSpec) -> set[str]:
        allowed = {
            "read", "write", "shell", "web", "git", "mcp",
            "browser", "code_intel", "lsp", "memory", "research",
        }
        requested = set(agent.tool_categories)
        return requested & allowed

    def validate(self, spec: AgentSpec) -> list[str]:
        errors: list[str] = []
        if spec.id != spec.id.strip().lower() or not spec.id.replace("-", "").replace("_", "").isalnum():
            errors.append("id must contain only lowercase letters, numbers, '-' or '_'.")
        if not spec.tool_categories:
            errors.append("tool_categories must contain at least one category.")
        if spec.write_access and "write" not in spec.tool_categories:
            errors.append("write_access=true requires the 'write' tool category.")
        return errors
