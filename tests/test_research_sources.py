from pathlib import Path

import yaml

from nexus_agent.research.sources import ResearchSource, ResearchSourceRegistry


def test_configured_sources_registry_round_trip(tmp_path: Path):
    path = tmp_path / "sources.yaml"
    registry = ResearchSourceRegistry(path)
    registry.add(
        ResearchSource(
            id="spec",
            url="https://example.test/spec",
            name="Example Specification",
            priority=100,
        )
    )
    assert registry.get("spec").url == "https://example.test/spec"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert payload["sources"][0]["id"] == "spec"
