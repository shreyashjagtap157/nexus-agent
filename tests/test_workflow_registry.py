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
        default_parallelism=3,
        default_iterations=42,
        effort_level="high",
        output_format="json",
        research_depth="deep",
        agent_ids=("researcher", "verifier"),
        research_source_urls=("https://example.test/spec",),
        tags=("custom", "research"),
    )
    path = registry.save(spec, "workspace")
    assert path.exists()
    loaded = registry.get("custom-research")
    assert loaded.source.startswith("workspace:")
    assert loaded.default_agents == 9
    assert loaded.default_parallelism == 3
    assert loaded.default_iterations == 42
    assert loaded.output_format == "json"
    assert loaded.agent_ids == ("researcher", "verifier")
    assert loaded.research_source_urls == ("https://example.test/spec",)
    configured = loaded.configure()
    assert configured.mode == TeamMode.RESEARCH
    assert configured.parallelism == 3
    assert configured.max_iterations_per_agent == 42
    assert configured.output_format == "json"
    assert registry.delete("custom-research", "workspace") is True
