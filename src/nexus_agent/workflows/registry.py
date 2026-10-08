"""Declarative orchestration workflow registry."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nexus_agent.team.models import TeamConfig, TeamMode


@dataclass(frozen=True)
class WorkflowSpec:
    id: str
    name: str
    description: str
    mode: TeamMode
    default_agents: int = 4
    require_reviewer: bool = True
    auto_synthesize: bool = True
    allow_parallel_writers: bool = False
    output_mode: str = "chat"
    research_depth: str = "detailed"
    research_collection: str = "until_saturation"
    tags: tuple[str, ...] = ()
    controls: dict[str, Any] = field(default_factory=dict)

    def configure(self, **overrides: Any) -> TeamConfig:
        values = {
            "mode": self.mode,
            "max_agents": self.default_agents,
            "require_reviewer": self.require_reviewer,
            "auto_synthesize": self.auto_synthesize,
            "allow_parallel_writers": self.allow_parallel_writers,
            "output_mode": self.output_mode,
            "research_depth": self.research_depth,
            "research_collection": self.research_collection,
        }
        values.update({key: value for key, value in overrides.items() if value is not None})
        return TeamConfig(**values).normalize()


class WorkflowRegistry:
    """Built-in enterprise workflows plus extensible configuration hooks."""

    BUILTINS = (
        WorkflowSpec(
            "code-change",
            "Code Change",
            "Architect -> implement -> test -> independent review with safe sequential writing.",
            TeamMode.CODE,
            default_agents=4,
            allow_parallel_writers=False,
            tags=("software", "build", "verify"),
        ),
        WorkflowSpec(
            "build-review",
            "Build + Adversarial Review",
            "Implement a requested change and require an adversarial correctness pass.",
            TeamMode.CODE,
            default_agents=4,
            allow_parallel_writers=False,
            tags=("software", "review", "security"),
        ),
        WorkflowSpec(
            "research-verify",
            "Research + Evidence Verification",
            "Gather primary sources, preserve evidence, challenge findings, then verify claims.",
            TeamMode.RESEARCH,
            default_agents=6,
            research_depth="comprehensive",
            research_collection="until_saturation",
            tags=("research", "evidence", "verification"),
        ),
        WorkflowSpec(
            "exhaustive-research",
            "Exhaustive Research",
            "Deep research with contradiction analysis and deterministic quotation verification.",
            TeamMode.RESEARCH,
            default_agents=12,
            research_depth="exhaustive",
            research_collection="until_saturation",
            tags=("research", "exhaustive", "sources"),
        ),
        WorkflowSpec(
            "architecture-debate",
            "Architecture Debate",
            "Independent architects and skeptics evaluate alternatives before a synthesized decision.",
            TeamMode.ANALYSIS,
            default_agents=5,
            tags=("architecture", "decision", "debate"),
        ),
        WorkflowSpec(
            "repository-audit",
            "Repository Audit",
            "Inspect a codebase for correctness, compatibility, security, tests and integration gaps.",
            TeamMode.REVIEW,
            default_agents=5,
            tags=("audit", "security", "quality"),
        ),
        WorkflowSpec(
            "automation",
            "Automation Engineering",
            "Design, implement and reliability-test an automation workflow.",
            TeamMode.AUTOMATION,
            default_agents=4,
            tags=("automation", "workflow", "reliability"),
        ),
        WorkflowSpec(
            "specification-analysis",
            "Specification Analysis",
            "Build a role-separated analysis team for requirements, implementability, formal consistency and contradiction review.",
            TeamMode.ANALYSIS,
            default_agents=8,
            tags=("specification", "formal", "consistency", "implementability"),
        ),
        WorkflowSpec(
            "security-audit",
            "Security Audit",
            "Run independent threat, dependency, implementation and adversarial security reviews before synthesis.",
            TeamMode.REVIEW,
            default_agents=7,
            tags=("security", "threat-model", "audit", "adversarial"),
        ),
        WorkflowSpec(
            "release-qualification",
            "Release Qualification",
            "Qualify a repository for release with compatibility, tests, packaging, documentation and independent audit workers.",
            TeamMode.REVIEW,
            default_agents=8,
            tags=("release", "qualification", "packaging", "regression"),
        ),
        WorkflowSpec(
            "dependency-upgrade",
            "Dependency Upgrade",
            "Analyze dependency changes, migration risk, compatibility and verification before updating a codebase.",
            TeamMode.CODE,
            default_agents=6,
            tags=("dependencies", "migration", "compatibility"),
        ),
        WorkflowSpec(
            "long-running-research",
            "Long-Running Research",
            "Operate an evidence-first research team until source saturation, contradiction closure or explicit stop.",
            TeamMode.RESEARCH,
            default_agents=12,
            research_depth="maximal",
            research_collection="continuous",
            tags=("research", "autonomous", "saturation", "evidence"),
        ),
    )

    def list(self) -> list[WorkflowSpec]:
        return list(self.BUILTINS)

    def get(self, workflow_id: str) -> WorkflowSpec:
        key = workflow_id.strip().lower()
        for workflow in self.BUILTINS:
            if workflow.id == key:
                return workflow
        raise ValueError(f"Unknown workflow {workflow_id!r}. Available: {', '.join(w.id for w in self.BUILTINS)}")
