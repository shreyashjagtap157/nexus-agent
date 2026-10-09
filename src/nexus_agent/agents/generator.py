"""LLM-assisted user agent generator."""

from __future__ import annotations

import json
import re
from typing import Any

from nexus_agent.llm.base import LLMProvider, Message, Role

from .models import AgentScope, AgentSpec


class AgentGenerator:
    SYSTEM_PROMPT = """You are NexusAgent's professional agent architect.
Generate reusable agent definitions, not an answer to the underlying task.
Create distinct, non-overlapping professional roles with concrete missions,
instructions, tools, permissions, dependencies and optional provider/model routing.
Never include API keys or secrets. Return JSON only."""

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def generate(self, request: str, max_agents: int = 8) -> list[AgentSpec]:
        if not request.strip():
            raise ValueError("Agent generation request cannot be empty.")
        prompt = f"""Request:
{request}

Maximum agents: {max_agents}

Return:
{{"agents":[{{"id":"slug","name":"...","profession":"...","description":"...",
"mission":"...","instructions":"...","tool_categories":["read","write","shell","web","git","mcp","browser","code_intel","lsp","memory","research","formal"],
"write_access":false,"reviewer":false,"dependencies":[],"model_role":"default",
"provider":null,"model":null,"fallbacks":[],"tags":[],"metadata":{{}}}}]}}"""
        response = self.provider.chat_completion(
            [
                Message(role=Role.SYSTEM, content=self.SYSTEM_PROMPT),
                Message(role=Role.USER, content=prompt),
            ],
            temperature=0.0,
            max_tokens=12000,
        )
        try:
            data = json.loads(response.content or "{}")
        except json.JSONDecodeError as exc:
            match = re.search(r"\{.*\}", response.content or "", flags=re.DOTALL)
            if not match:
                raise ValueError("Agent generator returned invalid JSON.") from exc
            data = json.loads(match.group(0))
        raw = data.get("agents", []) if isinstance(data, dict) else []
        specs: list[AgentSpec] = []
        for item in raw[:max_agents]:
            if not isinstance(item, dict):
                continue
            specs.append(AgentSpec.from_dict(item, AgentScope.USER))
        if not specs:
            raise ValueError("Agent generator produced no valid agent definitions.")
        return specs

    def preview(self, request: str, max_agents: int = 8) -> list[dict[str, Any]]:
        return [spec.to_dict() for spec in self.generate(request, max_agents)]
