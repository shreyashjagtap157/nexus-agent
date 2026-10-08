from types import SimpleNamespace

from nexus_agent.team.quality import evaluate_team


def cfg():
    return SimpleNamespace(
        require_reviewer=True,
        output_mode="chat",
    )


def test_research_synthesis_claim_markers_must_reference_verified_claims():
    research = {
        "passed": True,
        "verified_claim_ids": [1, 3],
        "claim_ids": [1, 2, 3],
    }
    passed = evaluate_team(
        results=[
            {"status": "completed", "reviewer": True, "agent_id": "reviewer"},
        ],
        config=cfg(),
        artifacts=[],
        research_summary=research,
        research_synthesis="Verified statement [claim:1].",
    )
    assert passed["checks"]["research_synthesis_evidence"]["passed"] is True

    rejected = evaluate_team(
        results=[
            {"status": "completed", "reviewer": True, "agent_id": "reviewer"},
        ],
        config=cfg(),
        artifacts=[],
        research_summary=research,
        research_synthesis="Unsupported statement [claim:2].",
    )
    assert rejected["checks"]["research_synthesis_evidence"]["passed"] is False


def test_research_synthesis_requires_markers_when_verified_claims_exist():
    research = {"passed": True, "verified_claim_ids": [7]}
    result = evaluate_team(
        results=[
            {"status": "completed", "reviewer": True, "agent_id": "reviewer"},
        ],
        config=cfg(),
        artifacts=[],
        research_summary=research,
        research_synthesis="A factual statement without provenance.",
    )
    assert result["checks"]["research_synthesis_evidence"]["passed"] is False
