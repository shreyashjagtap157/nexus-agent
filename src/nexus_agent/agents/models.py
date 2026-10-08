"""Typed agent profile models and scope semantics."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentScope(str, Enum):
    BUILTIN = "builtin"
    GLOBAL = "global"
    USER = "user"
    PROJECT = "project"
    WORKSPACE = "workspace"


@dataclass
class AgentSpec:
    id: str
    name: str
    profession: str
    description: str
    mission: str
    instructions: str
    scope: AgentScope = AgentScope.USER
    enabled: bool = True
    tool_categories: list[str] = field(default_factory=lambda: ["read"])
    write_access: bool = False
    reviewer: bool = False
    dependencies: list[str] = field(default_factory=list)
    model_role: str = "default"
    provider: str | None = None
    model: str | None = None
    fallbacks: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    skill_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "profession": self.profession,
            "description": self.description,
            "mission": self.mission,
            "instructions": self.instructions,
            "scope": self.scope.value,
            "enabled": self.enabled,
            "tool_categories": list(self.tool_categories),
            "write_access": self.write_access,
            "reviewer": self.reviewer,
            "dependencies": list(self.dependencies),
            "model_role": self.model_role,
            "provider": self.provider,
            "model": self.model,
            "fallbacks": list(self.fallbacks),
            "tags": list(self.tags),
            "skill_ids": list(self.skill_ids),
            "metadata": dict(self.metadata),
            "source_path": self.source_path,
        }

    def to_team_profile(self):
        from nexus_agent.team.models import AgentProfile
        return AgentProfile(
            role_id=self.id,
            name=self.name,
            profession=self.profession,
            mission=self.mission,
            instructions=self.instructions,
            tool_categories=list(self.tool_categories),
            write_access=self.write_access,
            reviewer=self.reviewer,
            dependencies=list(self.dependencies),
            model_role=self.model_role,
            provider=self.provider,
            model=self.model,
            fallbacks=list(self.fallbacks),
            skill_ids=list(self.skill_ids),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any], scope: AgentScope, source_path: str | None = None) -> "AgentSpec":
        identifier = str(data.get("id") or "").strip().lower()
        if not identifier:
            raise ValueError("Agent definition requires a non-empty id.")
        if not all(str(data.get(key) or "").strip() for key in ("name", "profession", "mission", "instructions")):
            raise ValueError(f"Agent {identifier!r} is missing required descriptive fields.")
        return cls(
            id=identifier,
            name=str(data["name"]).strip(),
            profession=str(data["profession"]).strip(),
            description=str(data.get("description") or "").strip(),
            mission=str(data["mission"]).strip(),
            instructions=str(data["instructions"]).strip(),
            scope=scope,
            enabled=bool(data.get("enabled", True)),
            tool_categories=[str(x).strip() for x in data.get("tool_categories", ["read"]) if str(x).strip()],
            write_access=bool(data.get("write_access", False)),
            reviewer=bool(data.get("reviewer", False)),
            dependencies=[str(x).strip().lower() for x in data.get("dependencies", []) if str(x).strip()],
            model_role=str(data.get("model_role") or identifier),
            provider=str(data["provider"]).strip() if data.get("provider") else None,
            model=str(data["model"]).strip() if data.get("model") else None,
            fallbacks=[str(x).strip() for x in data.get("fallbacks", []) if str(x).strip()],
            tags=[str(x).strip() for x in data.get("tags", []) if str(x).strip()],
            skill_ids=[str(x).strip().lower() for x in data.get("skill_ids", []) if str(x).strip()],
            metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
            source_path=source_path,
        )
