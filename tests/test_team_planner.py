import json

from nexus_agent.team.models import TeamConfig, TeamMode
from nexus_agent.team.planner import _parse_profiles


def test_generated_dependency_aliases_resolve_to_role_ids():
    payload = {
        "agents": [
            {
                "id": "researcher",
                "name": "Primary Researcher",
                "profession": "Research Scientist",
                "mission": "Gather sources",
                "instructions": "Find primary evidence.",
            },
            {
                "id": "verifier",
                "name": "Evidence Verifier",
                "profession": "Verification Specialist",
                "mission": "Verify claims",
                "instructions": "Check quotations.",
                "dependencies": ["Primary Researcher"],
            },
        ]
    }
    profiles = _parse_profiles(json.dumps(payload), TeamMode.RESEARCH, 2)
    assert profiles[0].role_id == "researcher"
    assert profiles[1].dependencies == ["researcher"]


def test_research_fallback_has_enough_distinct_professions_for_high_depth():
    profiles = _parse_profiles("{}", TeamMode.RESEARCH, 32)
    assert len(profiles) >= 32
    assert len({profile.role_id for profile in profiles}) == len(profiles)
    assert len({profile.profession for profile in profiles}) >= 24


def test_research_config_depth_floor_can_require_large_team():
    config = TeamConfig(mode=TeamMode.RESEARCH, research_depth="maximal", max_agents=4)
    normalized = config.normalize()
    assert normalized.max_agents >= 40
