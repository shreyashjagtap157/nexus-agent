"""Agent tool for managing the persistent research source registry."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from nexus_agent.tools.base import Tool

from .sources import ResearchSource, ResearchSourceRegistry


class ResearchSourceTool(Tool):
    def __init__(self, path: Path):
        self.registry = ResearchSourceRegistry(path)

    @property
    def name(self) -> str:
        return "research_sources"

    @property
    def description(self) -> str:
        return "List, add or remove user-configured trusted research sources and seed URLs for the current workspace."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "action": {"type": "string", "description": "list, add, remove or seed"},
            "source_id": {"type": "string", "description": "Source identifier for remove"},
            "url": {"type": "string", "description": "Source URL for add"},
            "name": {"type": "string", "description": "Human-readable source name", "required": False},
            "source_type": {"type": "string", "description": "web, paper, standard, repository, documentation, api", "required": False},
            "priority": {"type": "integer", "description": "Priority 0-100", "required": False},
            "tags": {"type": "array", "description": "Source tags", "required": False},
            "urls": {"type": "array", "description": "URLs for seed action", "required": False},
        }

    @property
    def permission_level(self) -> str:
        return "read-write"

    def execute(
        self,
        action: str,
        source_id: str = "",
        url: str = "",
        name: str = "",
        source_type: str = "web",
        priority: int = 50,
        tags: list[str] | None = None,
        urls: list[str] | None = None,
        **kwargs: Any,
    ) -> str:
        action = action.strip().lower()
        if action == "list":
            return str([source.to_dict() for source in self.registry.list(enabled_only=True)])
        if action == "add":
            source = ResearchSource(
                id=source_id.strip().lower() or "custom-source",
                url=url.strip(),
                name=name.strip(),
                source_type=source_type.strip(),
                priority=max(0, min(int(priority), 100)),
                tags=tags or [],
            )
            self.registry.add(source)
            return f"Saved research source {source.id}."
        if action == "remove":
            return "Removed." if self.registry.remove(source_id) else "Source not found."
        if action == "seed":
            count = self.registry.seed_urls(urls or [])
            return f"Seeded {count} source URL(s)."
        return "Error: action must be list, add, remove or seed."
