from nexus_agent.team.research import all_policies, policy


def test_research_depth_has_five_to_ten_coordination_turns():
    rows = all_policies()
    assert len(rows) == 21
    turns = [int(row["coordination_turns"]) for row in rows]
    assert all(5 <= value <= 10 for value in turns)
    assert turns == sorted(turns)


def test_research_depth_scales_evidence_work_monotonically():
    rows = all_policies()
    for key in (
        "sources_per_round",
        "verification_passes",
        "contradiction_passes",
        "formal_passes",
        "review_passes",
        "min_independent_sources",
    ):
        values = [int(row[key]) for row in rows]
        assert values == sorted(values), key


def test_research_depth_policy_is_explicitly_bounded_at_maximal():
    maximal = policy("maximal")
    assert maximal["coordination_turns"] == 10
    assert maximal["review_passes"] == 10
    assert maximal["formal_passes"] == 8
    assert maximal["min_independent_sources"] == 40
