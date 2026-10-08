"""Unified local audit-log endpoints."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from nexus_agent.audit import AuditLog
from nexus_agent.storage.layout import StorageLayout


def register_audit_routes(app: Any, state_manager: Any) -> None:
    router = APIRouter()

    def _require_local(request: Request) -> None:
        host = request.client.host if request.client else None
        if host not in {"127.0.0.1", "::1", "localhost"}:
            raise HTTPException(status_code=403, detail="Audit access is restricted to local clients.")

    def audit() -> AuditLog:
        workspace = Path(state_manager.get("workspace") or Path.cwd()).resolve()
        return AuditLog(StorageLayout(workspace).workspace_runtime / "audit.jsonl")

    @router.get("/api/audit/verify")
    async def audit_verify(request: Request):
        _require_local(request)
        return audit().verify()

    @router.get("/api/audit/records")
    async def audit_records(request: Request, run_id: str | None = None, limit: int = 500):
        _require_local(request)
        log = audit()
        return {
            "records": [
                item.to_dict()
                for item in log.read(run_id=run_id, limit=max(1, min(limit, 5000)))
            ]
        }

    app.include_router(router)
