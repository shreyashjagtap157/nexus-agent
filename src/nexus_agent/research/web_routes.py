"""Web management API for user-configured research sources."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

from nexus_agent.research.sources import ResearchSource, ResearchSourceRegistry


class SourceRequest(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    url: str = Field(min_length=1, max_length=10000)
    name: str = Field(default="", max_length=500)
    source_type: str = Field(default="web", max_length=32)
    priority: int = Field(default=50, ge=0, le=1000)
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)
    notes: str = Field(default="", max_length=10000)


def _require_local(request: Request) -> None:
    host = request.client.host if request.client else None
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(status_code=403, detail="Research source access is restricted to local clients.")


def register_research_source_routes(app: Any, state_manager: Any) -> None:
    def registry() -> ResearchSourceRegistry:
        workspace = Path(state_manager.get("workspace") or Path.cwd()).resolve()
        return ResearchSourceRegistry(workspace / ".nexus-agent" / "research-sources.yaml")

    @app.get("/api/research/sources")
    async def list_research_sources(request: Request, enabled_only: bool = False):
        _require_local(request)
        return {"sources": [source.to_dict() for source in registry().list(enabled_only=enabled_only)]}

    @app.post("/api/research/sources")
    async def add_research_source(request: Request, payload: SourceRequest):
        _require_local(request)
        source = ResearchSource(**payload.model_dump())
        saved = registry().add(source)
        return {"source": saved.to_dict()}

    @app.get("/api/research/sources/{source_id}")
    async def get_research_source(source_id: str, request: Request):
        _require_local(request)
        source = registry().get(source_id)
        if source is None:
            raise HTTPException(status_code=404, detail="Research source not found")
        return source.to_dict()

    @app.put("/api/research/sources/{source_id}")
    async def update_research_source(source_id: str, request: Request, payload: SourceRequest):
        _require_local(request)
        if source_id.strip().lower() != payload.id.strip().lower():
            raise HTTPException(status_code=400, detail="Path source ID and body ID must match")
        saved = registry().add(ResearchSource(**payload.model_dump()))
        return {"source": saved.to_dict()}

    @app.delete("/api/research/sources/{source_id}")
    async def delete_research_source(source_id: str, request: Request):
        _require_local(request)
        removed = registry().remove(source_id)
        return {"removed": removed}
