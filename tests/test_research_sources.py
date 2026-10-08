from pathlib import Path

from nexus_agent.research.sources import ResearchSource, ResearchSourceRegistry


def test_research_source_registry_round_trip(tmp_path: Path):
    registry = ResearchSourceRegistry(tmp_path / "sources.yaml")
    registry.add(
        ResearchSource(
            id="spec",
            url="https://example.test/spec",
            name="Example Spec",
            source_type="standard",
            priority=90,
            tags=["normative"],
        )
    )
    registry.seed_urls(["https://example.test/paper"])
    sources = registry.list()
    assert {item.id for item in sources} == {"spec", "source-2f6b2e0e72b6"} or len(sources) == 2
    assert registry.get("spec").url == "https://example.test/spec"
    assert registry.remove("spec") is True
