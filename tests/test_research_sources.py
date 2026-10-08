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
    assert len(sources) == 2
    assert any(item.id.startswith("source-") for item in sources)
    assert registry.get("spec").url == "https://example.test/spec"
    assert registry.remove("spec") is True
