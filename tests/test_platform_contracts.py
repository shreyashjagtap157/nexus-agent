from pathlib import Path

import pytest

from nexus_agent.agents.models import AgentScope, AgentSpec
from nexus_agent.agents.registry import AgentRegistry
from nexus_agent.auth.store import AuthStore
from nexus_agent.team.models import TeamConfig, TeamMode


def test_team_research_depth_normalization_scales_team_floor():
    config = TeamConfig(
        mode=TeamMode.RESEARCH,
        max_agents=2,
        parallelism=2,
        research_depth="universal",
    ).normalize()
    assert config.max_agents >= 32
    assert config.research_source_strategy == "hybrid"
    assert config.research_max_minutes == 10080
    assert config.research_idle_rounds == 2


def test_agent_registry_validates_write_capability(tmp_path: Path):
    spec = AgentSpec(
        id="bad-writer",
        name="Bad Writer",
        profession="Writer",
        description="",
        mission="Write",
        instructions="Write",
        tool_categories=["read"],
        write_access=True,
    )
    errors = AgentRegistry(tmp_path).validate(spec)
    assert any("write_access" in error for error in errors)


def test_auth_store_never_requires_project_config(tmp_path: Path):
    store = AuthStore(tmp_path / "auth.json", backend="file")
    store.set("nvidia_nim", "nvapi-test-secret", metadata={"scope": "live-test"})
    rows = store.list()
    assert rows[0]["provider"] == "nvidia_nim"
    assert "nvapi-test-secret" not in str(rows)
    assert "nvapi-test-secret" in (store.get("nvidia_nim") or "")
    store.remove("nvidia_nim")
    assert store.get("nvidia_nim") is None


def test_agent_profile_roundtrip_preserves_provider_routing(tmp_path: Path):
    registry = AgentRegistry(tmp_path, user_root=tmp_path / "user-agents")
    spec = AgentSpec(
        id="nim-verifier",
        name="NIM Verifier",
        profession="Evidence Verifier",
        description="",
        mission="Verify claims",
        instructions="Use exact source evidence.",
        provider="nvidia_nim",
        model="nvidia/nemotron-3.5-lightning-30b-a3b",
        fallbacks=["openrouter"],
        tool_categories=["read", "research"],
    )
    path = registry.save(spec, AgentScope.USER)
    assert path.exists()
    loaded = registry.get("nim-verifier")
    assert loaded is not None
    assert loaded.provider == "nvidia_nim"
    assert loaded.model == "nvidia/nemotron-3.5-lightning-30b-a3b"
    assert loaded.fallbacks == ["openrouter"]


def test_agent_skill_roundtrip_and_team_profile_binding(tmp_path):
    from nexus_agent.agents.models import AgentScope, AgentSpec
    from nexus_agent.agents.registry import AgentRegistry

    registry = AgentRegistry(tmp_path, user_root=tmp_path / "user-agents")
    skill_dir = tmp_path / ".nexus-agent" / "skills"
    skill_dir.mkdir(parents=True)
    (skill_dir / "example.md").write_text(
        "---\nname: example\ndescription: Example skill\nparameters: {}\n---\nDo the thing.\n",
        encoding="utf-8",
    )
    spec = AgentSpec(
        id="skilled-worker",
        name="Skilled Worker",
        profession="Worker",
        description="",
        mission="Use a reusable skill.",
        instructions="Execute the assigned work.",
        scope=AgentScope.WORKSPACE,
        tool_categories=["read"],
        skill_ids=["example"],
    )
    assert registry.validate(spec) == []
    saved = registry.save(spec, AgentScope.WORKSPACE)
    assert saved.exists()
    loaded = registry.get("skilled-worker")
    assert loaded is not None
    assert loaded.skill_ids == ["example"]
    assert loaded.to_team_profile().skill_ids == ["example"]
