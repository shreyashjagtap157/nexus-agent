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
