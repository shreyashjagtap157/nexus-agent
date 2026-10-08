"""Research evidence tools exposed to research-mode team workers."""
from __future__ import annotations

from typing import Any

from nexus_agent.tools.base import Tool
from nexus_agent.tools.webfetch import WebFetchTool

from .store import ResearchStore


class _ResearchTool(Tool):
    def __init__(self, db_path, team_id: str, agent_id: str):
        self.store = ResearchStore(db_path)
        self.team_id = team_id
        self.agent_id = agent_id


class ResearchRecordSourceTool(_ResearchTool):
    def __init__(self, db_path, team_id: str, agent_id: str):
        super().__init__(db_path, team_id, agent_id)
        self.fetcher = WebFetchTool()

    @property
    def name(self) -> str:
        return "research_record_source"

    @property
    def description(self) -> str:
        return (
            "Fetch a URL and persist the exact fetched text into the research evidence ledger. "
            "The content argument from the caller is never trusted as source evidence."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "url": {"type": "string", "description": "Absolute HTTP(S) source URL"},
            "title": {"type": "string", "description": "Optional human-readable source title"},
            "provider": {"type": "string", "description": "Discovery provider label", "required": False},
        }

    def execute(self, **kwargs: Any) -> Any:
        url = str(kwargs.get("url") or "").strip()
        if not url:
            return "Error: URL is required."
        fetched = self.fetcher.execute(url)
        if fetched.startswith("Error:"):
            return fetched
        return self.store.record_source(
            self.team_id,
            self.agent_id,
            url,
            str(kwargs.get("title") or url),
            fetched,
            str(kwargs.get("provider") or "web_fetch"),
        )


class ResearchRecordClaimTool(_ResearchTool):
    @property
    def name(self) -> str:
        return "research_record_claim"

    @property
    def description(self) -> str:
        return "Record a factual research claim and an exact quotation that supports it."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "claim_id": {"type": "integer", "description": "Existing claim ID; when provided, attach another source quotation instead of creating a new claim.", "required": False},
            "statement": {"type": "string", "description": "Claim statement; required when claim_id is not provided."},
            "claim_type": {"type": "string", "description": "fact, definition, requirement, historical or assessment"},
            "source_id": {"type": "integer", "description": "Research source ID from research_record_source"},
            "quote": {"type": "string", "description": "Exact supporting quotation"},
        }

    def execute(self, **kwargs: Any) -> Any:
        claim_id = int(kwargs.get("claim_id") or 0)
        source_id = int(kwargs.get("source_id") or 0)
        quote = str(kwargs.get("quote") or "")
        if claim_id:
            return self.store.attach_evidence(
                self.team_id,
                claim_id,
                source_id,
                quote,
            )
        return self.store.record_claim(
            self.team_id,
            self.agent_id,
            str(kwargs.get("statement") or ""),
            str(kwargs.get("claim_type") or "fact"),
            source_id,
            quote,
        )


class ResearchVerifyClaimTool(_ResearchTool):
    @property
    def name(self) -> str:
        return "research_verify_claim"

    @property
    def description(self) -> str:
        return "Run deterministic evidence verification: every recorded quotation must exist verbatim in its stored source snapshot."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "claim_id": {"type": "integer", "description": "Claim ID"},
            "note": {"type": "string", "description": "Verifier note"},
        }

    def execute(self, **kwargs: Any) -> Any:
        return self.store.verify_claim(
            self.team_id,
            int(kwargs.get("claim_id") or 0),
            self.agent_id,
            str(kwargs.get("note") or ""),
        )

class ResearchRecordConflictTool(_ResearchTool):
    @property
    def name(self) -> str:
        return "research_record_conflict"

    @property
    def description(self) -> str:
        return "Persist a contradiction or conflict between two claims for independent adjudication."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "claim_a": {"type": "integer", "description": "First claim ID"},
            "claim_b": {"type": "integer", "description": "Second claim ID"},
            "conflict_type": {"type": "string", "description": "contradiction, scope_mismatch, temporal_conflict, source_conflict"},
        }

    def execute(self, claim_a: int, claim_b: int, conflict_type: str = "contradiction", **kwargs: Any) -> Any:
        return self.store.record_conflict(
            self.team_id,
            self.agent_id,
            int(claim_a),
            int(claim_b),
            conflict_type,
        )


class ResearchAdjudicateConflictTool(_ResearchTool):
    @property
    def name(self) -> str:
        return "research_adjudicate_conflict"

    @property
    def description(self) -> str:
        return "Adjudicate a recorded research conflict and persist the resolution rationale."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "conflict_id": {"type": "integer", "description": "Conflict ID"},
            "status": {"type": "string", "description": "adjudicated, accepted_uncertainty, rejected"},
            "resolution": {"type": "string", "description": "Evidence-based resolution rationale"},
        }

    def execute(self, conflict_id: int, status: str, resolution: str, **kwargs: Any) -> Any:
        return self.store.adjudicate_conflict(
            self.team_id,
            int(conflict_id),
            self.agent_id,
            status,
            resolution,
        )
