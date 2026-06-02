"""
Unified Agent Protocol — XML input / JSON output schema for nexus-agent.

This module implements a hierarchical agent protocol where:
- INPUT  to LLM:  XML format for structured prompting
- OUTPUT from LLM: JSON format for machine parsing
- EVENTS: immutable execution log

Schema is designed for:
- RecurrentBlock-based models (Mythos) with iterative refinement
- Multi-agent coordination (architect/worker/reviewer)
- Code agents (file ops, commands, tool calls, tests)
- Both OpenAI function_call AND Anthropic tool_use formats
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from xml.etree import ElementTree as ET

# =============================================================================
# Enums
# =============================================================================

class AgentRole(Enum):
    ARCHITECT = "architect"
    WORKER = "worker"
    REVIEWER = "reviewer"
    QA = "qa"
    SECURITY = "security"
    COORDINATOR = "coordinator"
    GENERAL = "general"


class OperationType(Enum):
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_EDIT = "file_edit"
    COMMAND = "command"
    TOOL_CALL = "tool_call"
    WEB_SEARCH = "web_search"
    DELEGATION = "delegation"
    REASONING = "reasoning"
    REFLECTION = "reflection"
    FINAL_ANSWER = "final_answer"


class TaskStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    DELEGATED = "delegated"


class AgentState(Enum):
    IDLE = "idle"
    REASONING = "reasoning"
    PLANNING = "planning"
    EXECUTING = "executing"
    WAITING_TOOL = "waiting_tool"
    WAITING_DELEGATION = "waiting_delegation"
    EVALUATING = "evaluating"
    COMPLETE = "complete"
    ERROR = "error"


class ToolCallStatus(Enum):
    PENDING = "pending"
    CALLED = "called"
    RETURNED = "returned"
    FAILED = "failed"


# =============================================================================
# Tool Call Formats (supports both OpenAI and Anthropic)
# =============================================================================

@dataclass
class ToolParameter:
    name: str
    type: str
    description: str = ""
    required: bool = False
    default: Any = None
    enum: list[str] = field(default_factory=list)


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)

    def to_openai(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        p.name: {
                            "type": p.type,
                            "description": p.description,
                            "enum": p.enum if p.enum else None,
                        }
                        for p in self.parameters
                    },
                    "required": [p.name for p in self.parameters if p.required],
                },
            },
        }

    def to_anthropic(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    p.name: {
                        "type": p.type,
                        "description": p.description,
                    }
                    for p in self.parameters
                },
                "required": [p.name for p in self.parameters if p.required],
            },
        }


@dataclass
class ToolCall:
    id: str = field(default_factory=lambda: f"call_{uuid.uuid4().hex[:8]}")
    tool_name: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    status: ToolCallStatus = ToolCallStatus.PENDING
    result: Any | None = None
    error: str | None = None
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_openai(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.tool_name,
                "arguments": json.dumps(self.args),
            },
        }

    def to_anthropic(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.tool_name,
            "input": self.args,
        }

    @classmethod
    def from_openai(cls, data: dict) -> ToolCall:
        args = json.loads(data.get("function", {}).get("arguments", "{}"))
        return cls(
            id=data.get("id", f"call_{uuid.uuid4().hex[:8]}"),
            tool_name=data.get("function", {}).get("name", ""),
            args=args,
        )

    @classmethod
    def from_anthropic(cls, data: dict) -> ToolCall:
        return cls(
            id=data.get("id", f"call_{uuid.uuid4().hex[:8]}"),
            tool_name=data.get("name", ""),
            args=data.get("input", {}),
        )


# =============================================================================
# Core Data Classes
# =============================================================================

@dataclass
class MemoryEntry:
    key: str
    value: str
    access_count: int = 0
    created_at: float = field(default_factory=time.time)
    ttl: int = 3600


@dataclass
class Task:
    id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    type: OperationType = OperationType.REASONING
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    depends_on: list[str] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class FileOperation:
    path: str
    content: str | None = None
    old_content: str | None = None
    new_content: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    reason: str = ""
    operation_type: str = "read"  # read, write, edit, delete
    status: TaskStatus = TaskStatus.PENDING


@dataclass
class Command:
    command_string: str
    working_dir: str = ""
    reason: str = ""
    timeout_seconds: int = 60
    status: TaskStatus = TaskStatus.PENDING
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""


@dataclass
class Delegation:
    to_agent: str
    task: str
    task_id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    constraints: str = ""
    status: TaskStatus = TaskStatus.PENDING
    result: dict[str, Any] | None = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentInfo:
    id: str
    role: AgentRole
    capabilities: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    name: str = ""


@dataclass
class ReasoningStep:
    step: int
    observation: str = ""
    hypothesis: str = ""
    reasoning: str = ""
    confidence: float = 0.0
    halted_early: bool = False
    refinement: str = ""


# =============================================================================
# Execution Event Log
# =============================================================================

class EventLogger:
    """Immutable execution event log."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.events: list[dict[str, Any]] = []

    def log(self, event_type: str, **data):
        self.events.append({
            "event": event_type,
            "session_id": self.session_id,
            "timestamp": time.time(),
            **data,
        })

    def to_jsonl(self) -> str:
        return "\n".join(json.dumps(e) for e in self.events)

    def save(self, path: str):
        with open(path, "w") as f:
            f.write(self.to_jsonl())

    def get_events(self, event_type: str | None = None) -> list[dict[str, Any]]:
        if event_type is None:
            return list(self.events)
        return [e for e in self.events if e["event"] == event_type]


# =============================================================================
# Agent Protocol — XML Input Serializer
# =============================================================================

class AgentInputSerializer:
    """
    Serializes agent state to XML format for LLM prompts.
    Designed to work well with recurrent/block-iterative models.
    """

    DEFAULT_TOOLS = [
        ToolDefinition(
            name="file_read",
            description="Read contents of a file",
            parameters=[
                ToolParameter(name="path", type="string", description="Absolute path to file", required=True),
                ToolParameter(name="line_start", type="integer", description="Start line (optional)"),
                ToolParameter(name="line_end", type="integer", description="End line (optional)"),
            ],
        ),
        ToolDefinition(
            name="file_write",
            description="Write content to a file (creates or overwrites)",
            parameters=[
                ToolParameter(name="path", type="string", description="Absolute path to file", required=True),
                ToolParameter(name="content", type="string", description="Full file content to write", required=True),
            ],
        ),
        ToolDefinition(
            name="file_edit",
            description="Edit specific content in a file using old/new content matching",
            parameters=[
                ToolParameter(name="path", type="string", description="Absolute path to file", required=True),
                ToolParameter(name="old_content", type="string", description="Exact content to replace", required=True),
                ToolParameter(name="new_content", type="string", description="Replacement content", required=True),
            ],
        ),
        ToolDefinition(
            name="command",
            description="Execute a shell command",
            parameters=[
                ToolParameter(name="command_string", type="string", description="Command to execute", required=True),
                ToolParameter(name="working_dir", type="string", description="Working directory"),
                ToolParameter(name="timeout_seconds", type="integer", description="Timeout in seconds", default=60),
            ],
        ),
        ToolDefinition(
            name="web_search",
            description="Search the web for information",
            parameters=[
                ToolParameter(name="query", type="string", description="Search query", required=True),
                ToolParameter(name="num_results", type="integer", description="Number of results", default=5),
            ],
        ),
    ]

    def __init__(
        self,
        session_id: str,
        goal: str,
        agent_info: AgentInfo,
        tasks: list[Task],
        memory: dict[str, Any],
        conversation_history: list[dict[str, str]],
        tools: list[ToolDefinition] | None = None,
        constraints: str = "",
        success_criteria: str = "",
        environment: str = "",
        reasoning_depth: int = 8,
        thinking_enabled: bool = True,
        self_critique_enabled: bool = True,
        multi_agent_roster: list[AgentInfo] | None = None,
        pending_delegations: list[Delegation] | None = None,
    ):
        self.session_id = session_id
        self.goal = goal
        self.agent_info = agent_info
        self.tasks = tasks
        self.memory = memory
        self.conversation_history = conversation_history
        self.tools = tools or self.DEFAULT_TOOLS
        self.constraints = constraints
        self.success_criteria = success_criteria
        self.environment = environment
        self.reasoning_depth = reasoning_depth
        self.thinking_enabled = thinking_enabled
        self.self_critique_enabled = self_critique_enabled
        self.multi_agent_roster = multi_agent_roster or []
        self.pending_delegations = pending_delegations or []

    def to_xml(self) -> str:
        root = ET.Element("agent_input")

        ET.SubElement(root, "session_id").text = self.session_id

        identity = ET.SubElement(root, "agent_identity")
        ET.SubElement(identity, "name").text = self.agent_info.name or self.agent_info.id
        ET.SubElement(identity, "role").text = self.agent_info.role.value
        ET.SubElement(identity, "capabilities").text = ", ".join(self.agent_info.capabilities) if self.agent_info.capabilities else "general-purpose"
        ET.SubElement(identity, "limitations").text = ", ".join(self.agent_info.limitations) if self.agent_info.limitations else "none"

        ET.SubElement(root, "goal").text = self.goal

        if self.success_criteria:
            ET.SubElement(root, "success_criteria").text = self.success_criteria

        if self.constraints:
            ET.SubElement(root, "constraints").text = self.constraints

        if self.environment:
            ET.SubElement(root, "environment").text = self.environment

        context_el = ET.SubElement(root, "context")
        context_el.text = f"Working on task: {self.goal}"

        if self.memory:
            mem_el = ET.SubElement(root, "memory")
            if self.memory.get("working"):
                ET.SubElement(mem_el, "working_memory").text = str(self.memory.get("working", ""))
            if self.memory.get("long_term"):
                ET.SubElement(mem_el, "long_term_memory").text = str(self.memory.get("long_term", ""))

        reasoning_el = ET.SubElement(root, "reasoning_config")
        ET.SubElement(reasoning_el, "thinking_enabled").text = str(self.thinking_enabled).lower()
        ET.SubElement(reasoning_el, "thinking_depth").text = str(self.reasoning_depth)
        ET.SubElement(reasoning_el, "self_critique_enabled").text = str(self.self_critique_enabled).lower()

        if self.multi_agent_roster:
            roster_el = ET.SubElement(root, "agent_roster")
            for agent in self.multi_agent_roster:
                agent_el = ET.SubElement(roster_el, "agent", id=agent.id)
                ET.SubElement(agent_el, "role").text = agent.role.value
                ET.SubElement(agent_el, "capabilities").text = ", ".join(agent.capabilities) if agent.capabilities else "general-purpose"

        if self.pending_delegations:
            for d in self.pending_delegations:
                delegation_el = ET.SubElement(root, "delegation")
                ET.SubElement(delegation_el, "from").text = self.agent_info.id
                ET.SubElement(delegation_el, "to").text = d.to_agent
                ET.SubElement(delegation_el, "task").text = d.task
                if d.constraints:
                    ET.SubElement(delegation_el, "constraints").text = d.constraints

        task_queue_el = ET.SubElement(root, "task_queue")

        current_tasks = [t for t in self.tasks if t.status == TaskStatus.ACTIVE]
        pending_tasks = [t for t in self.tasks if t.status == TaskStatus.PENDING]
        completed_tasks = [t for t in self.tasks if t.status == TaskStatus.COMPLETED]

        if current_tasks:
            current_el = ET.SubElement(task_queue_el, "current_task")
            t = current_tasks[0]
            ET.SubElement(current_el, "id").text = t.id
            ET.SubElement(current_el, "type").text = t.type.value
            ET.SubElement(current_el, "description").text = t.description
            ET.SubElement(current_el, "attempts").text = str(t.attempts)

        if pending_tasks:
            ET.SubElement(task_queue_el, "pending_tasks").text = "\n".join(
                f"- [{t.id}] {t.type.value}: {t.description}" for t in pending_tasks
            )

        if completed_tasks:
            ET.SubElement(task_queue_el, "completed_tasks").text = "\n".join(
                f"- [{t.id}] {t.type.value}: {t.description}" for t in completed_tasks
            )

        tools_el = ET.SubElement(root, "tool_definitions")
        for tool in self.tools:
            tool_el = ET.SubElement(tools_el, "tool")
            ET.SubElement(tool_el, "name").text = tool.name
            ET.SubElement(tool_el, "description").text = tool.description
            if tool.parameters:
                params_el = ET.SubElement(tool_el, "parameters")
                for p in tool.parameters:
                    p_el = ET.SubElement(params_el, "parameter", name=p.name, type=p.type)
                    p_el.text = p.description
                    if p.required:
                        p_el.set("required", "true")

        if self.conversation_history:
            history_el = ET.SubElement(root, "conversation_history")
            for msg in self.conversation_history[-10:]:
                msg_el = ET.SubElement(history_el, "message", role=msg.get("role", "user"))
                msg_el.text = msg.get("content", "")

        output_el = ET.SubElement(root, "output_schema")
        output_el.text = (
            "Respond with valid JSON containing: "
            "thinking[], plan[], operations[], tool_calls[], "
            "final_answer, status, next_action. "
            "Use only the defined tools. "
            "For file operations, use: type, path, content/old_content/new_content, reason. "
            "For commands, use: type, command_string, working_dir, reason, timeout_seconds."
        )

        return ET.tostring(root, encoding="unicode", method="xml")

    def to_prompt(self) -> str:
        return self.to_xml()


# =============================================================================
# Agent Protocol — JSON Output Parser
# =============================================================================

class AgentOutputParser:
    """
    Parses JSON output from LLM into structured agent operations.
    Validates against schema and provides fallback parsing.
    """

    def __init__(self, raw_output: str):
        self.raw_output = raw_output
        self.data: dict[str, Any] = {}
        self.parse_errors: list[str] = []
        self._parse()

    def _parse(self):
        try:
            self.data = json.loads(self.raw_output)
        except json.JSONDecodeError as e:
            self.parse_errors.append(f"JSON parse error: {e}")
            self.data = self._fallback_parse()

    def _fallback_parse(self) -> dict[str, Any]:
        """Try to extract JSON from mixed output (e.g., with thinking text before/after)."""
        text = self.raw_output.strip()

        patterns = [
            r'\{[^{}]*"thinking"[^{}]*\}',
            r'\{[^{}]*"operations"[^{}]*\}',
            r'\{[^{}]*"tool_calls"[^{}]*\}',
            r'\{"[^"]+"\s*:\s*[^}]+\}',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue

        return {"error": f"Could not parse output: {text[:500]}"}

    def get_thinking(self) -> list[ReasoningStep]:
        """Extract thinking/reasoning steps."""
        thinking = self.data.get("thinking", [])
        if isinstance(thinking, list):
            return [ReasoningStep(
                step=i + 1,
                observation=t.get("observation", ""),
                hypothesis=t.get("hypothesis", ""),
                reasoning=t.get("reasoning", t.get("thought", "")),
                confidence=t.get("confidence", 0.5),
                halted_early=t.get("halted_early", False),
            ) for i, t in enumerate(thinking)]
        return []

    def get_reasoning(self) -> str:
        return self.data.get("reasoning", {}).get("final", "")

    def get_plan(self) -> list[str]:
        plan = self.data.get("plan", [])
        if isinstance(plan, list):
            return [str(p) for p in plan]
        return []

    def get_reflection(self) -> dict[str, str]:
        ref = self.data.get("reflection", {})
        return {
            "strengths": ref.get("strengths", []),
            "weaknesses": ref.get("weaknesses", []),
            "improvements": ref.get("improvements", []),
        }

    def get_active_task(self) -> Task | None:
        task_data = self.data.get("active_task", {})
        if not task_data:
            return None
        return Task(
            id=task_data.get("id", f"task_{uuid.uuid4().hex[:8]}"),
            type=OperationType(task_data.get("type", "reasoning")),
            status=TaskStatus(task_data.get("status", "pending")),
        )

    def get_file_operations(self) -> list[FileOperation]:
        """Extract file operations from output."""
        ops = self.data.get("operations", [])
        file_ops = []
        for op in ops:
            op_type = op.get("type", "")
            if op_type not in ("file_read", "file_write", "file_edit"):
                continue
            file_ops.append(FileOperation(
                path=op.get("path", ""),
                content=op.get("content"),
                old_content=op.get("old_content"),
                new_content=op.get("new_content"),
                line_start=op.get("line_start"),
                line_end=op.get("line_end"),
                reason=op.get("reason", ""),
                operation_type=op_type.replace("file_", ""),
                status=TaskStatus(op.get("status", "pending")),
            ))
        return file_ops

    def get_commands(self) -> list[Command]:
        """Extract command operations from output."""
        ops = self.data.get("operations", [])
        cmds = []
        for op in ops:
            if op.get("type") != "command":
                continue
            cmds.append(Command(
                command_string=op.get("command_string", op.get("command", "")),
                working_dir=op.get("working_dir", ""),
                reason=op.get("reason", ""),
                timeout_seconds=op.get("timeout_seconds", 60),
                status=TaskStatus(op.get("status", "pending")),
            ))
        return cmds

    def get_tool_calls(self) -> list[ToolCall]:
        """Extract tool calls from output (supports both OpenAI and Anthropic formats)."""
        calls = []
        raw_calls = self.data.get("tool_calls", [])

        for call in raw_calls:
            if isinstance(call, dict):
                if "function" in call:
                    calls.append(ToolCall.from_openai(call))
                elif "name" in call:
                    calls.append(ToolCall.from_anthropic(call))
                else:
                    calls.append(ToolCall(
                        id=call.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                        tool_name=call.get("tool_name", call.get("name", "")),
                        args=call.get("args", call.get("arguments", {})),
                        status=ToolCallStatus(call.get("status", "pending")),
                    ))
        return calls

    def get_delegations(self) -> list[Delegation]:
        """Extract delegation requests from output."""
        ma = self.data.get("multi_agent", {})
        delegated = ma.get("delegated_to", [])
        delegations = []
        for d in delegated:
            if isinstance(d, dict):
                delegations.append(Delegation(
                    to_agent=d.get("to", ""),
                    task=d.get("task", ""),
                    task_id=d.get("task_id", f"task_{uuid.uuid4().hex[:8]}"),
                    constraints=d.get("constraints", ""),
                    status=TaskStatus.DELEGATED,
                ))
        return delegations

    def get_final_answer(self) -> str:
        return self.data.get("final_answer", "")

    def get_status(self) -> str:
        return self.data.get("status", "unknown")

    def get_next_action(self) -> str:
        return self.data.get("next_action", "stop")

    def is_complete(self) -> bool:
        return self.get_status() in ("success", "complete", "error")

    def has_pending_operations(self) -> bool:
        ops = self.data.get("operations", [])
        return any(
            op.get("status") in ("pending", None)
            for op in ops
        )

    def get_next_pending_operation(self) -> dict[str, Any] | None:
        for op in self.data.get("operations", []):
            if op.get("status") in ("pending", None):
                return op
        return None


# =============================================================================
# Protocol — Main Entry Point
# =============================================================================

class AgentProtocol:
    """
    Main protocol handler coordinating input serialization and output parsing.
    """

    def __init__(
        self,
        session_id: str | None = None,
        model_name: str = "mythos",
        tools: list[ToolDefinition] | None = None,
    ):
        self.session_id = session_id or f"session_{uuid.uuid4().hex[:8]}"
        self.model_name = model_name
        self.default_tools = tools or AgentInputSerializer.DEFAULT_TOOLS
        self.event_logger = EventLogger(self.session_id)
        self.state = AgentState.IDLE
        self.tasks: list[Task] = []
        self.tool_calls: list[ToolCall] = []
        self.memory: dict[str, Any] = {"working": {}, "long_term": {}}
        self.conversation_history: list[dict[str, str]] = []

        self.event_logger.log("session_start", model=model_name)

    def create_input_serializer(
        self,
        goal: str,
        agent_role: AgentRole = AgentRole.GENERAL,
        agent_name: str = "",
        agent_capabilities: list[str] | None = None,
        constraints: str = "",
        success_criteria: str = "",
        environment: str = "",
        reasoning_depth: int = 8,
        thinking_enabled: bool = True,
        multi_agent_roster: list[AgentInfo] | None = None,
        pending_delegations: list[Delegation] | None = None,
    ) -> AgentInputSerializer:
        agent_info = AgentInfo(
            id=self.session_id,
            role=agent_role,
            capabilities=agent_capabilities or ["code_generation", "file_operations", "testing", "reasoning"],
            name=agent_name or agent_role.value,
        )

        return AgentInputSerializer(
            session_id=self.session_id,
            goal=goal,
            agent_info=agent_info,
            tasks=self.tasks,
            memory=self.memory,
            conversation_history=self.conversation_history,
            tools=self.default_tools,
            constraints=constraints,
            success_criteria=success_criteria,
            environment=environment,
            reasoning_depth=reasoning_depth,
            thinking_enabled=thinking_enabled,
            multi_agent_roster=multi_agent_roster,
            pending_delegations=pending_delegations,
        )

    def parse_output(self, raw_output: str) -> AgentOutputParser:
        parser = AgentOutputParser(raw_output)

        for step in parser.get_thinking():
            self.event_logger.log("thought_step", step=step.step, confidence=step.confidence, halted_early=step.halted_early)

        for op in parser.get_file_operations():
            self.event_logger.log("operation_pending", type=op.operation_type, path=op.path, status=op.status.value)

        for cmd in parser.get_commands():
            self.event_logger.log("operation_pending", type="command", command=cmd.command_string, status=cmd.status.value)

        for tc in parser.get_tool_calls():
            self.event_logger.log("tool_call_pending", tool_name=tc.tool_name, call_id=tc.id)

        next_action = parser.get_next_action()
        self.event_logger.log("output_received", next_action=next_action, status=parser.get_status())

        return parser

    def log_tool_result(self, tool_call: ToolCall):
        self.event_logger.log(
            "tool_call_end",
            tool_name=tool_call.tool_name,
            call_id=tool_call.id,
            success=tool_call.status == ToolCallStatus.RETURNED,
            duration_ms=tool_call.duration_ms,
            error=tool_call.error,
        )

    def log_file_operation(self, op: FileOperation, success: bool, duration_ms: float = 0.0):
        self.event_logger.log(
            "file_operation_end",
            operation=op.operation_type,
            path=op.path,
            success=success,
            duration_ms=duration_ms,
        )

    def log_task_complete(self, task_id: str, success: bool):
        self.event_logger.log("task_complete", task_id=task_id, success=success)

    def log_session_end(self, duration_ms: float, tasks_completed: int):
        self.event_logger.log(
            "session_end",
            duration_ms=duration_ms,
            tasks_completed=tasks_completed,
            status="success" if tasks_completed > 0 else "no_tasks",
        )

    def add_task(self, task_type: OperationType, description: str, depends_on: list[str] | None = None) -> Task:
        task = Task(
            type=task_type,
            description=description,
            depends_on=depends_on or [],
        )
        self.tasks.append(task)
        self.event_logger.log("task_added", task_id=task.id, type=task_type.value, description=description)
        return task

    def update_task_status(self, task_id: str, status: TaskStatus, result: dict | None = None):
        for task in self.tasks:
            if task.id == task_id:
                task.status = status
                task.result = result
                break
        self.event_logger.log("task_status_updated", task_id=task_id, status=status.value)

    def format_conversation_message(self, role: str, content: str):
        self.conversation_history.append({"role": role, "content": content})


def create_agent_protocol(
    goal: str,
    agent_role: AgentRole = AgentRole.GENERAL,
    model_name: str = "mythos",
    reasoning_depth: int = 8,
    tools: list[ToolDefinition] | None = None,
) -> tuple[AgentProtocol, AgentInputSerializer, str]:
    """
    Factory function to create protocol, serializer, and XML prompt.
    Returns: (protocol, serializer, xml_prompt)
    """
    protocol = AgentProtocol(model_name=model_name, tools=tools)
    serializer = protocol.create_input_serializer(
        goal=goal,
        agent_role=agent_role,
        reasoning_depth=reasoning_depth,
    )
    return protocol, serializer, serializer.to_prompt()
