"""Markdown + YAML-frontmatter format for persisted agent definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import AgentScope, AgentSpec


def parse_agent_file(path: Path, scope: AgentScope) -> AgentSpec:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"Agent file {path} must start with YAML frontmatter.")
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise ValueError(f"Agent file {path} has malformed frontmatter.")
    metadata = yaml.safe_load(parts[1]) or {}
    if not isinstance(metadata, dict):
        raise ValueError(f"Agent file {path} frontmatter must be a mapping.")
    body = parts[2].strip()
    if "instructions" not in metadata:
        metadata["instructions"] = body
    elif body:
        metadata["instructions"] = str(metadata["instructions"]).rstrip() + "\n\n" + body
    return AgentSpec.from_dict(metadata, scope, str(path.resolve()))


def render_agent_file(spec: AgentSpec) -> str:
    payload: dict[str, Any] = {
        "id": spec.id,
        "name": spec.name,
        "profession": spec.profession,
        "description": spec.description,
        "mission": spec.mission,
        "enabled": spec.enabled,
        "tool_categories": spec.tool_categories,
        "write_access": spec.write_access,
        "reviewer": spec.reviewer,
        "dependencies": spec.dependencies,
        "model_role": spec.model_role,
    }
    if spec.provider:
        payload["provider"] = spec.provider
    if spec.model:
        payload["model"] = spec.model
    if spec.fallbacks:
        payload["fallbacks"] = spec.fallbacks
    if spec.tags:
        payload["tags"] = spec.tags
    if spec.skill_ids:
        payload["skill_ids"] = spec.skill_ids
    if spec.metadata:
        payload["metadata"] = spec.metadata
    return (
        "---\n"
        + yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).rstrip()
        + "\n---\n\n"
        + spec.instructions.rstrip()
        + "\n"
    )


def write_agent_file(path: Path, spec: AgentSpec) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_agent_file(spec), encoding="utf-8")
    return path
