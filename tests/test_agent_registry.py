from pathlib import Path

import pytest

from nexus_agent.agents import AgentRegistry, AgentScope, AgentSpec


def make_spec() -> AgentSpec:
    return AgentSpec(
        id="security-reviewer",
        name="Security Reviewer",
        profession="Application Security Engineer",
        description="Reviews security risk.",
        mission="Find exploitable security defects.",
        instructions="Inspect evidence and report reproducible findings.",
        tool_categories=["read", "search", "shell"],
        reviewer=True,
    )


def test_agent_registry_scope_precedence(tmp_path: Path):
    registry = AgentRegistry(tmp_path)
    low = make_spec()
    high = make_spec()
    high.description = "Workspace override"
    registry.save(low, AgentScope.PROJECT)
    registry.save(high, AgentScope.WORKSPACE)
    resolved = registry.get("security-reviewer")
    assert resolved is not None
    assert resolved.description == "Workspace override"


def test_builtin_agents_are_immutable(tmp_path: Path):
    registry = AgentRegistry(tmp_path)
    with pytest.raises(ValueError):
        registry.save(make_spec(), AgentScope.BUILTIN)
    with pytest.raises(ValueError):
        registry.delete("architect", AgentScope.BUILTIN)
