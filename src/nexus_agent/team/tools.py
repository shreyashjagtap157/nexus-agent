"""Shared blackboard tools exposed to team workers."""
from __future__ import annotations

from typing import Any

from nexus_agent.tools.base import Tool

from .store import TeamStore


class TeamSendMessageTool(Tool):
    def __init__(self, store: TeamStore, team_id: str, sender_id: str):
        self.store = store
        self.team_id = team_id
        self.sender_id = sender_id

    @property
    def name(self) -> str:
        return "team_send_message"

    @property
    def description(self) -> str:
        return "Send a finding, question, warning, handoff or review request to another team worker or to the whole team."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "recipient_id": {"type": "string", "description": "Target agent ID. Empty broadcasts to the whole team."},
            "message_type": {"type": "string", "description": "QUESTION, FINDING, WARNING, REVIEW_REQUEST, HANDOFF or UPDATE"},
            "topic": {"type": "string", "description": "Short topic"},
            "message": {"type": "string", "description": "Message body"},
        }

    @property
    def permission_level(self) -> str:
        return "read-write"

    def execute(self, **kwargs: Any) -> Any:
        return self.store.message(
            self.team_id,
            self.sender_id,
            str(kwargs.get("message_type") or "UPDATE"),
            {"message": str(kwargs.get("message") or "")},
            recipient_id=str(kwargs.get("recipient_id") or "") or None,
            topic=str(kwargs.get("topic") or "") or None,
        )


class TeamReadMessagesTool(Tool):
    def __init__(self, store: TeamStore, team_id: str, sender_id: str):
        self.store = store
        self.team_id = team_id
        self.sender_id = sender_id

    @property
    def name(self) -> str:
        return "team_read_messages"

    @property
    def description(self) -> str:
        return "Read broadcast and direct messages sent to this worker."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"since": {"type": "number", "description": "Unix timestamp; 0 reads all retained messages."}}

    def execute(self, **kwargs: Any) -> Any:
        return self.store.messages(
            self.team_id,
            recipient_id=self.sender_id,
            since=float(kwargs.get("since", 0.0) or 0.0),
        )
