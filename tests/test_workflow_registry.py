from pathlib import Path

from nexus_agent.team.models import TeamMode
from nexus_agent.workflows import WorkflowRegistry, WorkflowSpec


def test_custom_workflow_round_trip(tmp_path: Path):
    registry = WorkflowRegistry(tmp_path)
    spec = WorkflowSpec(
        id="custom-research",
        name="Custom Research",
        description="Research with a fixed team shape.",
        mode=TeamMode.RESEARCH,
        default_agents=9,
        research_depth="deep",
        tags=("custom", "research"),
    )
    path = registry.save(spec, "workspace")
    assert path.exists()
    loaded = registry.get("custom-research")
    assert loaded.source.startswith("workspace:")
    assert loaded.default_agents == 9
    assert loaded.configure().mode == TeamMode.RESEARCH
    assert registry.delete("custom-research", "workspace") is True
