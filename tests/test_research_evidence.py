from pathlib import Path

from nexus_agent.research.store import ResearchStore


def test_research_evidence_ledger_verifies_exact_quotes(tmp_path: Path):
    store = ResearchStore(tmp_path / "research.db")
    source = store.record_source(
        "team-1",
        "researcher",
        "https://example.test/spec",
        "Example Spec",
        "The language uses algebraic data types.",
        "test",
    )
    claim = store.record_claim(
        "team-1",
        "researcher",
        "The language uses algebraic data types.",
        "fact",
        source["source_id"],
        "The language uses algebraic data types.",
    )
    verdict = store.verify_claim("team-1", claim["claim_id"], "verifier", "Exact quote verified.")
    assert verdict["verdict"] == "verified"


def test_research_evidence_ledger_rejects_wrong_quote(tmp_path: Path):
    store = ResearchStore(tmp_path / "research.db")
    source = store.record_source(
        "team-2",
        "researcher",
        "https://example.test/spec",
        "Example Spec",
        "A source statement.",
        "test",
    )
    claim = store.record_claim(
        "team-2",
        "researcher",
        "A claim",
        "fact",
        source["source_id"],
        "This text does not exist in the source.",
    )
    verdict = store.verify_claim("team-2", claim["claim_id"], "verifier")
    assert verdict["verdict"] == "rejected"

def test_research_conflicts_block_coverage_until_adjudicated(tmp_path: Path):
    store = ResearchStore(tmp_path / "research.db")
    source = store.record_source(
        "team-3",
        "researcher",
        "https://example.test/spec",
        "Example Spec",
        "Claim one. Claim two.",
        "test",
    )
    claim_a = store.record_claim(
        "team-3",
        "researcher",
        "Claim one.",
        "fact",
        source["source_id"],
        "Claim one.",
    )
    claim_b = store.record_claim(
        "team-3",
        "researcher",
        "Claim two.",
        "fact",
        source["source_id"],
        "Claim two.",
    )
    store.verify_claim("team-3", claim_a["claim_id"], "verifier")
    store.verify_claim("team-3", claim_b["claim_id"], "verifier")
    conflict = store.record_conflict(
        "team-3",
        "skeptic",
        claim_a["claim_id"],
        claim_b["claim_id"],
    )
    coverage = store.coverage("team-3", required_verification_passes=1)
    assert coverage["unresolved_conflicts"] == 1
    assert coverage["passed"] is False

    store.adjudicate_conflict(
        "team-3",
        conflict["conflict_id"],
        "adjudicator",
        "accepted_uncertainty",
        "The claims address different operating conditions and are therefore not mutually exclusive.",
    )
    coverage_after = store.coverage("team-3", required_verification_passes=1)
    assert coverage_after["unresolved_conflicts"] == 0
