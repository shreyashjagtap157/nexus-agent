"""
Core Agentic Loop — The heart of NexusAgent.

Implements the Gather → Act → Verify reasoning cycle inspired by
claude-code and codex. The agent autonomously:
1. Gathers context from the codebase and conversation
2. Reasons about the task and selects tools
3. Executes tool calls with permission checks
4. Observes results and iterates until the task is complete

Supports:
- Streaming responses for real-time TUI/GUI updates
- Tool calling with permission evaluation
- Context window management with auto-compaction
- Checkpoint creation for rollback
- Sub-agent delegation
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    pass

from nexus_agent.core.context import ContextManager
from nexus_agent.core.self_heal import SelfHealingExecutor
from nexus_agent.llm.base import (
    LLMProvider,
    LLMResponse,
    Message,
    Role,
    ToolCall,
    ToolDefinition,
)

logger = logging.getLogger(__name__)


class AgentMode(str, Enum):
    """Agent operating modes (inspired by opencode Plan/Build)."""
    AUTO = "auto"       # Agent decides when to plan vs execute
    PLAN = "plan"       # Read-only analysis and planning
    BUILD = "build"     # Full read/write execution
    REVIEW = "review"   # Code review mode


class AgentState(str, Enum):
    """Current state of the agent loop."""
    IDLE = "idle"
    THINKING = "thinking"
    TOOL_CALLING = "tool_calling"
    WAITING_APPROVAL = "waiting_approval"
    EXECUTING = "executing"
    ERROR = "error"
    DONE = "done"


@runtime_checkable
class _ToolLike(Protocol):
    """Protocol for tool-like objects used by the agent."""
    name: str
    description: str
    parameters: dict[str, Any]
    required_params: list[str]
    permission_level: str
    def execute(self, **kwargs: Any) -> Any: ...


@dataclass
class ToolResult:
    """Result of a tool execution."""
    tool_call_id: str
    tool_name: str
    output: str
    success: bool = True
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentEventType(str, Enum):
    """Agent event types for UI updates."""
    STATE_CHANGE = "state_change"
    THINKING = "thinking"
    CONTENT = "content"
    CONTENT_CHUNK = "content_chunk"
    CONTENT_COMPLETE = "content_complete"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    DONE = "done"


@dataclass
class AgentEvent:
    """Event emitted by the agent for UI updates."""
    type: AgentEventType
    data: Any = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentLoopConfig:
    """Configuration for the AgentLoop reasoning engine.

    All parameters have sensible defaults so minimal config is needed.
    """
    mode: AgentMode = AgentMode.AUTO
    workspace: Path | None = None
    max_iterations: int = 50
    temperature: float = 0.1
    max_tokens: int = 4096
    permission_callback: Callable[..., bool] | None = None
    system_prompt_extra: str = ""
    effort_level: str = "medium"
    goal: str = ""
    tool_timeout: float = 120.0
    max_input_chars: int = 50000


class AgentLoop:
    """The core agentic reasoning loop.

    Manages the conversation between the user, the LLM, and tools,
    implementing the gather → act → verify cycle.

    Usage:
        agent = AgentLoop(
            provider=local_engine,
            tools=tool_registry.get_tools(),
            config=AgentLoopConfig(mode=AgentMode.AUTO),
        )

        for event in agent.run("Fix the bug in utils.py"):
            handle_event(event)
    """

    # Hardcoded thresholds (parameterized for configurability)
    DEFAULT_TOOL_CONFIDENCE: float = 0.9
    DEFAULT_FINISH_CONFIDENCE: float = 1.0
    WARN_MESSAGE_THRESHOLD: int = 60
    DISPLAY_TRUNCATE_LENGTH: int = 2000

    EFFORT_CONFIG: dict[str, dict[str, Any]] = {
        "low": {
            "max_iterations": 15,
            "temperature": 0.3,
            "max_tokens": 2048,
            "reflection": False,
            "multi_pass": False,
            "description": "Fast responses, minimal iteration",
        },
        "medium": {
            "max_iterations": 25,
            "temperature": 0.15,
            "max_tokens": 4096,
            "reflection": False,
            "multi_pass": False,
            "description": "Balanced speed and quality",
        },
        "high": {
            "max_iterations": 50,
            "temperature": 0.1,
            "max_tokens": 8192,
            "reflection": True,
            "multi_pass": False,
            "description": "Thorough reasoning with reflection",
        },
        "xhigh": {
            "max_iterations": 80,
            "temperature": 0.05,
            "max_tokens": 16384,
            "reflection": True,
            "multi_pass": True,
            "description": "Deep reasoning with multi-pass review",
        },
        "max": {
            "max_iterations": 120,
            "temperature": 0.01,
            "max_tokens": 32768,
            "reflection": True,
            "multi_pass": True,
            "description": "Maximum intelligence, exhaustive analysis",
        },
    }

    # System prompt that defines the agent's behavior
    SYSTEM_PROMPT = """You are NexusAgent, an expert AI coding assistant running locally on the user's machine.

You have access to the user's filesystem and can read, write, and execute code directly.
You operate in an agentic loop: you can use tools to gather information, make changes, and verify results.

## Core Principles
1. **Gather Context First**: Before making changes, understand the codebase structure and relevant files.
2. **Plan Before Acting**: For complex tasks, create a plan and explain your approach.
3. **Make Precise Changes**: Use targeted edits rather than rewriting entire files.
4. **Verify Results**: After making changes, verify they work (run tests, check syntax, etc.).
5. **Be Transparent**: Explain your reasoning and what you're doing at each step.

## Working Directory
Current workspace: {workspace}

## Tool Usage
- Use tools to read files, search code, execute commands, and edit files.
- Always check file contents before editing them.
- After making changes, verify they compile/run correctly.
- Ask for permission before executing destructive operations.

## Response Format
- Use Markdown formatting for your responses.
- Show code changes as diffs when possible.
- Be concise but thorough in explanations.
"""

    def __init__(
        self,
        provider: LLMProvider,
        tools: list[_ToolLike] | None = None,
        config: AgentLoopConfig | None = None,
        self_healing_executor: SelfHealingExecutor | None = None,
    ):
        """Initialize the agent loop.

        Args:
            provider: LLM provider (local engine or cloud).
            tools: List of available tools.
            config: AgentLoopConfig with all optional settings.
            self_healing_executor: Optional SelfHealingExecutor instance.
        """
        cfg = config or AgentLoopConfig()
        self.provider = provider
        self.tools = tools or []
        self.mode = cfg.mode
        self.workspace = cfg.workspace or Path.cwd()
        self.temperature = cfg.temperature
        self.max_tokens = cfg.max_tokens
        self.permission_callback = cfg.permission_callback
        self.system_prompt_extra = cfg.system_prompt_extra
        self.effort_level = cfg.effort_level.lower().strip()
        self.goal = cfg.goal
        self.tool_timeout = cfg.tool_timeout
        self.max_input_chars = cfg.max_input_chars
        self._healer = self_healing_executor or SelfHealingExecutor(max_retries=3)

        # Apply effort-level config mapping
        effort_map = self.EFFORT_CONFIG.get(self.effort_level, self.EFFORT_CONFIG["medium"])
        self.max_iterations = effort_map["max_iterations"]
        self.temperature = effort_map["temperature"]
        self.max_tokens = min(effort_map["max_tokens"], cfg.max_tokens) if cfg.max_tokens != self.max_tokens else effort_map["max_tokens"]
        self._reflection_enabled = effort_map["reflection"]
        self._multi_pass_enabled = effort_map.get("multi_pass", False)

        # Conversation state
        self.messages: list[Message] = []
        self.state = AgentState.IDLE
        self.iteration_count = 0
        self._lock = threading.Lock()
        self.session_id = uuid.uuid4().hex[:12]

        # Core Architecture telemetry & reflection
        from nexus_agent.core.nla_telemetry import NLATelemetry as _NLATelemetry
        from nexus_agent.core.reflection import ReflectionEngine as _ReflectionEngine
        self.nla_telemetry = _NLATelemetry(self.session_id, self.workspace)
        self.reflection_engine = _ReflectionEngine(provider=self.provider)

        # Context manager for automatic compaction
        self._ctx_mgr = ContextManager(provider=self.provider)

        # Reusable thread pool for tool execution
        self._tool_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="agent_tool")

        # Trace event buffer (flushed every 10 events or on completion)
        self._trace_buffer: list[dict[str, Any]] = []

        # Streaming state (used by run_stream)
        self._stream_content: str = ""
        self._stream_tool_calls: list[ToolCall] = []

        # Tool registry (name → tool instance)
        self._tool_map: dict[str, Any] = {}
        self._tool_definitions: list[ToolDefinition] = []
        self.disabled_tools: set[str] = set()
        self._setup_tools()

    def _setup_tools(self) -> None:
        """Register tools and create LLM-compatible definitions."""
        for tool in self.tools:
            self._tool_map[tool.name] = tool
            self._tool_definitions.append(ToolDefinition(
                name=tool.name,
                description=tool.description,
                parameters=tool.parameters,
                required_params=tool.required_params,
            ))

    def _build_system_prompt(self) -> str:
        """Build the system prompt with workspace context."""
        prompt = self.SYSTEM_PROMPT.format(workspace=self.workspace)

        # State-of-the-art auto-discovery of workspace standard files (e.g. CLAUDE.md, AGENT.md)
        rules_files = ["CLAUDE.md", ".nexus-agent.md", "AGENT.md", "developer.md"]
        for rf in rules_files:
            rf_path = Path(self.workspace) / rf
            if rf_path.exists():
                try:
                    rules_content = rf_path.read_text(encoding="utf-8", errors="ignore")
                    if len(rules_content) > 50000:
                        logger.warning(f"Workspace rules file {rf} is too large (>50KB). Skipping for security.")
                        continue
                    lower_content = rules_content.lower()
                    danger_keywords = [
                        "ignore all previous", "ignore previous instructions", "override system prompt",
                        "you are now", "new system instructions", "system override"
                    ]
                    if any(dk in lower_content for dk in danger_keywords):
                        logger.warning(f"Potential prompt injection pattern detected in workspace rules file {rf}. Skipping.")
                        continue
                    if rules_content.strip():
                        prompt += f"\n\n## WORKSPACE STANDARDS & INSTRUCTIONS (from {rf})\n{rules_content}"
                        logger.info(f"Loaded workspace standards from {rf}")
                        break
                except (OSError, PermissionError, UnicodeDecodeError) as e:
                    logger.debug(f"Failed to read workspace rules file {rf}: {e}")

        if self.goal:
            prompt += f"\n\n## ACTIVE OBJECTIVE\nYour current Hermes goal is: **{self.goal}**\nConcentrate strictly on achieving this objective. Avoid out-of-scope edits."

        if self.mode == AgentMode.PLAN:
            prompt += "\n\n## Mode: PLAN\nYou are in read-only planning mode. Analyze and plan but DO NOT make any file changes."
        elif self.mode == AgentMode.BUILD:
            prompt += "\n\n## Mode: BUILD\nYou have full read/write access. Execute the plan and make necessary changes."
        elif self.mode == AgentMode.REVIEW:
            prompt += "\n\n## Mode: REVIEW\nYou are reviewing code. Provide analysis, suggestions, and identify issues."

        if self.system_prompt_extra:
            prompt += f"\n\n{self.system_prompt_extra}"

        return prompt

    def _trace_event(self, event_type: str, data: Any) -> None:
        """Log structured agent event to local JSONL trace telemetry.

        Events are buffered in memory and flushed in batches to avoid
        per-event file I/O in the hot agent loop.
        """
        # Serialize non-serializable objects cleanly
        serializable_data = data
        if isinstance(data, Exception):
            serializable_data = str(data)
        elif hasattr(data, "value"):  # Enum support
            serializable_data = data.value

        self._trace_buffer.append({
            "timestamp": time.time(),
            "session_id": self.session_id,
            "iteration": self.iteration_count,
            "mode": self.mode.value,
            "state": self.state.value,
            "event_type": event_type,
            "data": serializable_data,
        })

        if len(self._trace_buffer) >= 10:
            self._flush_trace_buffer()

    def _flush_trace_buffer(self) -> None:
        """Flush buffered trace events and NLA telemetry to disk."""
        self.nla_telemetry.flush()
        try:
            trace_dir = Path(self.workspace) / ".nexus-agent" / "traces"
            trace_dir.mkdir(parents=True, exist_ok=True)
            summary = self.nla_telemetry.generate_session_summary()
            summary_file = trace_dir / f"summary_{self.session_id}.md"
            summary_file.write_text(summary, encoding="utf-8")
        except (OSError, ValueError) as summary_err:
            logger.debug(f"Failed to auto-generate NLA telemetry summary: {summary_err}")

        if not self._trace_buffer:
            return
        try:
            trace_dir = Path(self.workspace) / ".nexus-agent" / "traces"
            trace_dir.mkdir(parents=True, exist_ok=True)
            trace_file = trace_dir / f"trace_{self.session_id}.jsonl"
            lines = "\n".join(json.dumps(e) for e in self._trace_buffer) + "\n"
            with open(trace_file, "a", encoding="utf-8") as f:
                f.write(lines)
            self._trace_buffer.clear()
        except (OSError, ValueError) as e:
            logger.warning(f"Failed to flush trace buffer: {e}")

    def _emit_event(self, event_type: AgentEventType | str, data: Any = None) -> AgentEvent:
        """Helper to create, trace, and return an AgentEvent."""
        if isinstance(event_type, str):
            event_type = AgentEventType(event_type)
        event = AgentEvent(type=event_type, data=data)
        self._trace_event(event_type.value, data)
        return event


    def _get_tool_definitions(self) -> list[ToolDefinition] | None:
        """Get tool definitions based on current mode."""
        disabled = getattr(self, "disabled_tools", set())
        if self.mode == AgentMode.PLAN:
            # Plan mode: only read-only tools
            return [td for td in self._tool_definitions
                    if self._tool_map[td.name].permission_level == "read-only"
                    and td.name not in disabled]

        if not self._tool_definitions:
            return None

        return [td for td in self._tool_definitions if td.name not in disabled]

    def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call with permission checking.

        Args:
            tool_call: The tool call to execute.

        Returns:
            ToolResult with output or error.
        """
        tool = self._tool_map.get(tool_call.name)
        if not tool:
            return ToolResult(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                output="",
                success=False,
                error=f"Unknown tool: {tool_call.name}",
            )

        # Permission check
        if self.permission_callback:
            if not self.permission_callback(tool_call):
                return ToolResult(
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                    output="",
                    success=False,
                    error="Permission denied by user",
                )

        # Execute with SelfHealingExecutor retry loop and timeout
        def _do_execute() -> ToolResult:
            def on_heal_event(ev_name: str, ev_data: Any):
                logger.info(f"Self-heal event emit: {ev_name} -> {ev_data}")

            heal_res = self._healer.execute_with_healing(
                tool=tool,
                arguments=tool_call.arguments,
                tool_call_id=tool_call.id,
                on_event=on_heal_event,
            )

            return ToolResult(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                output=heal_res.final_output,
                success=heal_res.success,
                error=heal_res.diagnosis if not heal_res.success else None,
            )

        try:
            fut = self._tool_executor.submit(_do_execute)
            return fut.result(timeout=self.tool_timeout)
        except TimeoutError:
            logger.error(f"Tool execution timed out ({tool_call.name}) after {self.tool_timeout}s")
            return ToolResult(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                output="",
                success=False,
                error=f"Tool execution timed out after {self.tool_timeout}s",
            )
        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"Tool execution error ({tool_call.name}): {e}")
            return ToolResult(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                output="",
                success=False,
                error=str(e),
            )

    def _init_conversation(self, user_input: str) -> str:
        if not self.messages:
            system_prompt = self._build_system_prompt()
            self.messages.append(Message(role=Role.SYSTEM, content=system_prompt))

        truncated_input = user_input[:self.max_input_chars]
        if self._multi_pass_enabled:
            planning_prompt = f"[Task]\n{truncated_input}\n\n[Plan-First]\nBefore starting, create a clear step-by-step plan for how you will approach this task. Break it down into phases: context gathering, implementation, verification. Then execute each phase."
            self.messages.append(Message(role=Role.USER, content=planning_prompt))
        else:
            self.messages.append(Message(role=Role.USER, content=truncated_input))
        self.iteration_count = 0
        return truncated_input

    def _check_and_compact(self) -> None:
        if self._ctx_mgr.should_compact(self.messages):
            self.compact_context()

    def _log_iteration_telemetry(self, response: LLMResponse) -> None:
        try:
            self.nla_telemetry.log_iteration(
                thought_process=response.content or "No thought content",
                strategy_selected="tool_calling" if response.has_tool_calls else "finish",
                tools_considered=[tc.name for tc in response.tool_calls] if response.has_tool_calls else [],
                confidence_score=self.DEFAULT_TOOL_CONFIDENCE if response.has_tool_calls else self.DEFAULT_FINISH_CONFIDENCE,
                alternative_paths=[]
            )
        except (OSError, ValueError) as telemetry_err:
            logger.warning(f"Telemetry log failed: {telemetry_err}")

    def _process_tool_calls(
        self, tool_calls: list[ToolCall]
    ) -> Iterator[AgentEvent]:
        with self._lock:
            self.state = AgentState.TOOL_CALLING

        for tool_call in tool_calls:
            yield self._emit_event("tool_call", {
                "id": tool_call.id,
                "name": tool_call.name,
                "arguments": tool_call.arguments,
            })

            with self._lock:
                self.state = AgentState.EXECUTING
            result = self._execute_tool(tool_call)

            yield self._emit_event("tool_result", {
                "id": result.tool_call_id,
                "name": result.tool_name,
                "output": result.output[:self.DISPLAY_TRUNCATE_LENGTH],
                "success": result.success,
                "error": result.error,
            })

            with self._lock:
                self.messages.append(Message(
                    role=Role.TOOL,
                    content=result.output if result.success else f"Error: {result.error}",
                    tool_call_id=result.tool_call_id,
                    name=result.tool_name,
                ))

        with self._lock:
            if len(self.messages) > self.WARN_MESSAGE_THRESHOLD:
                logger.warning(f"Conversation has {len(self.messages)} messages — consider /compact")

    def _handle_reflection(self, user_input: str, response: LLMResponse) -> tuple[bool, list[AgentEvent]]:
        if not self._reflection_enabled or not response.content:
            return False, []
        events = [self._emit_event("thinking", "Performing high-effort reflection pass...")]
        critique = self.reflection_engine.evaluate(
            user_request=user_input,
            agent_output=response.content
        )
        if not critique.approved:
            events.append(self._emit_event("thinking", f"Reflection failed (Score: {critique.score}). Injecting self-correction prompt..."))
            with self._lock:
                self.messages.append(Message(
                    role=Role.USER,
                    content=critique.to_feedback_prompt()
                ))
            return True, events
        return False, events

    def _call_llm(self) -> LLMResponse:
        response = self.provider.chat_completion(
            messages=self.messages,
            tools=self._get_tool_definitions(),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return response

    def run(self, user_input: str) -> Iterator[AgentEvent]:
        truncated_input = self._init_conversation(user_input)
        yield self._emit_event("state_change", AgentState.THINKING)

        while True:
            with self._lock:
                if self.iteration_count >= self.max_iterations:
                    break
                self.iteration_count += 1
                self._check_and_compact()
            self.state = AgentState.THINKING

            try:
                yield self._emit_event("thinking", f"Iteration {self.iteration_count}")
                response = self._call_llm()
            except (RuntimeError, ValueError, OSError) as e:
                self.state = AgentState.ERROR
                yield self._emit_event("error", str(e))
                self._flush_trace_buffer()
                return

            if response.content:
                yield self._emit_event("content", response.content)

            self._log_iteration_telemetry(response)

            with self._lock:
                self.messages.append(Message(
                    role=Role.ASSISTANT,
                    content=response.content,
                    tool_calls=response.tool_calls,
                ))

            if response.has_tool_calls:
                yield from self._process_tool_calls(response.tool_calls)
                continue

            rework_needed, reflection_events = self._handle_reflection(truncated_input, response)
            for ev in reflection_events:
                yield ev
            if rework_needed:
                continue

            with self._lock:
                self.state = AgentState.DONE
            yield self._emit_event("done", {
                "iterations": self.iteration_count,
                "finish_reason": response.finish_reason,
            })
            self._flush_trace_buffer()
            return

        with self._lock:
            self.state = AgentState.DONE
        yield self._emit_event("done", {
            "iterations": self.iteration_count,
            "max_reached": True,
        })
        self._flush_trace_buffer()

    def _run_streaming(self) -> Iterator[AgentEvent]:
        if not getattr(self.provider, 'supports_streaming', False):
            logger.debug("Provider doesn't support streaming, falling back to non-streaming")
            response = self.provider.chat_completion(
                messages=self.messages,
                tools=self._get_tool_definitions(),
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            self._stream_content = response.content or ""
            self._stream_tool_calls = response.tool_calls or []
            return

        for chunk in self.provider.chat_completion_stream(
            messages=self.messages,
            tools=self._get_tool_definitions(),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        ):
            if chunk.content:
                self._stream_content += chunk.content
                yield self._emit_event("content_chunk", chunk.content)
            if chunk.tool_calls:
                self._stream_tool_calls.extend(chunk.tool_calls)
            if chunk.is_final:
                break

    def run_stream(self, user_input: str) -> Iterator[AgentEvent]:
        truncated_input = self._init_conversation(user_input)
        yield self._emit_event("state_change", AgentState.THINKING)

        while True:
            with self._lock:
                if self.iteration_count >= self.max_iterations:
                    break
                self.iteration_count += 1
                self._check_and_compact()
            self.state = AgentState.THINKING

            yield self._emit_event("thinking", f"Iteration {self.iteration_count}")

            self._stream_content = ""
            self._stream_tool_calls: list[ToolCall] = []

            try:
                yield from self._run_streaming()
            except (RuntimeError, ValueError, OSError) as e:
                self.state = AgentState.ERROR
                yield self._emit_event("error", str(e))
                self._flush_trace_buffer()
                return

            if self._stream_content:
                yield self._emit_event("content_complete", self._stream_content)

            self._log_iteration_telemetry(
                type('LLMResponse', (), {
                    'content': self._stream_content,
                    'has_tool_calls': bool(self._stream_tool_calls),
                    'tool_calls': self._stream_tool_calls,
                })()
            )

            with self._lock:
                self.messages.append(Message(
                    role=Role.ASSISTANT,
                    content=self._stream_content or None,
                    tool_calls=self._stream_tool_calls or None,
                ))

            if self._stream_tool_calls:
                yield from self._process_tool_calls(self._stream_tool_calls)
                continue

            rework_needed, reflection_events = self._handle_reflection(truncated_input, type('LLMResponse', (), {
                'content': self._stream_content,
                'has_tool_calls': False,
                'tool_calls': [],
            })())
            for ev in reflection_events:
                yield ev
            if rework_needed:
                continue

            # Multi-pass review for xhigh+ efforts
            if self._multi_pass_enabled and self._stream_content:
                yield self._emit_event("thinking", "Review pass: verifying completeness...")
                review_msg = (
                    "[Review Request]\nOriginal task: "
                    f"{truncated_input[:500]}\n\n"
                    "Your completed work is above. Review it carefully:\n"
                    "1. Does it fully address all parts of the request?\n"
                    "2. Are there any edge cases, errors, or missing details?\n"
                    "3. Did you verify the solution works?\n"
                    "4. If changes were made, are they correct and complete?\n\n"
                    'If the work is complete and correct, say "Looks good" with a brief summary. '
                    "If anything is missing or wrong, fix it now."
                )
                with self._lock:
                    self.messages.append(Message(role=Role.USER, content=review_msg))
                self._stream_content = ""
                self._stream_tool_calls = []
                try:
                    yield from self._run_streaming()
                except (RuntimeError, ValueError, OSError) as e:
                    pass
                if self._stream_content:
                    yield self._emit_event("content_complete", self._stream_content)
                    with self._lock:
                        self.messages.append(Message(
                            role=Role.ASSISTANT,
                            content=self._stream_content or None,
                        ))

            self.state = AgentState.DONE
            yield self._emit_event("done", {
                "iterations": self.iteration_count,
            })
            self._flush_trace_buffer()
            return

        self.state = AgentState.DONE
        yield self._emit_event("done", {
            "iterations": self.iteration_count,
            "max_reached": True,
        })
        self._flush_trace_buffer()

    def add_context(self, content: str, label: str = "context") -> None:
        """Add additional context to the conversation.

        Useful for injecting file contents, search results, or other
        context into the conversation.
        """
        self.messages.append(Message(
            role=Role.SYSTEM,
            content=f"[{label}]\n{content}",
        ))

    def get_conversation_history(self) -> list[dict[str, Any]]:
        """Get the conversation history as serializable dicts."""
        return [msg.to_openai_format() for msg in self.messages]

    def clear_history(self) -> None:
        """Clear conversation history (keep system prompts and context)."""
        self.messages = [m for m in self.messages if m.role == Role.SYSTEM]
        self.iteration_count = 0
        self.state = AgentState.IDLE

    def compact_context(self, focus: str | None = None) -> dict[str, Any]:
        """Compact the conversation context by summarizing older messages.

        Args:
            focus: Optional area of focus to preserve in compaction.

        Returns:
            Dict with compaction stats.
        """
        if not self.messages or len(self.messages) < 4:
            return {"compacted": False, "reason": "too_few_messages"}
        before = len(self.messages)
        self.messages = self._ctx_mgr.compact(self.messages, focus=focus)
        after = len(self.messages)
        return {
            "compacted": before != after,
            "before": before,
            "after": after,
            "focus": focus,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get conversation statistics."""
        model_name = self.provider.model_name
        provider_name = self.provider.name
        token_est = self.provider.count_message_tokens(self.messages)
        return {
            "session_id": self.session_id,
            "mode": self.mode.value,
            "state": self.state.value,
            "message_count": len(self.messages),
            "iteration_count": self.iteration_count,
            "model": model_name,
            "provider": provider_name,
            "token_estimate": token_est,
        }
