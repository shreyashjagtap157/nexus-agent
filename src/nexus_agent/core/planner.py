"""Planner Agent — Read-only analytical planning assistant.

Analyzes the codebase context and user requests to create structured
implementation plans without write access (inspired by opencode Plan mode).
"""

from __future__ import annotations

import logging
from typing import Any

from nexus_agent.core.agent import AgentEvent, AgentLoop, AgentLoopConfig, AgentMode
from nexus_agent.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class Planner:
    """Read-only planning agent.

    Uses an agentic loop with read-only permission level tools to analyze the
    codebase and generate a comprehensive implementation plan.
    """

    SYSTEM_PROMPT = """You are the NexusAgent Planner.
Your sole responsibility is to analyze user requests and codebase contexts to create a highly precise, step-by-step Technical Implementation Plan.

You operate in READ-ONLY mode. You have access to tools that let you find, search, read, and list files and execute safe commands (like git status, pytest dry-runs).
You DO NOT have permission to edit or write files, nor run destructive commands.

Your final output MUST be a detailed technical Markdown plan containing:
1. **Goal**: High-level explanation of the changes.
2. **Impacted Components**: Exactly which files, classes, and functions are changing.
3. **Proposed Changes**: Code-level details or diff expectations for each file.
4. **Verification Plan**: Step-by-step instructions on how the Executor should test and verify the changes.

Be analytical, meticulous, and think through edge cases before outputting your plan.
"""

    def __init__(self, provider: LLMProvider, tools: list[Any], **agent_kwargs: Any):
        """Initialize the Planner.

        Args:
            provider: LLM provider instance.
            tools: All workspace tools.
            agent_kwargs: Extra agent config arguments.
        """
        self.read_only_tools = [t for t in tools if getattr(t, "permission_level", "dangerous") == "read-only"]
        # Filter out keys that conflict with AgentLoopConfig constructor
        conflicting_keys = {"mode", "system_prompt_extra"}
        filtered_kwargs = {k: v for k, v in agent_kwargs.items() if k not in conflicting_keys}
        cfg = AgentLoopConfig(mode=AgentMode.PLAN, system_prompt_extra=self.SYSTEM_PROMPT, **filtered_kwargs)
        self.agent = AgentLoop(
            provider=provider,
            tools=self.read_only_tools,
            config=cfg,
        )

    def plan(self, task: str) -> AgentEvent:
        """Generate an implementation plan for a task.

        Args:
            task: The user request/task description.

        Yields:
            AgentEvent stream.
        """
        prompt = (
            f"Please generate a complete, step-by-step Technical Implementation Plan for the following task:\n"
            f"\"\"\"\n{task}\n\"\"\"\n"
            f"First, gather necessary codebase context (list directories, read relevant code files) to understand "
            f"the implementation details before drawing up the plan."
        )
        yield from self.agent.run_stream(prompt)

    def clear(self) -> None:
        """Clear conversation history."""
        self.agent.clear_history()
