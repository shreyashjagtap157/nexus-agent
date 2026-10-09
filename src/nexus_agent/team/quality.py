"""Deterministic team quality evaluation."""

from __future__ import annotations

import re
from typing import Any


def _claim_id_set(value: Any) -> set[int]:
    if isinstance(value, (list, tuple, set, frozenset)):
        raw_items = value
    else:
        raw_items = str(value or "").split(",")
    claim_ids: set[int] = set()
    for item in raw_items:
        text = str(item).strip()
        if text.isdigit():
            claim_ids.add(int(text))
    return claim_ids


def evaluate_team(
    *,
    results: list[dict[str, Any]],
    config: Any,
    artifacts: list[str],
    research_summary: dict[str, Any] | None = None,
    research_synthesis: str = "",
) -> dict[str, Any]:
    total = len(results)
    completed = sum(item.get("status") == "completed" for item in results)
    failed = [item for item in results if item.get("status") == "failed"]
    cancelled = [item for item in results if item.get("status") == "cancelled"]
    reviewers = [
        item for item in results if item.get("reviewer") and item.get("status") == "completed"
    ]

    checks: dict[str, dict[str, Any]] = {
        "workers_complete": {
            "passed": completed == total and total > 0,
            "completed": completed,
            "total": total,
        },
        "reviewer_present": {
            "passed": (not config.require_reviewer) or bool(reviewers),
            "reviewers_completed": len(reviewers),
            "required": bool(config.require_reviewer),
        },
        "no_failed_workers": {
            "passed": not failed,
            "failed": [item.get("agent_id") for item in failed],
        },
        "no_cancelled_workers": {
            "passed": not cancelled,
            "cancelled": [item.get("agent_id") for item in cancelled],
        },
        "artifacts": {
            "passed": config.output_mode == "chat" or bool(artifacts),
            "requested": config.output_mode,
            "count": len(artifacts),
        },
    }

    if research_summary is not None:
        checks["research_evidence"] = research_summary
        verified_claim_ids = _claim_id_set(research_summary.get("verified_claim_ids"))
        markers = [int(match) for match in re.findall(r"\[claim:(\d+)\]", research_synthesis or "")]
        checks["research_synthesis_evidence"] = {
            "passed": not bool(research_synthesis.strip())
            or (
                bool(verified_claim_ids)
                and bool(markers)
                and all(marker in verified_claim_ids for marker in markers)
            ),
            "marker_count": len(markers),
            "invalid_markers": sorted(set(markers) - verified_claim_ids),
            "verified_claim_ids": sorted(verified_claim_ids),
        }

    passed = all(bool(value.get("passed")) for value in checks.values())
    return {
        "passed": passed,
        "checks": checks,
        "score": round(
            sum(1 for value in checks.values() if value.get("passed")) / max(1, len(checks)) * 100,
            2,
        ),
    }
