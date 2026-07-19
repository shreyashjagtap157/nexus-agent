"""
Council Tool — Multi-perspective decision making.

Wraps the Agent Council as a proper Tool subclass so the primary agent
can convene a panel of expert personas to debate and vote on proposals
during execution.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from nexus_agent.tools.base import Tool

if TYPE_CHECKING:
    from nexus_agent.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class CouncilTool(Tool):
    """Convene an expert council to debate and vote on decisions."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider

    def set_provider(self, provider: LLMProvider) -> None:
        """Late-bind the LLM provider (may not be available at construction)."""
        self._provider = provider

    @property
    def name(self) -> str:
        return "council"

    @property
    def description(self) -> str:
        return (
            "Convene a panel of expert agents to debate a proposal and reach a "
            "decision. The council has 5 members: Strategist, Architect, Security "
            "expert, Pragmatist (feasibility), and UX Advocate. Each member votes "
            "independently. Optional rebuttal round lets them respond to each other. "
            "Use when you need a multi-perspective decision on architecture, design, "
            "or strategy questions."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "topic": {
                "type": "string",
                "description": "The proposal or question to decide on.",
            },
            "context": {
                "type": "string",
                "description": "Supporting context (background, constraints, options).",
                "required": False,
            },
            "rebuttals": {
                "type": "boolean",
                "description": "If true, run a second round where members see each other's votes (default: false).",
                "required": False,
            },
        }

    @property
    def required_params(self) -> list[str]:
        return ["topic"]

    @property
    def permission_level(self) -> str:
        return "read-only"

    @property
    def timeout(self) -> int:
        return 60

    def execute(self, topic: str, **kwargs: Any) -> str:
        if not topic or not topic.strip():
            return "Error: 'topic' is required."
        from nexus_agent.core.debate import Council
        council = Council(
            provider=self._provider,
            approval_threshold=0.6,
        )
        decision = council.convene(
            topic=topic,
            context=kwargs.get("context", ""),
            include_rebuttals=kwargs.get("rebuttals", False),
        )
        lines = [
            f"Council Decision: {decision.consensus.upper()}",
            f"Confidence: {decision.confidence:.0%}",
            f"Duration: {decision.duration:.1f}s",
            "",
        ]
        for vote in decision.votes:
            icon = {"approve": "+1", "abstain": "(_)", "reject": "-1"}.get(vote.vote, "?")
            lines.append(f"  {icon} {vote.member_name}: {vote.reasoning[:200]}")
        lines.append("")
        lines.append(decision.summary)
        return "\n".join(lines)
