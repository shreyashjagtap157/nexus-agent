"""Typed models for NexusAgent multi-agent teams."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TeamMode(str, Enum):
    AUTO = "auto"
    CODE = "code"
    RESEARCH = "research"
    REVIEW = "review"
    ANALYSIS = "analysis"
    PLAN = "plan"
    AUTOMATION = "automation"


class TeamAgentState(str, Enum):
    PLANNED = "planned"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_AGENT = "waiting_agent"
    WAITING_TOOL = "waiting_tool"
    WAITING_USER = "waiting_user"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentProfile:
    role_id: str
    name: str
    profession: str
    mission: str
    instructions: str
    tool_categories: list[str] = field(default_factory=list)
    write_access: bool = False
    reviewer: bool = False
    dependencies: list[str] = field(default_factory=list)
    model_role: str = "default"

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_id": self.role_id,
            "name": self.name,
            "profession": self.profession,
            "mission": self.mission,
            "instructions": self.instructions,
            "tool_categories": list(self.tool_categories),
            "write_access": self.write_access,
            "reviewer": self.reviewer,
            "dependencies": list(self.dependencies),
            "model_role": self.model_role,
        }


@dataclass
class TeamConfig:
    mode: TeamMode = TeamMode.AUTO
    max_agents: int = 6
    parallelism: int = 4
    max_iterations_per_agent: int = 30
    workspace: str = "."
    output_mode: str = "chat"
    effort_level: str = "medium"
    auto_synthesize: bool = True
    require_reviewer: bool = True
    allow_parallel_writers: bool = False
    auto_approve_tools: bool = False

    def normalize(self) -> "TeamConfig":
        self.max_agents = max(1, min(int(self.max_agents), 64))
        self.parallelism = max(1, min(int(self.parallelism), self.max_agents))
        self.max_iterations_per_agent = max(1, min(int(self.max_iterations_per_agent), 500))
        return self


@dataclass
class TeamRunResult:
    team_id: str
    goal: str
    success: bool
    summary: str
    agents: list[dict[str, Any]] = field(default_factory=list)
    synthesis: str = ""
    failures: list[str] = field(default_factory=list)
