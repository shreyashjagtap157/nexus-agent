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


from nexus_agent.team.research import all_policies, policy


def test_all_research_depths_are_bounded_to_five_to_ten_coordination_turns():
    rows = all_policies()
    assert len(rows) == 21
    values = [row["coordination_turns"] for row in rows]
    assert all(5 <= int(value) <= 10 for value in values)
    assert values == sorted(values)


def test_research_depth_increases_work_without_increasing_coordination_cap():
    rows = all_policies()
    deep = rows[rows.index(policy("deep"))]
    maximal = policy("maximal")
    assert int(deep["coordination_turns"]) <= int(maximal["coordination_turns"]) <= 10
    for key in (
        "sources_per_round",
        "verification_passes",
        "contradiction_passes",
        "formal_passes",
        "review_passes",
        "min_independent_sources",
    ):
        assert int(deep[key]) <= int(maximal[key])


def test_maximal_depth_is_still_a_bounded_ten_turn_protocol():
    item = policy("maximal")
    assert item["coordination_turns"] == 10
    assert item["sources_per_round"] == 30
    assert item["verification_passes"] == 8
    assert item["contradiction_passes"] == 8
    assert item["formal_passes"] == 8
    assert item["review_passes"] == 10


def test_gui_exposes_provider_and_general_configuration_routes():
    from fastapi.routing import APIRoute

    from nexus_agent.gui.server import app

    routes = {
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
    }
    assert "/api/providers" in routes
    assert "/api/provider-config" in routes
    assert "/api/config/full" in routes
    assert "/api/config/{section}" in routes
