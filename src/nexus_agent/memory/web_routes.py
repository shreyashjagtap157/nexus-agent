"""Web API for explicit scoped memory."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
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


def register_memory_routes(app: Any, state_manager: Any) -> None:
    router = APIRouter()

    @router.get("/api/memory/scoped/search")
    async def scoped_search(
        scope: MemoryScope = MemoryScope.USER,
        query: str = "",
        limit: int = 20,
    ):
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
    async def scoped_search_post(payload: MemorySearchRequest):
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
    async def scoped_store(payload: MemoryStoreRequest):
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
    async def scoped_stats():
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
