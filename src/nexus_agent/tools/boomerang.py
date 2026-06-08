"""
Boomerang Tool — Nested agent task delegation.

Wraps the boomerang task primitives as a proper Tool subclass so the
primary agent can spawn sub-agents, ask for second opinions, and
delegate complex tasks during execution.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from nexus_agent.tools.agent_tools import (
    ask_agent,
    delegate_task,
    get_registry,
    spawn_agent,
)
from nexus_agent.tools.base import Tool

if TYPE_CHECKING:
    from nexus_agent.core.agent import AgentLoop

logger = logging.getLogger(__name__)


class BoomerangTool(Tool):
    """Spawn sub-agents, delegate tasks, and ask other agents for input."""

    def __init__(self, agent_loop: AgentLoop | None = None) -> None:
        self._agent_loop = agent_loop

    def set_agent_loop(self, agent_loop: AgentLoop) -> None:
        """Late-bind the agent loop (created after tools in init flow)."""
        self._agent_loop = agent_loop

    @property
    def name(self) -> str:
        return "boomerang"

    @property
    def description(self) -> str:
        return (
            "Spawn sub-agents for background work, delegate complex tasks, "
            "and ask other agents for expert opinions. Actions: spawn, ask, "
            "delegate, list_tasks. Use 'spawn' to run a self-contained sub-task, "
            "'ask' to query an expert persona, 'delegate' for complex multi-step "
            "tasks, and 'list_tasks' to check on running sub-agents."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "action": {
                "type": "string",
                "description": "One of: spawn, ask, delegate, list_tasks.",
            },
            "prompt": {
                "type": "string",
                "description": "Task description or question (for spawn/ask/delegate).",
                "required": False,
            },
            "delegation_type": {
                "type": "string",
                "description": "Task type: general, research, code, review, debug (for spawn).",
                "required": False,
            },
            "agent_persona": {
                "type": "string",
                "description": "Expert persona: technical_advisor, code_reviewer, architect, debugger (for ask).",
                "required": False,
            },
            "context": {
                "type": "string",
                "description": "Supporting context for ask/delegate.",
                "required": False,
            },
            "timeout": {
                "type": "integer",
                "description": "Max execution time in seconds (default 120).",
                "required": False,
            },
            "wait": {
                "type": "boolean",
                "description": "If true, block until task finishes (default true for spawn, false for delegate).",
                "required": False,
            },
        }

    @property
    def required_params(self) -> list[str]:
        return ["action"]

    @property
    def permission_level(self) -> str:
        return "read-write"

    @property
    def timeout(self) -> int:
        return 120

    def execute(self, action: str, **kwargs: Any) -> str:
        action = (action or "").strip().lower().replace("-", "_")

        if action == "spawn":
            return self._spawn(**kwargs)
        if action == "ask":
            return self._ask(**kwargs)
        if action == "delegate":
            return self._delegate(**kwargs)
        if action == "list_tasks":
            return self._list_tasks()
        return f"Error: unknown action '{action}'. Valid: spawn, ask, delegate, list_tasks."

    def _spawn(self, **kwargs: Any) -> str:
        prompt = kwargs.get("prompt", "")
        if not prompt:
            return "Error: 'prompt' is required for spawn."
        result = spawn_agent(
            prompt=prompt,
            agent_loop=self._agent_loop,
            delegation_type=kwargs.get("delegation_type", "general"),
            timeout=int(kwargs.get("timeout", 120)),
        )
        status = result.get("status", "unknown")
        output = result.get("output", "")
        if status == "completed":
            return f"[Sub-agent {result['task_id']}] completed in {result.get('duration', 0):.1f}s:\n{output}"
        if status == "failed":
            return f"[Sub-agent {result['task_id']}] FAILED: {result.get('error', 'unknown error')}"
        return f"[Sub-agent {result['task_id']}] status: {status}"

    def _ask(self, **kwargs: Any) -> str:
        question = kwargs.get("prompt", "")
        if not question:
            return "Error: 'prompt' (question) is required for ask."
        result = ask_agent(
            question=question,
            context=kwargs.get("context", ""),
            agent_persona=kwargs.get("agent_persona", "technical_advisor"),
            provider=getattr(self._agent_loop, "provider", None) if self._agent_loop else None,
        )
        answer = result.get("answer", "No answer.")
        persona = result.get("persona", "unknown")
        confidence = result.get("confidence", "low")
        return f"[{persona} ({confidence} confidence)] {answer}"

    def _delegate(self, **kwargs: Any) -> str:
        task = kwargs.get("prompt", "")
        if not task:
            return "Error: 'prompt' (task description) is required for delegate."
        result = delegate_task(
            task_description=task,
            wait_for_result=kwargs.get("wait", False),
            timeout=int(kwargs.get("timeout", 300)),
            agent_loop=self._agent_loop,
        )
        status = result.get("status", "unknown")
        output = result.get("output", "")
        if status == "completed":
            return f"[Delegated task {result['task_id']}] completed in {result.get('duration', 0):.1f}s:\n{output}"
        if status in ("running", "pending"):
            return f"[Delegated task {result['task_id']}] {status}."
        return f"[Delegated task {result['task_id']}] FAILED: {result.get('error', 'unknown')}"

    def _list_tasks(self) -> str:
        registry = get_registry()
        active = registry.list_active()
        all_tasks = registry.list_all()
        lines = [f"Total sub-agent tasks: {len(all_tasks)}"]
        if active:
            lines.append(f"Active: {len(active)}")
            for t in active:
                lines.append(f"  [{t['task_id']}] {t['status']} ({t.get('duration', 0):.1f}s)")
        else:
            lines.append("No active tasks.")
        return "\n".join(lines)
