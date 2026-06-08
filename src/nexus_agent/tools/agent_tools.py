"""
Boomerang Tasks — Nested agent spawning for sub-tasks.

Tools that let the primary agent spawn, manage, and collect results from
sub-agents. Each sub-agent runs its own mini agent-loop with isolated
context, tools, and memory — then returns results to the parent.

These tools are meant to be registered in the agent's tool registry,
not imported and called directly (though they can be imported for testing).
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

logger = logging.getLogger(__name__)


class AgentTaskResult:
    """Result from a boomerang sub-agent task."""

    def __init__(
        self,
        task_id: str,
        status: str = "running",
        output: str = "",
        error: str | None = None,
        duration: float = 0.0,
    ):
        self.task_id = task_id
        self.status = status
        self.output = output
        self.error = error
        self.duration = duration

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "duration": round(self.duration, 2),
        }


class BoomerangTaskRegistry:
    """Registry of active boomerang tasks with status tracking."""

    def __init__(self):
        self._tasks: dict[str, AgentTaskResult] = {}
        self._lock = threading.Lock()

    def register(self, task_id: str, result: AgentTaskResult) -> None:
        with self._lock:
            self._tasks[task_id] = result

    def update(self, task_id: str, **kwargs: Any) -> None:
        with self._lock:
            if task_id in self._tasks:
                for k, v in kwargs.items():
                    setattr(self._tasks[task_id], k, v)

    def get(self, task_id: str) -> AgentTaskResult | None:
        with self._lock:
            return self._tasks.get(task_id)

    def list_active(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                t.to_dict() for t in self._tasks.values()
                if t.status in ("running", "pending")
            ]

    def list_all(self) -> list[dict[str, Any]]:
        with self._lock:
            return [t.to_dict() for t in self._tasks.values()]


# Singleton registry — shared across all agent instances
_task_registry = BoomerangTaskRegistry()


def get_registry() -> BoomerangTaskRegistry:
    return _task_registry


def spawn_agent(
    prompt: str,
    agent_loop: Any,
    delegation_type: str = "general",
    timeout: int = 120,
    tools: list[str] | None = None,
) -> dict[str, Any]:
    """Spawn a sub-agent to handle a self-contained task.

    The sub-agent runs its own reasoning loop with isolated context
    and returns results as structured output.

    Args:
        prompt: The task description for the sub-agent.
        agent_loop: The parent AgentLoop instance (injected by tool dispatcher).
        delegation_type: 'general', 'research', 'code', 'review', or 'debug'.
        timeout: Maximum execution time in seconds.
        tools: Subset of tool names to grant the sub-agent (None = all).

    Returns:
        Dict with 'task_id', 'status', 'output', 'error', 'duration'.
    """
    task_id = f"bt:{uuid.uuid4().hex[:12]}"
    result = AgentTaskResult(task_id=task_id, status="running")
    _task_registry.register(task_id, result)
    start = time.time()

    try:
        sub_context = (
            f"[Boomerang Task — {delegation_type}]\n"
            f"Task ID: {task_id}\n"
            f"Parent: {getattr(agent_loop, 'session_id', 'unknown')}\n\n"
            f"{prompt}\n\n"
            "Output your final answer inside <result>...</result> tags."
        )

        if hasattr(agent_loop, "run") and callable(agent_loop.run):
            sub_output = agent_loop.run(
                user_input=sub_context,
                max_iterations=10,
                tools_allowlist=tools,
            )
        else:
            sub_output = _fallback_execute(prompt, delegation_type)

        elapsed = time.time() - start
        raw = sub_output if isinstance(sub_output, str) else str(sub_output or "")

        import re as _re
        result_match = _re.search(r"<result>(.*?)</result>", raw, _re.DOTALL)
        output = result_match.group(1).strip() if result_match else raw.strip()

        result.status = "completed"
        result.output = output
        result.duration = elapsed
        _task_registry.update(task_id, status="completed", output=output, duration=elapsed)

    except Exception as e:
        elapsed = time.time() - start
        result.status = "failed"
        result.error = str(e)
        result.duration = elapsed
        _task_registry.update(task_id, status="failed", error=str(e), duration=elapsed)
        logger.warning("Boomerang task %s failed: %s", task_id, e)

    return result.to_dict()


def ask_agent(
    question: str,
    context: str = "",
    agent_persona: str = "technical_advisor",
    provider: Any = None,
) -> dict[str, Any]:
    """Ask another agent for their perspective on a specific question.

    Useful for getting a second opinion or expert advice without
    spawning a full sub-agent loop.

    Args:
        question: The question to ask.
        context: Relevant context for the question.
        agent_persona: Persona for the responding agent (e.g.,
            'technical_advisor', 'code_reviewer', 'architect').
        provider: LLM provider instance. If None, falls back to heuristic.

    Returns:
        Dict with 'answer', 'persona', 'confidence'.
    """
    task_id = f"ask:{uuid.uuid4().hex[:8]}"
    start = time.time()

    system_prompts = {
        "technical_advisor": "You are a senior technical advisor. Answer the question concisely with technical depth.",
        "code_reviewer": "You are an expert code reviewer. Analyze the code and provide detailed feedback.",
        "architect": "You are a software architect. Evaluate the design and suggest improvements.",
        "debugger": "You are a debugging specialist. Find the root cause and suggest fixes.",
    }
    system_prompt = system_prompts.get(
        agent_persona,
        "You are a helpful AI assistant. Answer the question concisely.",
    )

    try:
        if provider and hasattr(provider, "chat_completion"):
            from nexus_agent.llm.base import Message, Role
            messages = [
                Message(role=Role.SYSTEM, content=system_prompt),
                Message(role=Role.USER, content=f"Context:\n{context}\n\nQuestion:\n{question}" if context else question),
            ]
            response = provider.chat_completion(messages=messages, temperature=0.3, max_tokens=1024)
            answer = (response.content or "").strip()
        else:
            answer = _heuristic_answer(question, agent_persona)

        elapsed = time.time() - start
        return {
            "task_id": task_id,
            "answer": answer or "No answer generated.",
            "persona": agent_persona,
            "confidence": "medium" if answer else "low",
            "duration": round(elapsed, 2),
        }
    except Exception as e:
        logger.warning("ask_agent failed: %s", e)
        return {
            "task_id": task_id,
            "answer": f"Error: {e}",
            "persona": agent_persona,
            "confidence": "low",
            "duration": round(time.time() - start, 2),
        }


def delegate_task(
    task_description: str,
    tools_to_expose: list[str] | None = None,
    wait_for_result: bool = True,
    timeout: int = 300,
    agent_loop: Any = None,
) -> dict[str, Any]:
    """Delegate a complex task to a sub-agent with full tool access.

    Unlike spawn_agent which returns text, delegate_task can optionally
    block until the sub-agent finishes (or runs up to timeout).

    Args:
        task_description: What the sub-agent should do.
        tools_to_expose: Tool names the sub-agent may use (None = all).
        wait_for_result: If True, block until task finishes.
        timeout: Maximum wall-clock time in seconds.
        agent_loop: Parent AgentLoop instance.

    Returns:
        Dict with 'task_id', 'status', 'result', 'tool_calls_made'.
    """
    task_id = f"dt:{uuid.uuid4().hex[:12]}"
    result = AgentTaskResult(task_id=task_id, status="pending")
    _task_registry.register(task_id, result)
    start = time.time()

    def _run():
        try:
            result.status = "running"
            _task_registry.update(task_id, status="running")

            wrapped = (
                f"[Delegated Task — {task_id}]\n"
                f"{task_description}\n\n"
                "When finished, wrap your final answer in <result>...</result>."
            )

            if agent_loop and hasattr(agent_loop, "run") and callable(agent_loop.run):
                sub_output = agent_loop.run(
                    user_input=wrapped,
                    max_iterations=15,
                    tools_allowlist=tools_to_expose,
                )
            else:
                sub_output = _fallback_execute(task_description, "delegated")

            raw = sub_output if isinstance(sub_output, str) else str(sub_output or "")
            import re as _re
            result_match = _re.search(r"<result>(.*?)</result>", raw, _re.DOTALL)
            output = result_match.group(1).strip() if result_match else raw.strip()

            elapsed = time.time() - start
            result.status = "completed"
            result.output = output
            result.duration = elapsed
            _task_registry.update(task_id, status="completed", output=output, duration=elapsed)
        except Exception as e:
            elapsed = time.time() - start
            result.status = "failed"
            result.error = str(e)
            result.duration = elapsed
            _task_registry.update(task_id, status="failed", error=str(e), duration=elapsed)

    task_thread = threading.Thread(target=_run, daemon=True)
    task_thread.start()

    if wait_for_result:
        task_thread.join(timeout=timeout)
        final = _task_registry.get(task_id)
        return final.to_dict() if final else result.to_dict()

    return result.to_dict()


def _fallback_execute(prompt: str, task_type: str) -> str:
    """Fallback when no agent loop is available (useful for testing)."""
    prompt_lower = prompt.lower()
    if "count" in prompt_lower or "list" in prompt_lower:
        return f"<result>Fallback execution for '{task_type}' task completed. Prompt: {prompt[:100]}...</result>"
    return f"<result>Fallback {task_type} agent executed: task acknowledged but no LLM provider available.</result>"


def _heuristic_answer(question: str, persona: str) -> str:
    """Heuristic fallback answer when no LLM provider is available."""
    q = question.lower()
    if "security" in q or "vulnerability" in q:
        return "Heuristic: Review input validation, authentication, and dependency versions."
    if "perform" in q or "slow" in q:
        return "Heuristic: Check for N+1 queries, caching, and synchronous I/O in hot paths."
    if "design" in q or "architect" in q:
        return "Heuristic: Consider separation of concerns, interface boundaries, and testability."
    return f"Heuristic response for '{persona}': unable to generate a detailed answer without an LLM provider."
