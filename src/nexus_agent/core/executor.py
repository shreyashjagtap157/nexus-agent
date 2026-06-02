"""Executor Agent — Read-write implementation assistant.

Executes code changes, writes files, and verifies implementations
using full system permission tools (inspired by opencode Build mode).
"""

from __future__ import annotations

import logging
from typing import Any

from nexus_agent.core.agent import AgentEvent, AgentLoop, AgentLoopConfig, AgentMode
from nexus_agent.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class Executor:
    """Read-write implementation agent.

    Uses an agentic loop with full read-write tools to execute structural changes
    based on a pre-defined plan, then verifies the code using tests.
    """

    SYSTEM_PROMPT = """You are the NexusAgent Executor.
Your responsibility is to take a Technical Implementation Plan and execute it completely.

You operate in BUILD mode. You have access to all file operations, shell executions, code editing, and Git tools.
Your goal is to implement the changes cleanly, matching the plan's specifications, and verify their correctness.

## Execution Rules:
1. **Precision**: Edit code precisely, replacing only what is needed.
2. **Safety**: Do not delete unrelated files. Use Git tool to see the diff and track your changes.
3. **Verify**: Always run tests or compile steps after completing edits. If a test fails, fix your code immediately.
4. **Final Check**: Inspect git diff at the end to ensure the code changes are clean and well-structured.
"""

    def __init__(self, provider: LLMProvider, tools: list[Any], **agent_kwargs: Any):
        """Initialize the Executor.

        Args:
            provider: LLM provider instance.
            tools: All workspace tools.
            agent_kwargs: Extra agent config arguments.
        """
        self.tools = tools
        # Filter out keys that conflict with AgentLoopConfig constructor
        conflicting_keys = {"mode", "system_prompt_extra"}
        filtered_kwargs = {k: v for k, v in agent_kwargs.items() if k not in conflicting_keys}
        cfg = AgentLoopConfig(mode=AgentMode.BUILD, system_prompt_extra=self.SYSTEM_PROMPT, **filtered_kwargs)
        self.agent = AgentLoop(
            provider=provider,
            tools=tools,
            config=cfg,
        )

    def execute_plan(self, task: str, plan: str) -> AgentEvent:
        """Execute a task using a pre-defined implementation plan.

        Args:
            task: The original high-level user request.
            plan: The generated Technical Implementation Plan.

        Yields:
            AgentEvent stream.
        """
        prompt = (
            f"Please execute the following task:\n"
            f"\"\"\"\n{task}\n\"\"\"\n\n"
            f"Follow this step-by-step Technical Implementation Plan meticulously:\n"
            f"\"\"\"\n{plan}\n\"\"\"\n\n"
            f"Verify your work when complete by running tests or compilation checks."
        )
        yield from self.agent.run_stream(prompt)

    def clear(self) -> None:
        """Clear conversation history."""
        self.agent.clear_history()
