"""Web API for configurable and generated agent profiles."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
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
    async def save_agent(agent_id: str, request: Request, payload: AgentWriteRequest):
        if request.client and request.client.host not in {"127.0.0.1", "::1", "localhost"}:
            raise HTTPException(status_code=403, detail="Agent mutation is restricted to local clients.")
        if agent_id.strip().lower() != payload.id.strip().lower():
            raise HTTPException(status_code=400, detail="Path agent ID and body ID must match")
        registry = _registry(state_manager)
        spec = AgentSpec.from_dict(payload.model_dump(), payload.scope)
        errors = registry.validate(spec)
        if errors:
            raise HTTPException(status_code=422, detail=errors)
        path = registry.save(spec, payload.scope)
        return {"agent": spec.to_dict(), "path": str(path)}

    @router.delete("/api/agents/{agent_id}")
    async def delete_agent(agent_id: str, request: Request, scope: AgentScope | None = None):
        if request.client and request.client.host not in {"127.0.0.1", "::1", "localhost"}:
            raise HTTPException(status_code=403, detail="Agent mutation is restricted to local clients.")
        removed = _registry(state_manager).delete(agent_id, scope)
        if not removed:
            raise HTTPException(status_code=404, detail="No persisted definition found")
        return {"removed": removed}

    @router.post("/api/agents/generate")
    async def generate_agents(request: Request, payload: AgentGenerateRequest):
        if request.client and request.client.host not in {"127.0.0.1", "::1", "localhost"}:
            raise HTTPException(status_code=403, detail="Agent mutation is restricted to local clients.")
        provider = state_manager.get("engine")
        workspace = Path(state_manager.get("workspace") or Path.cwd()).resolve()
        config = state_manager.get("config") or load_config(workspace=workspace)
        if provider is None:
            provider_name = payload.provider or config.get("providers", {}).get("active", "local")
            provider = ProviderFactory.create_provider(provider_name, config, payload.model)
        specs = AgentGenerator(provider).generate(payload.request, max_agents=payload.max_agents)
        registry = AgentRegistry(workspace)
        paths = []
        for spec in specs:
            errors = registry.validate(spec)
            if errors:
                raise HTTPException(status_code=422, detail={spec.id: errors})
            paths.append(str(registry.save(spec, payload.scope)))
        return {"agents": [spec.to_dict() for spec in specs], "paths": paths}

    app.include_router(router)
