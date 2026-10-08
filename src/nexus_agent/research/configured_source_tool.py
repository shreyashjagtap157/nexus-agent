"""Explicit configured-source research tool."""
from __future__ import annotations

from typing import Any

from nexus_agent.tools.base import Tool
from nexus_agent.tools.webfetch import WebFetchTool

from .sources import ResearchSourceRegistry
from .store import ResearchStore


class ResearchConfiguredSourceTool(Tool):
    """List/fetch only user-registered research sources."""

    def __init__(self, registry_path, research_db, team_id: str, agent_id: str):
        self.registry = ResearchSourceRegistry(registry_path)
        self.store = ResearchStore(research_db)
        self.team_id = team_id
        self.agent_id = agent_id
        self.fetcher = WebFetchTool()

    @property
    def name(self) -> str:
        return "research_configured_source"

    @property
    def description(self) -> str:
        return (
            "Use only configured research sources. Actions: list or fetch. "
            "Fetch records the exact returned source text in the evidence ledger."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "action": {"type": "string", "description": "list or fetch"},
            "source_id": {"type": "string", "description": "Configured source ID for fetch"},
        }

    @property
    def permission_level(self) -> str:
        return "read-only"

    def execute(self, action: str, source_id: str = "", **kwargs: Any) -> Any:
        mode = action.strip().lower()
        if mode == "list":
            return [
                source.to_dict()
                for source in self.registry.list(enabled_only=True)
            ]
        if mode != "fetch":
            return "Error: action must be list or fetch."
        source = self.registry.get(source_id)
        if source is None or not source.enabled:
            return "Error: configured research source not found or disabled."
        result = self.fetcher.execute(source.url)
        if result.startswith("Error:"):
            return result
        record = self.store.record_source(
            self.team_id,
            self.agent_id,
            source.url,
            source.name or source.url,
            result,
            provider="configured",
        )
        return {
            "source": source.to_dict(),
            "record": record,
            "content": result,
        }
