"""FastAPI routes for the unified NexusAgent multi-agent workbench."""
from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from nexus_agent.core.config import load_config
from nexus_agent.permissions.manager import PermissionManager
from nexus_agent.storage.layout import StorageLayout
from nexus_agent.mcp.client import load_configured_servers
from nexus_agent.research.store import ResearchStore

from .models import TeamConfig, TeamMode
from .control import control as control_team_request
from .providers import make_provider_selector
from .research import all_policies
from .runtime import TeamRuntime, build_workspace_tools
from nexus_agent.workflows import WorkflowRegistry
from .store import TeamStore


class TeamControlRequest(BaseModel):
    action: str = Field(pattern="^(pause|resume|stop)$")


class TeamStartRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=100000)
    workflow_id: str | None = None
    mode: TeamMode = TeamMode.AUTO
    max_agents: int = Field(default=6, ge=1, le=64)
    parallelism: int = Field(default=4, ge=1, le=32)
    max_iterations_per_agent: int = Field(default=30, ge=1, le=500)
    effort_level: str = Field(default="medium", max_length=32)
    output_mode: str = Field(default="chat", pattern="^(chat|file|both)$")
    output_format: str = Field(default="markdown", pattern="^(markdown|text|json)$")
    auto_synthesize: bool = True
    require_reviewer: bool = True
    auto_approve_tools: bool = False
    research_depth: str = "detailed"
    research_collection: str = "until_saturation"
    agent_ids: list[str] = Field(default_factory=list)
    use_saved_agents: bool = True


def _workspace(state_manager: Any) -> Path:
    return Path(state_manager.get("workspace") or Path.cwd()).resolve()


def register_team_routes(app: Any, state_manager: Any) -> None:
    router = APIRouter()
    jobs: dict[str, dict[str, Any]] = {}
    lock = threading.RLock()

    def store_for() -> TeamStore:
        return TeamStore(StorageLayout(_workspace(state_manager)).team_db)

    def build_runtime() -> TeamRuntime:
        provider = state_manager.get("engine")
        if provider is None:
            raise HTTPException(status_code=503, detail="No LLM provider is loaded")
        workspace = _workspace(state_manager)
        memory_manager = state_manager.get("memory_manager")
        config = state_manager.get("config") or {}
        mcp_clients, mcp_tools = load_configured_servers(config)
        tools = build_workspace_tools(workspace, memory_manager, provider=provider, mcp_tools=mcp_tools)
        permission_manager = PermissionManager()
        permission_manager.load_from_config(state_manager.get("config") or {})
        return TeamRuntime(
            provider,
            tools,
            workspace=workspace,
            data_dir=StorageLayout(workspace).workspace_runtime,
            permission_callback=lambda tc: permission_manager.check_and_approve(
                tool_name=tc.name,
                arguments=tc.arguments,
                description=f"Team worker requesting {tc.name}",
            ),
            provider_selector=make_provider_selector(
                state_manager.get("config") or {},
                provider,
            ),
            mcp_clients=mcp_clients,
        )

    @router.get("/api/workflows")
    async def workflows():
        return {"workflows": [workflow.__dict__ for workflow in WorkflowRegistry().list()]}

    @router.get("/api/research-depths")
    async def research_depths():
        return {"depths": all_policies()}

    @router.get("/api/teams")
    async def list_teams(limit: int = 100, offset: int = 0):
        store = store_for()
        try:
            return store.list_teams(limit=limit, offset=offset)
        finally:
            store.close()

    @router.post("/api/teams")
    async def start_team(req: TeamStartRequest):
        if state_manager.get("engine") is None:
            raise HTTPException(status_code=503, detail="No LLM provider is loaded")
        job_id = f"team-{int(time.time() * 1000)}"
        with lock:
            jobs[job_id] = {"status": "queued", "team_id": None, "result": None, "error": None}

        def worker():
            runtime = build_runtime()
            workflow = WorkflowRegistry().get(req.workflow_id) if req.workflow_id else None
            cfg = (workflow.configure() if workflow else TeamConfig(mode=req.mode)).normalize()
            cfg.workflow_id = req.workflow_id or ""
            cfg.mode = req.mode if not req.workflow_id else cfg.mode
            cfg.max_agents = req.max_agents
            cfg.parallelism = req.parallelism
            cfg.max_iterations_per_agent = req.max_iterations_per_agent
            cfg.workspace = str(_workspace(state_manager))
            cfg.effort_level = req.effort_level
            cfg.output_mode = req.output_mode
            cfg.output_format = req.output_format
            cfg.auto_synthesize = req.auto_synthesize
            cfg.require_reviewer = req.require_reviewer
            cfg.auto_approve_tools = req.auto_approve_tools
            cfg.research_depth = req.research_depth
            cfg.research_collection = req.research_collection
            cfg.agent_ids = req.agent_ids
            cfg.use_saved_agents = req.use_saved_agents
            cfg.normalize()
            with lock:
                jobs[job_id]["status"] = "running"
            try:
                result = runtime.run_collect(req.goal, cfg)
                with lock:
                    jobs[job_id].update({
                        "status": "completed" if result.success else "needs_review",
                        "team_id": result.team_id,
                        "result": result.__dict__,
                    })
            except Exception as exc:
                with lock:
                    jobs[job_id].update({"status": "failed", "error": str(exc)})

        threading.Thread(target=worker, name=job_id, daemon=True).start()
        return {"job_id": job_id}

    @router.get("/api/team-history/{team_id}")
    async def team_history(team_id: str):
        store = store_for()
        try:
            team = store.team(team_id)
            if team is None:
                raise HTTPException(status_code=404, detail="Unknown team")
            return {
                "team": team,
                "agents": store.agents(team_id),
                "messages": store.messages(team_id),
                "events": store.events(team_id, limit=5000),
            }
        finally:
            store.close()

    @router.post("/api/teams/{team_id}/control")
    async def control_team(team_id: str, req: TeamControlRequest):
        store = store_for()
        try:
            accepted = store.request_control(team_id, req.action)
            if not accepted:
                raise HTTPException(status_code=409, detail="Team is terminal or unknown")
            control_team_request(team_id, req.action)
            store.event(team_id, "team_control", {"action": req.action})
            return {"team_id": team_id, "action": req.action, "accepted": True}
        finally:
            store.close()

    @router.get("/api/teams/{job_id}")
    async def team_status(job_id: str):
        with lock:
            job = dict(jobs.get(job_id) or {})
        if not job:
            raise HTTPException(status_code=404, detail="Unknown team job")
        if job.get("team_id"):
            store = store_for()
            try:
                return {
                    **job,
                    "team": store.team(job["team_id"]),
                    "agents": store.agents(job["team_id"]),
                    "messages": store.messages(job["team_id"]),
                    "events": store.events(job["team_id"], limit=500),
                }
            finally:
                store.close()
        return job

    @router.get("/api/teams/{team_id}/events")
    async def team_events(team_id: str, limit: int = 500, offset: int = 0):
        store = store_for()
        try:
            return store.events(team_id, limit=limit, offset=offset)
        finally:
            store.close()

    @router.get("/api/teams/{team_id}/messages")
    async def team_messages(team_id: str, recipient_id: str | None = None):
        store = store_for()
        try:
            return store.messages(team_id, recipient_id=recipient_id)
        finally:
            store.close()

    @router.get("/api/teams/{team_id}/research")
    async def team_research(team_id: str):
        research = ResearchStore(StorageLayout(_workspace(state_manager)).research_db)
        return research.export(team_id)

    @router.get("/api/teams/{team_id}/stream")
    async def team_stream(team_id: str):
        workspace = _workspace(state_manager)

        async def generator():
            offset = 0
            idle = 0
            while idle < 2400:
                store = TeamStore(StorageLayout(workspace).team_db)
                try:
                    batch = store.events(team_id, limit=250, offset=offset)
                    team = store.team(team_id)
                finally:
                    store.close()
                if batch:
                    idle = 0
                    offset += len(batch)
                    for event in batch:
                        yield f"data: {json.dumps(event, default=str)}\n\n"
                else:
                    idle += 1
                if team and team.get("status") in {"completed", "needs_review", "failed", "cancelled"}:
                    yield f"data: {json.dumps({'type': 'terminal', 'status': team['status']})}\n\n"
                    return
                await asyncio.sleep(0.5)

        return StreamingResponse(
            generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    app.include_router(router)
