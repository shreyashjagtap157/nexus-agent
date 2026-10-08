"""Research evidence tools exposed to research-mode team workers."""
from __future__ import annotations

from typing import Any

from nexus_agent.tools.base import Tool

from .store import ResearchStore


class _ResearchTool(Tool):
    def __init__(self, db_path, team_id: str, agent_id: str):
        self.store = ResearchStore(db_path)
        self.team_id = team_id
        self.agent_id = agent_id


class ResearchRecordSourceTool(_ResearchTool):
    @property
    def name(self) -> str:
        return "research_record_source"

    @property
    def description(self) -> str:
        return "Persist a fetched source and its exact content into the research evidence ledger."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "url": {"type": "string", "description": "Source URL"},
            "title": {"type": "string", "description": "Source title"},
            "content": {"type": "string", "description": "Exact fetched source text"},
            "provider": {"type": "string", "description": "Discovery/fetch provider"},
        }

    def execute(self, **kwargs: Any) -> Any:
        return self.store.record_source(
            self.team_id,
            self.agent_id,
            str(kwargs.get("url") or ""),
            str(kwargs.get("title") or ""),
            str(kwargs.get("content") or ""),
            str(kwargs.get("provider") or ""),
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
