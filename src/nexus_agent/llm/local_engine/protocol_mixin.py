from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from typing import Any

from nexus_agent.protocol.agent_protocol import (
    AgentOutputParser,
    AgentProtocol,
    AgentRole,
    OperationType,
    Task,
    TaskStatus,
    ToolCallStatus,
)

logger = logging.getLogger(__name__)


class ProtocolMixin:
    _protocol: AgentProtocol | None
    _use_agent_protocol: bool
    _agent_role: AgentRole
    _reasoning_depth: int
    _current_goal: str
    _tool_results: dict[str, Any]
    _model_name_str: str
    _llm: Any

    def enable_agent_protocol(
        self,
        goal: str,
        reasoning_depth: int = 8,
        agent_role: AgentRole = AgentRole.GENERAL,
        constraints: str = "",
        success_criteria: str = "",
        environment: str = "",
    ):
        self._use_agent_protocol = True
        self._agent_role = agent_role
        self._reasoning_depth = reasoning_depth
        self._current_goal = goal

        self._protocol = AgentProtocol(
            session_id=f"local_{uuid.uuid4().hex[:8]}",
            model_name=self._model_name_str,
        )

        if constraints:
            self._protocol.tasks.append(
                Task(type=OperationType.REASONING, description=f"Constraints: {constraints}")
            )

        logger.info(
            f"Agent protocol enabled: role={agent_role.value}, "
            f"reasoning_depth={reasoning_depth}, goal='{goal[:100]}...'"
        )

    def disable_agent_protocol(self):
        self._use_agent_protocol = False
        self._protocol = None
        logger.info("Agent protocol disabled")

    def add_task(
        self,
        task_type: OperationType,
        description: str,
        depends_on: list[str] | None = None,
    ) -> Task:
        if not self._protocol:
            self.enable_agent_protocol(f"Execute task: {description}")
        return self._protocol.add_task(task_type, description, depends_on)

    def set_tool_result(self, tool_call_id: str, result: Any, success: bool = True, error: str | None = None):
        self._tool_results[tool_call_id] = {"result": result, "success": success, "error": error}

    def get_xml_prompt(self) -> str:
        if not self._protocol:
            raise RuntimeError("Agent protocol not enabled. Call enable_agent_protocol() first.")

        serializer = self._protocol.create_input_serializer(
            goal=self._current_goal,
            agent_role=self._agent_role,
            reasoning_depth=self._reasoning_depth,
        )
        return serializer.to_prompt()

    def _run_protocol_completion(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        **kwargs,
    ) -> AgentOutputParser:
        if not self._protocol:
            raise RuntimeError("Protocol not enabled")

        start_time = time.time()

        try:
            output = self._llm.create_completion(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )
        except (ValueError, RuntimeError) as e:
            logger.error(f"Protocol completion error: {e}")
            raise RuntimeError(f"Model inference failed: {e}") from e

        raw_output = output.get("choices", [{}])[0].get("text", "")

        elapsed_ms = (time.time() - start_time) * 1000

        parser = self._protocol.parse_output(raw_output)

        for step in parser.get_thinking():
            self._protocol.event_logger.log(
                "thought_step",
                step=step.step,
                confidence=step.confidence,
                halted_early=step.halted_early,
                duration_ms=elapsed_ms,
            )

        self._protocol.event_logger.log(
            "completion_generated",
            tokens=output.get("usage", {}).get("completion_tokens", 0),
            duration_ms=elapsed_ms,
            status=parser.get_status(),
        )

        return parser

    def _execute_operations(
        self,
        parser: AgentOutputParser,
        execute_fn: Callable[[dict[str, Any]], Any],
    ) -> tuple[list[dict], list[dict]]:
        executed = []
        failed = []

        for file_op in parser.get_file_operations():
            op_desc = f"{file_op.operation_type}: {file_op.path}"
            try:
                result = execute_fn({
                    "type": "file_operation",
                    "operation": file_op.operation_type,
                    "path": file_op.path,
                    "content": file_op.content,
                    "old_content": file_op.old_content,
                    "new_content": file_op.new_content,
                    "reason": file_op.reason,
                })
                executed.append({"type": "file_operation", "operation": file_op.operation_type, "path": file_op.path, "result": result})
                if self._protocol:
                    self._protocol.log_file_operation(file_op, True)
            except (RuntimeError, ValueError, OSError, TypeError, AttributeError, KeyError, LookupError) as e:
                failed.append({"type": "file_operation", "operation": file_op.operation_type, "path": file_op.path, "error": str(e)})
                if self._protocol:
                    self._protocol.log_file_operation(file_op, False)
                    logger.error(f"File operation failed: {op_desc} — {e}")

        for cmd in parser.get_commands():
            cmd_desc = f"command: {cmd.command_string[:50]}"
            try:
                result = execute_fn({
                    "type": "command",
                    "command": cmd.command_string,
                    "working_dir": cmd.working_dir,
                    "reason": cmd.reason,
                    "timeout_seconds": cmd.timeout_seconds,
                })
                executed.append({"type": "command", "command": cmd.command_string, "result": result})
                if self._protocol:
                    self._protocol.event_logger.log("command_executed", command=cmd.command_string, success=True)
            except (RuntimeError, ValueError, OSError, TypeError, AttributeError, KeyError, LookupError) as e:
                failed.append({"type": "command", "command": cmd.command_string, "error": str(e)})
                if self._protocol:
                    self._protocol.event_logger.log("command_executed", command=cmd.command_string, success=False, error=str(e))
                    logger.error(f"Command failed: {cmd_desc} — {e}")

        tool_calls = parser.get_tool_calls()
        for tc in tool_calls:
            tc_call = tc.tool_name
            tc_id = tc.id
            tc_args = tc.args
            try:
                result = execute_fn({
                    "type": "tool_call",
                    "tool_name": tc_call,
                    "args": tc_args,
                })
                tc.status = ToolCallStatus.RETURNED
                tc.result = result
                if self._protocol:
                    self._protocol.log_tool_result(tc)
                executed.append({"type": "tool_call", "tool_name": tc_call, "result": result})
            except (RuntimeError, ValueError, OSError, TypeError, AttributeError, KeyError, LookupError) as e:
                tc.status = ToolCallStatus.FAILED
                tc.error = str(e)
                if self._protocol:
                    self._protocol.log_tool_result(tc)
                failed.append({"type": "tool_call", "tool_name": tc_call, "error": str(e)})
                logger.error(f"Tool call failed: {tc_call} — {e}")

        for delegation in parser.get_delegations():
            try:
                result = execute_fn({
                    "type": "delegation",
                    "to_agent": delegation.to_agent,
                    "task": delegation.task,
                    "constraints": delegation.constraints,
                })
                delegation.status = TaskStatus.DELEGATED
                delegation.result = result
                if self._protocol:
                    self._protocol.event_logger.log(
                        "delegation_sent",
                        to_agent=delegation.to_agent,
                        task=delegation.task,
                        success=True,
                    )
                executed.append({"type": "delegation", "to": delegation.to_agent, "result": result})
            except (RuntimeError, ValueError, OSError, TypeError, AttributeError, KeyError, LookupError) as e:
                if self._protocol:
                    self._protocol.event_logger.log(
                        "delegation_sent",
                        to_agent=delegation.to_agent,
                        task=delegation.task,
                        success=False,
                        error=str(e),
                    )
                failed.append({"type": "delegation", "to": delegation.to_agent, "error": str(e)})
                logger.error(f"Delegation failed: {delegation.to_agent} — {e}")

        return executed, failed

    def run_agent_loop(
        self,
        goal: str,
        execute_fn: Callable[[dict[str, Any]], Any],
        max_iterations: int = 20,
        temperature: float = 0.1,
        agent_role: AgentRole = AgentRole.GENERAL,
        reasoning_depth: int = 8,
        constraints: str = "",
        success_criteria: str = "",
        environment: str = "",
    ) -> dict[str, Any]:
        self.enable_agent_protocol(
            goal=goal,
            agent_role=agent_role,
            reasoning_depth=reasoning_depth,
            constraints=constraints,
            success_criteria=success_criteria,
            environment=environment,
        )

        self._current_goal = goal

        all_executed = []
        all_failed = []
        all_thinking = []
        iterations = 0

        while iterations < max_iterations:
            iterations += 1

            if self._protocol:
                self._protocol.event_logger.log("iteration_start", iteration=iterations)

            xml_prompt = self.get_xml_prompt()
            parser = self._run_protocol_completion(xml_prompt, temperature=temperature)

            thinking_steps = parser.get_thinking()
            all_thinking.extend(thinking_steps)

            plan = parser.get_plan()
            final_answer = parser.get_final_answer()
            status = parser.get_status()
            next_action = parser.get_next_action()

            executed, failed = self._execute_operations(parser, execute_fn)
            all_executed.extend(executed)
            all_failed.extend(failed)

            if self._protocol:
                self._protocol.event_logger.log(
                    "iteration_end",
                    iteration=iterations,
                    status=status,
                    next_action=next_action,
                    executed_count=len(executed),
                    failed_count=len(failed),
                )

            if status in ("success", "complete") or next_action == "stop":
                break

            if not parser.has_pending_operations() and not plan:
                break

        if self._protocol:
            self._protocol.log_session_end(
                duration_ms=0,
                tasks_completed=len(all_executed),
            )

        return {
            "final_answer": final_answer,
            "iterations": iterations,
            "executed_ops": all_executed,
            "failed_ops": all_failed,
            "thinking": [{"step": t.step, "observation": t.observation, "confidence": t.confidence} for t in all_thinking],
            "events": self._protocol.event_logger.to_jsonl() if self._protocol else "",
            "status": status if iterations < max_iterations else "max_iterations_reached",
        }
