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
    provider: str | None = None
    model: str | None = None
    fallbacks: list[str] = field(default_factory=list)

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
            "provider": self.provider,
            "model": self.model,
            "fallbacks": list(self.fallbacks),
        }


@dataclass
class TeamConfig:
    mode: TeamMode = TeamMode.AUTO
    workflow_id: str = ""
    max_agents: int = 6
    parallelism: int = 4
    max_iterations_per_agent: int = 30
    workspace: str = "."
    output_mode: str = "chat"
    output_format: str = "markdown"
    research_depth: str = "detailed"
    research_collection: str = "until_saturation"
    research_source_strategy: str = "hybrid"
    research_max_minutes: int = 10080
    research_idle_rounds: int = 2
    research_source_urls: list[str] = field(default_factory=list)
    effort_level: str = "medium"
    auto_synthesize: bool = True
    require_reviewer: bool = True
    allow_parallel_writers: bool = False
    auto_approve_tools: bool = False
    agent_ids: list[str] = field(default_factory=list)
    use_saved_agents: bool = True

    def normalize(self) -> "TeamConfig":
        self.max_agents = max(1, min(int(self.max_agents), 64))
        self.parallelism = max(1, min(int(self.parallelism), self.max_agents))
        self.max_iterations_per_agent = max(1, min(int(self.max_iterations_per_agent), 500))
        self.research_max_minutes = max(1, min(int(self.research_max_minutes), 525600))
        self.research_idle_rounds = max(1, min(int(self.research_idle_rounds), 20))
        self.output_mode = self.output_mode if self.output_mode in {"chat", "file", "both"} else "chat"
        self.output_format = self.output_format if self.output_format in {"markdown", "text", "json"} else "markdown"
        self.research_collection = (
            self.research_collection
            if self.research_collection in {"bounded", "until_saturation", "continuous"}
            else "until_saturation"
        )
        self.research_source_strategy = (
            self.research_source_strategy
            if self.research_source_strategy in {"user_only", "hybrid", "autonomous"}
            else "hybrid"
        )
        if self.mode == TeamMode.RESEARCH:
            from .research import policy as research_policy
            depth = research_policy(self.research_depth)
            self.max_agents = max(self.max_agents, min(int(depth["role_floor"]), 64))
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
    artifact_paths: list[str] = field(default_factory=list)
