"""Web API for explicit scoped memory."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from nexus_agent.memory.scoped import MemoryScope, ScopedMemory
from nexus_agent.storage.layout import StorageLayout


class MemoryStoreRequest(BaseModel):
    scope: MemoryScope = MemoryScope.USER
    content: str = Field(min_length=1, max_length=200000)
    category: str = Field(default="general", max_length=200)
    agent_id: str | None = None
    team_id: str | None = None
    session_id: str | None = None


class MemorySearchRequest(BaseModel):
    scope: MemoryScope = MemoryScope.USER
    query: str = Field(default="", max_length=20000)
    limit: int = Field(default=20, ge=1, le=200)
    agent_id: str | None = None
    team_id: str | None = None
    session_id: str | None = None


def _memory(state_manager: Any, payload: MemoryStoreRequest | MemorySearchRequest):
    workspace = Path(state_manager.get("workspace") or Path.cwd()).resolve()
    return ScopedMemory(
        StorageLayout(workspace),
        agent_id=payload.agent_id,
        team_id=payload.team_id,
        session_id=payload.session_id,
    )


def _require_local(request: Request) -> None:
    host = request.client.host if request.client else None
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(status_code=403, detail="Scoped memory access is restricted to local clients.")


def register_memory_routes(app: Any, state_manager: Any) -> None:
    router = APIRouter()

    @router.get("/api/memory/scoped/search")
    async def scoped_search(
        request: Request,
        scope: MemoryScope = MemoryScope.USER,
        query: str = "",
        limit: int = 20,
    ):
        _require_local(request)
        class Payload:
            agent_id = None
            team_id = None
            session_id = None
        memory = _memory(state_manager, Payload())
        try:
            return {"scope": scope.value, "results": memory.search(query, scopes=[scope], limit=max(1, min(limit, 200)))}
        finally:
            memory.close()

    @router.post("/api/memory/scoped/search")
    async def scoped_search_post(request: Request, payload: MemorySearchRequest):
        _require_local(request)
        memory = _memory(state_manager, payload)
        try:
            return {
                "scope": payload.scope.value,
                "results": memory.search(
                    payload.query,
                    scopes=[payload.scope],
                    limit=payload.limit,
                ),
            }
        finally:
            memory.close()

    @router.post("/api/memory/scoped/store")
    async def scoped_store(request: Request, payload: MemoryStoreRequest):
        _require_local(request)
        memory = _memory(state_manager, payload)
        try:
            entry_id = memory.store(
                payload.content,
                scope=payload.scope,
                category=payload.category,
            )
            return {"id": entry_id, "scope": payload.scope.value}
        finally:
            memory.close()

    @router.get("/api/memory/scoped/stats")
    async def scoped_stats(request: Request):
        _require_local(request)
        class Payload:
            agent_id = None
            team_id = None
            session_id = None
        memory = _memory(state_manager, Payload())
        try:
            return memory.stats()
        finally:
            memory.close()

    app.include_router(router)
