from pathlib import Path

from nexus_agent.agents import AgentRegistry, AgentScope, AgentSpec


def test_agent_registry_scope_precedence(tmp_path: Path):
    registry = AgentRegistry(tmp_path, project_root=tmp_path)
    project = AgentSpec(
        id="reviewer",
        name="Project Reviewer",
        profession="Reviewer",
        description="project",
        mission="review project",
        instructions="project instructions",
        scope=AgentScope.PROJECT,
    )
    workspace = AgentSpec(
        id="reviewer",
        name="Workspace Reviewer",
        profession="Reviewer",
        description="workspace",
        mission="review workspace",
        instructions="workspace instructions",
        scope=AgentScope.WORKSPACE,
    )
    registry.save(project, AgentScope.PROJECT)
    registry.save(workspace, AgentScope.WORKSPACE)
    resolved = registry.get("reviewer")
    assert resolved is not None
    assert resolved.name == "Workspace Reviewer"


def test_agent_registry_validation_catches_write_mismatch(tmp_path: Path):
    registry = AgentRegistry(tmp_path, project_root=tmp_path)
    spec = AgentSpec(
        id="writer",
        name="Writer",
        profession="Writer",
        description="",
        mission="write",
        instructions="write",
        tool_categories=["read"],
        write_access=True,
    )
    assert "write_access=true requires the 'write' tool category." in registry.validate(spec)
