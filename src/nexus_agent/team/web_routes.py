"""FastAPI routes for the unified NexusAgent multi-agent workbench."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
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


logger = logging.getLogger(__name__)


class WorkflowWriteRequest(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    mode: TeamMode = TeamMode.AUTO
    default_agents: int = Field(default=4, ge=1, le=64)
    default_parallelism: int = Field(default=4, ge=1, le=64)
    default_iterations: int = Field(default=30, ge=1, le=500)
    effort_level: str = Field(default="medium", max_length=32)
    require_reviewer: bool = True
    auto_synthesize: bool = True
    allow_parallel_writers: bool = False
    output_mode: str = Field(default="chat", pattern="^(chat|file|both)$")
    output_format: str = Field(default="markdown", pattern="^(markdown|text|json)$")
    research_depth: str = "detailed"
    research_collection: str = "until_saturation"
    research_source_strategy: str = Field(
        default="hybrid", pattern="^(user_only|hybrid|autonomous)$"
    )
    research_max_minutes: int = Field(default=10080, ge=1, le=525600)
    research_idle_rounds: int = Field(default=2, ge=1, le=20)
    agent_ids: list[str] = Field(default_factory=list)
    research_source_urls: list[str] = Field(default_factory=list, max_length=200)
    tags: list[str] = Field(default_factory=list)
    controls: dict[str, Any] = Field(default_factory=dict)
    scope: str = Field(default="workspace", pattern="^(user|workspace)$")


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
    research_source_strategy: str = Field(
        default="hybrid", pattern="^(user_only|hybrid|autonomous)$"
    )
    research_source_urls: list[str] = Field(default_factory=list, max_length=200)
    research_max_minutes: int = Field(default=10080, ge=1, le=525600)
    research_idle_rounds: int = Field(default=2, ge=1, le=20)
    agent_ids: list[str] = Field(default_factory=list)
    use_saved_agents: bool = True


def _workspace(state_manager: Any) -> Path:
    return Path(state_manager.get("workspace") or Path.cwd()).resolve()


def _require_local_client(request: Request) -> None:
    host = request.client.host if request.client else None
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(
            status_code=403, detail="Team data access is restricted to local clients."
        )


def _artifact_root(state_manager: Any, team_id: str) -> Path:
    base = StorageLayout(_workspace(state_manager)).artifacts.resolve()
    root = (base / team_id).resolve()
    try:
        root.relative_to(base)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid team identifier") from exc
    return root


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
        tools = build_workspace_tools(
            workspace, memory_manager, provider=provider, mcp_tools=mcp_tools
        )
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
    async def workflows(request: Request):
        _require_local_client(request)
        return {
            "workflows": [
                workflow.__dict__ for workflow in WorkflowRegistry(_workspace(state_manager)).list()
            ]
        }

    @router.put("/api/workflows/{workflow_id}")
    async def save_workflow(workflow_id: str, request: Request, req: WorkflowWriteRequest):
        _require_local_client(request)
        if workflow_id.strip().lower() != req.id.strip().lower():
            raise HTTPException(status_code=400, detail="Path workflow ID and body ID must match")
        from nexus_agent.workflows.registry import WorkflowSpec

        registry = WorkflowRegistry(_workspace(state_manager))
        candidate = WorkflowSpec.from_dict(req.model_dump(), f"{req.scope}:web")
        path = registry.save(candidate, req.scope)
        return {"workflow": candidate.__dict__, "path": str(path)}

    @router.delete("/api/workflows/{workflow_id}")
    async def delete_workflow(workflow_id: str, request: Request, scope: str = "workspace"):
        _require_local_client(request)
        registry = WorkflowRegistry(_workspace(state_manager))
        if not registry.delete(workflow_id, scope):
            raise HTTPException(status_code=404, detail="Custom workflow not found")
        return {"deleted": workflow_id, "scope": scope}

    @router.get("/api/research-depths")
    async def research_depths(request: Request):
        _require_local_client(request)
        return {"depths": all_policies()}

    @router.get("/api/research-sources")
    async def research_sources(request: Request):
        _require_local_client(request)
        from nexus_agent.research.sources import ResearchSourceRegistry

        registry = ResearchSourceRegistry(
            _workspace(state_manager) / ".nexus-agent" / "research-sources.yaml"
        )
        return {"sources": [item.to_dict() for item in registry.list()]}

    @router.post("/api/research-sources/seed")
    async def seed_research_sources(request: Request, payload: dict[str, Any]):
        _require_local_client(request)
        from nexus_agent.research.sources import ResearchSourceRegistry

        urls = payload.get("urls") if isinstance(payload, dict) else []
        if not isinstance(urls, list):
            raise HTTPException(status_code=422, detail="urls must be a list")
        registry = ResearchSourceRegistry(
            _workspace(state_manager) / ".nexus-agent" / "research-sources.yaml"
        )
        count = registry.seed_urls([str(url) for url in urls])
        return {"seeded": count, "sources": [item.to_dict() for item in registry.list()]}

    @router.get("/api/teams")
    async def list_teams(request: Request, limit: int = 100, offset: int = 0):
        _require_local_client(request)
        store = store_for()
        try:
            return store.list_teams(limit=limit, offset=offset)
        finally:
            store.close()

    @router.post("/api/teams")
    async def start_team(request: Request, req: TeamStartRequest):
        _require_local_client(request)
        if state_manager.get("engine") is None:
            raise HTTPException(status_code=503, detail="No LLM provider is loaded")
        job_id = f"team-{uuid.uuid4().hex}"
        with lock:
            jobs[job_id] = {"status": "queued", "team_id": None, "result": None, "error": None}

        def worker():
            runtime = None
            with lock:
                jobs[job_id]["status"] = "running"
            try:
                runtime = build_runtime()
                workflow = (
                    WorkflowRegistry(_workspace(state_manager)).get(req.workflow_id)
                    if req.workflow_id
                    else None
                )
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
                cfg.research_source_strategy = req.research_source_strategy
                cfg.research_max_minutes = req.research_max_minutes
                cfg.research_idle_rounds = req.research_idle_rounds
                cfg.research_source_urls = req.research_source_urls
                cfg.agent_ids = req.agent_ids
                cfg.use_saved_agents = req.use_saved_agents
                cfg.normalize()

                result = runtime.run_collect(req.goal, cfg)
                with lock:
                    jobs[job_id].update(
                        {
                            "status": "completed" if result.success else "needs_review",
                            "team_id": result.team_id,
                            "result": result.__dict__,
                        }
                    )
            except (RuntimeError, ValueError, OSError, TypeError, KeyError, AttributeError) as exc:
                logger.exception("Team job failed before completion")
                with lock:
                    jobs[job_id].update({"status": "failed", "error": str(exc)})
            finally:
                if runtime is not None:
                    runtime.close()

        threading.Thread(target=worker, name=job_id, daemon=True).start()
        return {"job_id": job_id}

    @router.get("/api/team-history/{team_id}")
    async def team_history(request: Request, team_id: str):
        _require_local_client(request)
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
    async def control_team(team_id: str, request: Request, req: TeamControlRequest):
        _require_local_client(request)
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
    async def team_status(request: Request, job_id: str):
        _require_local_client(request)
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
    async def team_events(request: Request, team_id: str, limit: int = 500, offset: int = 0):
        _require_local_client(request)
        store = store_for()
        try:
            return store.events(team_id, limit=limit, offset=offset)
        finally:
            store.close()

    @router.get("/api/teams/{team_id}/messages")
    async def team_messages(request: Request, team_id: str, recipient_id: str | None = None):
        _require_local_client(request)
        store = store_for()
        try:
            return store.messages(team_id, recipient_id=recipient_id)
        finally:
            store.close()

    @router.get("/api/teams/{team_id}/report")
    async def team_report(request: Request, team_id: str, format: str = "markdown"):
        _require_local_client(request)
        root = _artifact_root(state_manager, team_id)
        if format not in {"markdown", "text", "json"}:
            raise HTTPException(status_code=400, detail="format must be markdown, text or json")

        extension = {"markdown": "result.md", "text": "result.txt", "json": "result.json"}[format]
        artifact = (root / extension).resolve()
        try:
            artifact.relative_to(root)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid report artifact path")
        if artifact.is_file():
            return FileResponse(
                artifact,
                filename=artifact.name,
                media_type={
                    "markdown": "text/markdown",
                    "text": "text/plain",
                    "json": "application/json",
                }[format],
            )

        store = store_for()
        try:
            team = store.team(team_id)
            if team is None:
                raise HTTPException(status_code=404, detail="Unknown team")
            agents = store.agents(team_id)
            events = store.events(team_id, limit=5000)
            quality = {}
            for event in reversed(events):
                if event.get("event_type") == "team_quality_gate":
                    quality = event.get("payload") or {}
                    break
            synthesis = ""
            for event in reversed(events):
                if event.get("event_type") == "team_synthesis":
                    synthesis = str((event.get("payload") or {}).get("content") or "")
                    break
            payload = {
                "team": team,
                "agents": agents,
                "quality": quality,
                "synthesis": synthesis,
                "events": events,
            }
        finally:
            store.close()

        if format == "json":
            return JSONResponse(payload)

        markdown = (
            "# NexusAgent Team Report\n\n"
            + f"Team: `{team_id}`\n\n"
            + "## Goal\n\n"
            + str(payload["team"]["goal"])
            + "\n\n## Synthesis\n\n"
            + (payload["synthesis"] or "No synthesis was persisted.")
            + "\n\n## Quality Gate\n\n"
            + json.dumps(payload["quality"], ensure_ascii=False, indent=2, default=str)
            + "\n\n## Agents\n\n"
            + "\n".join(
                f"- **{item.get('name', item.get('agent_id'))}** — {item.get('profession', '')} — {item.get('state', item.get('status', 'unknown'))}"
                for item in payload["agents"]
            )
            + "\n"
        )
        if format == "text":
            markdown = markdown.replace("# NexusAgent Team Report\n\n", "")
            markdown = markdown.replace("## ", "")
        return PlainTextResponse(
            markdown,
            media_type="text/markdown" if format == "markdown" else "text/plain",
        )

    @router.get("/api/teams/{team_id}/artifacts")
    async def team_artifacts(request: Request, team_id: str):
        _require_local_client(request)
        root = _artifact_root(state_manager, team_id)
        if not root.exists():
            return {"artifacts": []}
        artifacts = []
        for path in sorted(root.rglob("*")):
            resolved = path.resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                continue
            if resolved.is_file():
                artifacts.append(
                    {
                        "name": str(resolved.relative_to(root)),
                        "size": resolved.stat().st_size,
                        "path": str(resolved),
                    }
                )
        return {"team_id": team_id, "artifacts": artifacts}

    @router.get("/api/teams/{team_id}/artifacts/{artifact_path:path}")
    async def download_team_artifact(request: Request, team_id: str, artifact_path: str):
        _require_local_client(request)
        root = _artifact_root(state_manager, team_id)
        target = (root / artifact_path).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid artifact path")
        if not target.is_file():
            raise HTTPException(status_code=404, detail="Artifact not found")
        return FileResponse(target, filename=target.name)

    @router.get("/api/teams/{team_id}/audit")
    async def team_audit(request: Request, team_id: str):
        _require_local_client(request)
        store = store_for()
        try:
            result = store._audit.verify()
            result["records"] = [
                record.to_dict() for record in store._audit.read(run_id=team_id, limit=5000)
            ]
            return result
        finally:
            store.close()

    @router.get("/api/teams/{team_id}/audit/verify")
    async def team_audit_verify(request: Request, team_id: str):
        _require_local_client(request)
        store = store_for()
        try:
            result = store._audit.verify()
            return {
                "team_id": team_id,
                "valid": result.get("valid", False),
                "records": len(store._audit.read(run_id=team_id)),
                "chain_records_total": result.get("records", 0),
                "last_hash": result.get("last_hash"),
            }
        finally:
            store.close()

    @router.get("/api/teams/{team_id}/research")
    async def team_research(request: Request, team_id: str):
        _require_local_client(request)
        research = ResearchStore(StorageLayout(_workspace(state_manager)).research_db)
        return research.export(team_id)

    @router.get("/api/teams/{team_id}/stream")
    async def team_stream(request: Request, team_id: str):
        _require_local_client(request)
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
                if team and team.get("status") in {
                    "completed",
                    "needs_review",
                    "failed",
                    "cancelled",
                }:
                    yield f"data: {json.dumps({'type': 'terminal', 'status': team['status']})}\n\n"
                    return
                await asyncio.sleep(0.5)

        return StreamingResponse(
            generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    app.include_router(router)
