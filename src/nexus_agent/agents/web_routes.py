"""Web API for configurable and generated agent profiles."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from nexus_agent.agents import AgentGenerator, AgentRegistry, AgentScope, AgentSpec
from nexus_agent.core.config import load_config
from nexus_agent.llm.providers.factory import ProviderFactory


class AgentWriteRequest(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    profession: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    mission: str = Field(min_length=1, max_length=4000)
    instructions: str = Field(min_length=1, max_length=20000)
    scope: AgentScope = AgentScope.WORKSPACE
    enabled: bool = True
    tool_categories: list[str] = Field(default_factory=lambda: ["read", "search"])
    write_access: bool = False
    reviewer: bool = False
    dependencies: list[str] = Field(default_factory=list)
    model_role: str = "default"
    provider: str | None = None
    model: str | None = None
    fallbacks: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class AgentGenerateRequest(BaseModel):
    request: str = Field(min_length=1, max_length=100000)
    max_agents: int = Field(default=6, ge=1, le=32)
    scope: AgentScope = AgentScope.WORKSPACE
    provider: str | None = None
    model: str | None = None


def _registry(state_manager: Any) -> AgentRegistry:
    workspace = Path(state_manager.get("workspace") or Path.cwd()).resolve()
    return AgentRegistry(workspace)


def register_agent_routes(app: Any, state_manager: Any) -> None:
    router = APIRouter()

    @router.get("/api/agents")
    async def list_agents(include_disabled: bool = False):
        return {
            "roots": _registry(state_manager).roots_info(),
            "agents": [item.to_dict() for item in _registry(state_manager).load(include_disabled=include_disabled)],
        }

    @router.get("/api/agents/{agent_id}")
    async def get_agent(agent_id: str):
        spec = _registry(state_manager).get(agent_id)
        if spec is None:
            raise HTTPException(status_code=404, detail="Unknown or disabled agent")
        return spec.to_dict()

    @router.put("/api/agents/{agent_id}")
    async def save_agent(agent_id: str, request: AgentWriteRequest):
        if agent_id.strip().lower() != request.id.strip().lower():
            raise HTTPException(status_code=400, detail="Path agent ID and body ID must match")
        registry = _registry(state_manager)
        spec = AgentSpec.from_dict(request.model_dump(), request.scope)
        errors = registry.validate(spec)
        if errors:
            raise HTTPException(status_code=422, detail=errors)
        path = registry.save(spec, request.scope)
        return {"agent": spec.to_dict(), "path": str(path)}

    @router.delete("/api/agents/{agent_id}")
    async def delete_agent(agent_id: str, scope: AgentScope | None = None):
        removed = _registry(state_manager).delete(agent_id, scope)
        if not removed:
            raise HTTPException(status_code=404, detail="No persisted definition found")
        return {"removed": removed}

    @router.post("/api/agents/generate")
    async def generate_agents(request: AgentGenerateRequest):
        provider = state_manager.get("engine")
        workspace = Path(state_manager.get("workspace") or Path.cwd()).resolve()
        config = state_manager.get("config") or load_config(workspace=workspace)
        if provider is None:
            provider_name = request.provider or config.get("providers", {}).get("active", "local")
            provider = ProviderFactory.create_provider(provider_name, config, request.model)
        specs = AgentGenerator(provider).generate(request.request, max_agents=request.max_agents)
        registry = AgentRegistry(workspace)
        paths = []
        for spec in specs:
            errors = registry.validate(spec)
            if errors:
                raise HTTPException(status_code=422, detail={spec.id: errors})
            paths.append(str(registry.save(spec, request.scope)))
        return {"agents": [spec.to_dict() for spec in specs], "paths": paths}

    app.include_router(router)
