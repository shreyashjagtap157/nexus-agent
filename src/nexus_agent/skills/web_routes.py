"""Web catalog for reusable NexusAgent skills."""
from __future__ import annotations

from pathlib import Path
from typing import Any

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
    async def list_skills():
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
