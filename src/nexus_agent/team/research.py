"""Research-depth policy for NexusAgent teams."""
from __future__ import annotations

from typing import Any

RESEARCH_DEPTHS: tuple[str, ...] = (
    "glance",
    "surface",
    "shallow",
    "basic",
    "preliminary",
    "exploratory",
    "focused",
    "detailed",
    "deep",
    "very_deep",
    "comprehensive",
    "exhaustive",
    "atomic",
    "molecular",
    "cellular",
    "planetary",
    "stellar",
    "galactic",
    "cosmic",
    "universal",
    "maximal",
)

_RESEARCH_POLICY: tuple[dict[str, Any], ...] = (
    {"name": "glance", "label": "Glance", "role_floor": 2, "query_rounds": 1, "sources_per_query": 2, "verification_passes": 1},
    {"name": "surface", "label": "Surface", "role_floor": 2, "query_rounds": 1, "sources_per_query": 3, "verification_passes": 1},
    {"name": "shallow", "label": "Shallow", "role_floor": 3, "query_rounds": 2, "sources_per_query": 3, "verification_passes": 1},
    {"name": "basic", "label": "Basic", "role_floor": 3, "query_rounds": 2, "sources_per_query": 4, "verification_passes": 1},
    {"name": "preliminary", "label": "Preliminary", "role_floor": 4, "query_rounds": 2, "sources_per_query": 4, "verification_passes": 2},
    {"name": "exploratory", "label": "Exploratory", "role_floor": 4, "query_rounds": 3, "sources_per_query": 4, "verification_passes": 2},
    {"name": "focused", "label": "Focused", "role_floor": 5, "query_rounds": 3, "sources_per_query": 5, "verification_passes": 2},
    {"name": "detailed", "label": "Detailed", "role_floor": 6, "query_rounds": 3, "sources_per_query": 5, "verification_passes": 2},
    {"name": "deep", "label": "Deep", "role_floor": 7, "query_rounds": 4, "sources_per_query": 5, "verification_passes": 3},
    {"name": "very_deep", "label": "Very Deep", "role_floor": 8, "query_rounds": 4, "sources_per_query": 6, "verification_passes": 3},
    {"name": "comprehensive", "label": "Comprehensive", "role_floor": 10, "query_rounds": 5, "sources_per_query": 6, "verification_passes": 3},
    {"name": "exhaustive", "label": "Exhaustive", "role_floor": 12, "query_rounds": 6, "sources_per_query": 7, "verification_passes": 4},
    {"name": "atomic", "label": "Atomic", "role_floor": 14, "query_rounds": 7, "sources_per_query": 8, "verification_passes": 4},
    {"name": "molecular", "label": "Molecular", "role_floor": 16, "query_rounds": 8, "sources_per_query": 8, "verification_passes": 4},
    {"name": "cellular", "label": "Cellular", "role_floor": 18, "query_rounds": 9, "sources_per_query": 9, "verification_passes": 5},
    {"name": "planetary", "label": "Planetary", "role_floor": 20, "query_rounds": 10, "sources_per_query": 10, "verification_passes": 5},
    {"name": "stellar", "label": "Stellar", "role_floor": 22, "query_rounds": 12, "sources_per_query": 10, "verification_passes": 5},
    {"name": "galactic", "label": "Galactic", "role_floor": 24, "query_rounds": 14, "sources_per_query": 12, "verification_passes": 6},
    {"name": "cosmic", "label": "Cosmic", "role_floor": 28, "query_rounds": 16, "sources_per_query": 12, "verification_passes": 6},
    {"name": "universal", "label": "Universal", "role_floor": 32, "query_rounds": 20, "sources_per_query": 15, "verification_passes": 7},
    {"name": "maximal", "label": "Maximal", "role_floor": 40, "query_rounds": 0, "sources_per_query": 20, "verification_passes": 8},
)


def policy(depth: str) -> dict[str, Any]:
    normalized = depth.strip().lower().replace("-", "_").replace(" ", "_")
    for item in _RESEARCH_POLICY:
        if item["name"] == normalized:
            return dict(item)
    raise ValueError(
        f"Unknown research depth {depth!r}. "
        f"Choose one of: {', '.join(RESEARCH_DEPTHS)}"
    )


def all_policies() -> list[dict[str, Any]]:
    return [dict(item) for item in _RESEARCH_POLICY]
