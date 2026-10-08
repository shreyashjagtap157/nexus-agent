"""User-extensible orchestration workflow registry."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import platformdirs
import yaml

from nexus_agent.core.config import get_data_dir
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
    source: str = "builtin"

    def configure(self, **overrides: Any) -> TeamConfig:
        values = {
            "mode": self.mode,
            "workflow_id": self.id,
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

    @classmethod
    def from_dict(cls, data: dict[str, Any], source: str) -> "WorkflowSpec":
        workflow_id = str(data.get("id") or "").strip().lower()
        if not workflow_id:
            raise ValueError("Workflow requires id.")
        mode = TeamMode(str(data.get("mode") or "auto"))
        return cls(
            id=workflow_id,
            name=str(data.get("name") or workflow_id).strip(),
            description=str(data.get("description") or "").strip(),
            mode=mode,
            default_agents=max(1, min(int(data.get("default_agents", 4)), 64)),
            require_reviewer=bool(data.get("require_reviewer", True)),
            auto_synthesize=bool(data.get("auto_synthesize", True)),
            allow_parallel_writers=bool(data.get("allow_parallel_writers", False)),
            output_mode=str(data.get("output_mode") or "chat"),
            research_depth=str(data.get("research_depth") or "detailed"),
            research_collection=str(data.get("research_collection") or "until_saturation"),
            tags=tuple(str(x).strip() for x in data.get("tags", []) if str(x).strip()),
            controls=data.get("controls") if isinstance(data.get("controls"), dict) else {},
            source=source,
        )


class WorkflowRegistry:
    """Built-in workflows plus user/workspace YAML workflows."""

    BUILTINS = (
        WorkflowSpec("code-change", "Code Change", "Architect -> implement -> test -> review.", TeamMode.CODE, default_agents=4, tags=("software", "build", "verify")),
        WorkflowSpec("build-review", "Build + Adversarial Review", "Implement a requested change and run an adversarial correctness pass.", TeamMode.CODE, default_agents=4, tags=("software", "review", "security")),
        WorkflowSpec("research-verify", "Research + Evidence Verification", "Gather primary sources, preserve evidence, challenge findings, then verify claims.", TeamMode.RESEARCH, default_agents=6, research_depth="comprehensive", tags=("research", "evidence", "verification")),
        WorkflowSpec("exhaustive-research", "Exhaustive Research", "Deep research with contradiction analysis and deterministic quotation verification.", TeamMode.RESEARCH, default_agents=12, research_depth="exhaustive", tags=("research", "exhaustive", "sources")),
        WorkflowSpec("architecture-debate", "Architecture Debate", "Independent architects and skeptics evaluate alternatives before synthesis.", TeamMode.ANALYSIS, default_agents=5, tags=("architecture", "decision", "debate")),
        WorkflowSpec("repository-audit", "Repository Audit", "Inspect a codebase for correctness, compatibility, security, tests and integration gaps.", TeamMode.REVIEW, default_agents=5, tags=("audit", "security", "quality")),
        WorkflowSpec("automation", "Automation Engineering", "Design, implement and reliability-test an automation workflow.", TeamMode.AUTOMATION, default_agents=4, tags=("automation", "workflow", "reliability")),
        WorkflowSpec("specification-analysis", "Specification Analysis", "Requirements, implementability, formal consistency and contradiction review.", TeamMode.ANALYSIS, default_agents=8, tags=("specification", "formal", "consistency", "implementability")),
        WorkflowSpec("security-audit", "Security Audit", "Independent threat, dependency, implementation and adversarial security review.", TeamMode.REVIEW, default_agents=7, tags=("security", "threat-model", "audit", "adversarial")),
        WorkflowSpec("release-qualification", "Release Qualification", "Qualify a repository for release with compatibility, tests, packaging, docs and audit.", TeamMode.REVIEW, default_agents=8, tags=("release", "qualification", "packaging")),
        WorkflowSpec("dependency-upgrade", "Dependency Upgrade", "Analyze dependency changes, migration risk and compatibility before updating.", TeamMode.CODE, default_agents=6, tags=("dependencies", "migration", "compatibility")),
        WorkflowSpec("long-running-research", "Long-Running Research", "Evidence-first research until source saturation or explicit stop.", TeamMode.RESEARCH, default_agents=12, research_depth="maximal", research_collection="continuous", tags=("research", "autonomous", "saturation")),
    )

    def __init__(self, workspace: Path | None = None):
        self.workspace = (workspace or Path.cwd()).resolve()

    @property
    def roots(self) -> list[tuple[str, Path]]:
        return [
            ("user", Path(get_data_dir()) / "workflows"),
            ("workspace", self.workspace / ".nexus-agent" / "workflows"),
        ]

    def _custom(self) -> list[WorkflowSpec]:
        discovered: dict[str, WorkflowSpec] = {}
        for scope, root in self.roots:
            if not root.exists():
                continue
            for path in sorted(root.glob("*.yaml")) + sorted(root.glob("*.yml")):
                try:
                    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                    if isinstance(data, dict):
                        spec = WorkflowSpec.from_dict(data, f"{scope}:{path}")
                        discovered[spec.id] = spec
                except (OSError, ValueError, yaml.YAMLError):
                    continue
        return list(discovered.values())

    def list(self) -> list[WorkflowSpec]:
        merged = {workflow.id: workflow for workflow in self.BUILTINS}
        for workflow in self._custom():
            merged[workflow.id] = workflow
        return sorted(merged.values(), key=lambda workflow: workflow.name.lower())

    def get(self, workflow_id: str) -> WorkflowSpec:
        key = workflow_id.strip().lower()
        for workflow in self.list():
            if workflow.id == key:
                return workflow
        raise ValueError(f"Unknown workflow {workflow_id!r}. Available: {', '.join(w.id for w in self.list())}")

    def save(self, workflow: WorkflowSpec, scope: str = "workspace") -> Path:
        root = dict(self.roots)[scope]
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{workflow.id}.yaml"
        payload = {
            "id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "mode": workflow.mode.value,
            "default_agents": workflow.default_agents,
            "require_reviewer": workflow.require_reviewer,
            "auto_synthesize": workflow.auto_synthesize,
            "allow_parallel_writers": workflow.allow_parallel_writers,
            "output_mode": workflow.output_mode,
            "research_depth": workflow.research_depth,
            "research_collection": workflow.research_collection,
            "tags": list(workflow.tags),
            "controls": workflow.controls,
        }
        path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return path

    def delete(self, workflow_id: str, scope: str = "workspace") -> bool:
        root = dict(self.roots)[scope]
        path = root / f"{workflow_id.strip().lower()}.yaml"
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False
