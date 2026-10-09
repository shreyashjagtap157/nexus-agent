from pathlib import Path

from nexus_agent.research.store import ResearchStore


def test_research_coverage_requires_verification_threshold(tmp_path: Path):
    store = ResearchStore(tmp_path / "research.db")
    source = store.record_source(
        "team-coverage",
        "researcher",
        "https://example.test/a",
        "A",
        "Supported statement.",
        "test",
    )
    claim = store.record_claim(
        "team-coverage",
        "researcher",
        "Supported statement.",
        "fact",
        source["source_id"],
        "Supported statement.",
    )
    assert store.coverage("team-coverage", required_verification_passes=2)["passed"] is False
    store.verify_claim("team-coverage", claim["claim_id"], "verifier-a")
    assert store.coverage("team-coverage", required_verification_passes=2)["passed"] is False
    store.verify_claim("team-coverage", claim["claim_id"], "verifier-b")
    coverage = store.coverage("team-coverage", required_verification_passes=2)
    assert coverage["passed"] is True
    assert coverage["claims_meeting_verification_threshold"] == 1


def test_research_claim_can_attach_second_source(tmp_path: Path):
    store = ResearchStore(tmp_path / "research.db")
    first = store.record_source(
        "team-multi",
        "researcher",
        "https://example.test/a",
        "A",
        "The system is deterministic. Source A provides context.",
        "test",
    )
    second = store.record_source(
        "team-multi",
        "researcher",
        "https://example.test/b",
        "B",
        "The system is deterministic. Source B provides independent context.",
        "test",
    )
    claim = store.record_claim(
        "team-multi",
        "researcher",
        "The system is deterministic.",
        "fact",
        first["source_id"],
        "The system is deterministic.",
    )
    evidence = store.attach_evidence(
        "team-multi",
        claim["claim_id"],
        second["source_id"],
        "The system is deterministic.",
    )
    assert evidence["quote_present"] is True
    store.verify_claim("team-multi", claim["claim_id"], "verifier")
    coverage = store.coverage("team-multi", 1)
    assert coverage["source_count"] == 2
    assert coverage["passed"] is True


def test_adding_evidence_invalidates_prior_verification_until_rechecked(tmp_path: Path):
    store = ResearchStore(tmp_path / "research.db")
    first = store.record_source(
        "team-recheck",
        "researcher",
        "https://example.test/a",
        "A",
        "The runtime is deterministic. Source A explains the execution model.",
        "test",
    )
    claim = store.record_claim(
        "team-recheck",
        "researcher",
        "The runtime is deterministic.",
        "fact",
        first["source_id"],
        "The runtime is deterministic.",
    )
    store.verify_claim("team-recheck", claim["claim_id"], "verifier-a")
    assert store.coverage("team-recheck", 1)["passed"] is True

    second = store.record_source(
        "team-recheck",
        "researcher",
        "https://example.test/b",
        "B",
        "The runtime is deterministic. Source B independently confirms the behavior.",
        "test",
    )
    store.attach_evidence(
        "team-recheck",
        claim["claim_id"],
        second["source_id"],
        "The runtime is deterministic.",
    )

    current_claim = next(item for item in store.claims("team-recheck") if item["claim_id"] == claim["claim_id"])
    assert current_claim["status"] == "quote_present"
    invalidated = store.coverage("team-recheck", 1)
    assert invalidated["passed"] is False
    assert invalidated["verified_claims"] == 0

    store.verify_claim("team-recheck", claim["claim_id"], "verifier-b")
    rechecked = store.coverage("team-recheck", 1)
    assert rechecked["passed"] is True
    assert rechecked["source_count"] == 2
    assert rechecked["claims_meeting_verification_threshold"] == 1
