"""Web catalog for reusable NexusAgent skills."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request

from nexus_agent.skills import SkillRegistry


def register_skill_routes(app: Any, state_manager: Any) -> None:
    workspace = Path(state_manager.get("workspace") or Path.cwd()).resolve()
    registry = SkillRegistry(
        search_dirs=[
            str(workspace / ".nexus-agent" / "skills"),
        ],
        workspace=workspace,
    )

    @app.get("/api/skills")
    async def list_skills(request: Request):
        if request.client and request.client.host not in {"127.0.0.1", "::1", "localhost"}:
            raise HTTPException(status_code=403, detail="Workspace skill access is restricted to local clients.")
        skills = registry.discover_skills()
        return {
            "skills": [
                {
                    "id": skill.name,
                    "name": skill.name,
                    "description": skill.description,
                    "permission_level": skill.permission_level,
                    "parameters": skill.parameters,
                }
                for skill in skills
            ]
        }
