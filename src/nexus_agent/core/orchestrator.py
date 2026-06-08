"""Multi-Agent Orchestrator — Coordinates specialized sub-agents.

Implements the **Boomerang Tasks** pattern (inspired by Roo Code):
- Decompose high-level goals into sub-tasks
- Delegate sub-tasks to isolated AgentLoop instances ("throw")
- Collect results back into the orchestrator ("boomerang return")
- Integrate sub-results into the final output

Also orchestrates sequential planning, user approvals, execution, and
verification using Planner and Executor sub-agents.
"""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nexus_agent.core.agent import AgentEvent, AgentLoop, AgentLoopConfig, AgentMode, AgentState
from nexus_agent.core.debate import DebateEngine
from nexus_agent.core.devops import VerificationPipeline
from nexus_agent.core.executor import Executor
from nexus_agent.core.planner import Planner
from nexus_agent.core.task_graph import TaskGraph
from nexus_agent.llm.base import LLMProvider

logger = logging.getLogger(__name__)


# ── Boomerang Task Types ────────────────────────────────────────────


@dataclass
class BoomerangSubTask:
    """A single sub-task that can be delegated to a sub-agent.

    The "boomerang" metaphor:
    1. **Launch:** The orchestrator defines a focused sub-goal and "throws" it
       to an isolated AgentLoop with a subset of tools.
    2. **Return:** The sub-agent executes and sends back a structured result.
    3. **Integrate:** The orchestrator collects results and integrates them.
    """
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    description: str = ""
    context: str = ""
    status: str = "pending"  # pending | running | completed | failed
    result: str = ""
    error: str | None = None
    tool_names: list[str] | None = None  # Subset of tools to expose (None = all)
    effort_level: str = "low"
    max_iterations: int = 15


@dataclass
class BoomerangResult:
    """Aggregated result of a boomerang task execution."""
    success: bool = True
    subtask_results: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    total_iterations: int = 0


class Orchestrator:
    """Multi-Agent Orchestrator with Boomerang Task delegation.

    Coordinates specialized sub-agents:
    1. Spawn Planner to generate a technical plan (read-only).
    2. Prompt for user feedback or approval (gated).
    3. Spawn Executor to write code, test, and verify.
    4. **Boomerang Tasks**: Decompose complex goals into sub-tasks,
       delegate each to an isolated AgentLoop, and collect results.
    """

    def __init__(
        self,
        provider: LLMProvider,
        tools: list[Any],
        approval_callback: Callable[[str], bool] | None = None,
        workspace: Path | None = None,
        **agent_kwargs: Any,
    ):
        """Initialize the Orchestrator.

        Args:
            provider: The active LLM provider.
            tools: All registered workspace tools.
            approval_callback: Callback function to ask the user for approval of the plan.
                               Receives the plan markdown and returns True if approved.
            workspace: The workspace root folder.
            agent_kwargs: Common parameters to forward to sub-agents.
        """
        self.provider = provider
        self.tools = tools
        self.approval_callback = approval_callback
        self.workspace = workspace or Path.cwd()
        self.agent_kwargs = agent_kwargs

        self.planner = Planner(provider, tools, workspace=self.workspace, **agent_kwargs)
        self.executor = Executor(provider, tools, workspace=self.workspace, **agent_kwargs)

    # ── Boomerang Task Public API ──────────────────────────────────

    def delegate_subtask(
        self,
        subtask: BoomerangSubTask,
        tools: list[Any] | None = None,
    ) -> Iterator[AgentEvent]:
        """Delegate a single sub-task to an isolated AgentLoop.

        The sub-agent runs with its own conversation context, a focused
        system prompt, and an optional subset of tools. When it finishes,
        the result is captured and "boomerangs" back to the orchestrator.

        Args:
            subtask: The sub-task definition (description, context, tool subset).
            tools: Optional tool override. If None, uses the orchestrator's tools.

        Yields:
            AgentEvent stream of the delegated execution.
        """
        # Select a focused subset of tools for this sub-task
        sub_tools = tools or self.tools
        if subtask.tool_names is not None:
            sub_tools = [t for t in sub_tools if t.name in subtask.tool_names]

        # Build a focused system prompt for the sub-agent
        system_prompt = (
            f"You are a focused sub-agent working on a specific task.\n"
            f"## Objective\n{subtask.description}\n\n"
            f"## Context\n{subtask.context}\n\n"
            f"## Rules\n"
            f"1. Focus exclusively on this objective. Do not go out of scope.\n"
            f"2. When you have completed the task, clearly state 'TASK COMPLETE' "
            f"and provide a summary of what was done.\n"
            f"3. If you encounter an error you cannot resolve, state 'TASK FAILED' "
            f"and explain the error.\n"
        )

        # Create an isolated AgentLoop for this sub-task
        cfg = AgentLoopConfig(
            mode=AgentMode.BUILD,
            max_iterations=subtask.max_iterations,
            system_prompt_extra=system_prompt,
            workspace=self.workspace,
        )
        sub_agent = AgentLoop(
            provider=self.provider,
            tools=sub_tools,
            config=cfg,
        )

        subtask.status = "running"
        yield AgentEvent(
            type="state_change",
            data=f"delegating_subtask:{subtask.id}",
        )
        yield AgentEvent(
            type="content",
            data=f"[magenta]  Boomerang → Sub-task: {subtask.description[:80]}...[/magenta]\n",
        )

        collected_output = ""
        first_chunk = True
        try:
            for event in sub_agent.run_stream(subtask.description):
                # Capture the agent's output for the result
                if event.type.value == "content_chunk":
                    collected_output += event.data
                elif event.type.value == "content_complete":
                    collected_output = event.data
                elif event.type.value == "error":
                    subtask.status = "failed"
                    subtask.error = str(event.data)
                yield event
                first_chunk = False

            # Check if the sub-agent signaled completion or failure
            if subtask.status != "failed":
                if "TASK FAILED" in collected_output.upper():
                    subtask.status = "failed"
                    subtask.error = "Sub-agent reported failure: " + collected_output[-500:]
                elif "TASK COMPLETE" in collected_output.upper():
                    subtask.status = "completed"
                else:
                    # Assume success if no failure signal
                    subtask.status = "completed"

            subtask.result = collected_output
        except (RuntimeError, ValueError, OSError) as e:
            subtask.status = "failed"
            subtask.error = str(e)
            yield AgentEvent(type="error", data=f"Sub-task {subtask.id} failed: {e}")

        # Boomerang result back
        status_icon = "✅" if subtask.status == "completed" else "❌"
        yield AgentEvent(
            type="content",
            data=f"[cyan]  ← Boomerang returned ({status_icon} {subtask.status})\n"
            f"     Sub-task: {subtask.description[:100]}[/cyan]\n",
        )

    def run_boomerang(self, goal: str) -> Iterator[AgentEvent]:
        """Decompose a complex goal into sub-tasks using the planner,
        then delegate each sub-task via ``delegate_subtask`` and collect results.

        This implements the full Boomerang pattern:
        1. The orchestrator plans the decomposition
        2. Each sub-task is "thrown" to an isolated AgentLoop
        3. Results "boomerang" back with structured output
        4. The orchestrator integrates results into a final summary

        Args:
            goal: The high-level goal to decompose and execute.

        Yields:
            AgentEvent stream.
        """
        yield AgentEvent(type="state_change", data="planning")
        yield AgentEvent(
            type="content",
            data="[bold magenta]◆ Boomerang: Decomposing goal into sub-tasks...[/bold magenta]\n",
        )

        # 1. Use the planner to decompose the goal
        decomposition_prompt = (
            f"Analyze the following goal and break it into 3-8 independent, "
            f"focused sub-tasks that can be executed in parallel or sequence.\n\n"
            f"Goal: {goal}\n\n"
            f"For each sub-task, provide:\n"
            f"1. A one-line description\n"
            f"2. The specific context needed\n"
            f"3. Which tool categories are needed (read/write/shell/search)\n\n"
            f"Format as a numbered list. Each sub-task must be self-contained."
        )

        plan = ""
        for event in self.planner.plan(decomposition_prompt):
            yield event
            if event.type.value == "content_chunk":
                plan += event.data
            elif event.type.value == "content_complete":
                plan = event.data

        if not plan:
            yield AgentEvent(type="error", data="Failed to decompose goal into sub-tasks.")
            return

        # 2. Parse sub-tasks from the plan (numbered list format)
        subtasks = self._parse_subtasks(plan)
        if not subtasks:
            # Fall back: execute the goal as a single sub-task
            subtasks = [BoomerangSubTask(description=goal, context=plan)]

        yield AgentEvent(
            type="content",
            data=f"[green]  Decomposed into {len(subtasks)} sub-tasks[/green]\n",
        )

        # 3. Execute each sub-task (sequential order for consistency)
        results: list[dict[str, Any]] = []
        total_iterations = 0
        all_success = True

        for i, subtask in enumerate(subtasks):
            yield AgentEvent(
                type="content",
                data=f"\n[bold]--- Sub-task {i + 1}/{len(subtasks)} ---[/bold]\n",
            )

            # Collect events from the delegated sub-task
            for event in self.delegate_subtask(subtask):
                yield event
                if event.type.value == "content_chunk":
                    pass  # Already captured in delegate_subtask

            results.append({
                "id": subtask.id,
                "description": subtask.description,
                "status": subtask.status,
                "result": subtask.result,
                "error": subtask.error,
            })

            if subtask.status != "completed":
                all_success = False

            # Estimate iteration count from result length
            total_iterations += max(1, len(subtask.result) // 500)

        # 4. Aggregate summary
        completed = sum(1 for r in results if r["status"] == "completed")
        failed = sum(1 for r in results if r["status"] == "failed")

        yield AgentEvent(
            type="content",
            data=(
                f"\n[bold]🎯 Boomerang Complete:[/bold] {completed}/{len(subtasks)} sub-tasks succeeded"
                + (f", {failed} failed" if failed else "")
                + "\n"
            ),
        )

        boomerang_result = BoomerangResult(
            success=all_success,
            subtask_results=results,
            summary=f"Executed {len(subtasks)} sub-tasks: {completed} completed, {failed} failed.",
            total_iterations=total_iterations,
        )

        yield AgentEvent(type="state_change", data=AgentState.DONE)
        yield AgentEvent(type="done", data={
            "type": "boomerang",
            "success": boomerang_result.success,
            "summary": boomerang_result.summary,
            "subtasks": results,
        })

    def _parse_subtasks(self, plan: str) -> list[BoomerangSubTask]:
        """Parse numbered sub-tasks from a planner's markdown output.

        Looks for patterns like:
        1. Description of the task
           Context: additional context here
           Tools: read
        """
        import re

        subtasks: list[BoomerangSubTask] = []
        lines = plan.split("\n")

        current_desc = []
        current_context = []

        for line in lines:
            # Match numbered list items like "1. ..." or "1) ..."
            numbered_match = re.match(r"^\s*\d+[\.\)]\s+(.+)", line)
            if numbered_match:
                # Save previous sub-task if we have one
                if current_desc:
                    desc = " ".join(current_desc).strip()
                    if desc:
                        subtasks.append(BoomerangSubTask(
                            description=desc,
                            context="\n".join(current_context).strip(),
                        ))
                current_desc = [numbered_match.group(1)]
                current_context = []
            elif line.strip().lower().startswith("context:") or line.strip().lower().startswith("tools:"):
                current_context.append(line.strip())
            elif current_desc:
                # Continuation of current sub-task description
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and not stripped.startswith("```"):
                    current_desc.append(stripped)

        # Don't forget the last sub-task
        if current_desc:
            desc = " ".join(current_desc).strip()
            if desc:
                subtasks.append(BoomerangSubTask(
                    description=desc,
                    context="\n".join(current_context).strip(),
                ))

        return subtasks

    # ── Original Methods ───────────────────────────────────────────

    def run_task(self, task: str, plan_only: bool = False) -> Iterator[AgentEvent]:
        """Orchestrate a high-level task.

        Args:
            task: The user request.
            plan_only: If True, stops after generating the plan and does not execute it.

        Yields:
            AgentEvent stream of the orchestration progress.
        """
        yield AgentEvent(type="state_change", data="planning")
        yield AgentEvent(type="content", data="[bold magenta]◆ Orchestrator spawned Planner Sub-Agent...[/bold magenta]\n")

        # 1. Spawn Planner
        plan_content = ""
        for event in self.planner.plan(task):
            yield event
            if event.type == "content_chunk":
                plan_content += event.data
            elif event.type == "content_complete":
                plan_content = event.data

        if not plan_content:
            yield AgentEvent(type="error", data="Planner failed to generate an implementation plan.")
            return

        yield AgentEvent(type="content", data="\n[bold green]✅ Technical Implementation Plan Generated![/bold green]\n")

        if plan_only:
            yield AgentEvent(type="done", data={"plan": plan_content, "executed": False})
            return

        # 2. Gate with Plan Approval
        approved = True
        if self.approval_callback:
            yield AgentEvent(type="state_change", data=AgentState.WAITING_APPROVAL)
            yield AgentEvent(type="content", data="[yellow]⌛ Waiting for plan approval...[/yellow]\n")
            approved = self.approval_callback(plan_content)

        if not approved:
            yield AgentEvent(type="content", data="[red]❌ Implementation plan was rejected by the user. Aborting task.[/red]\n")
            yield AgentEvent(type="done", data={"plan": plan_content, "executed": False, "approved": False})
            return

        yield AgentEvent(type="content", data="\n[bold magenta]◆ Orchestrator approved! Spawning Executor Sub-Agent...[/bold magenta]\n")
        yield AgentEvent(type="state_change", data="executing")

        # 3. Spawn Executor to perform edits and verify
        for event in self.executor.execute_plan(task, plan_content):
            yield event

        yield AgentEvent(type="content", data="\n[bold green]🎉 Task successfully completed by Executor Sub-Agent![/bold green]\n")
        yield AgentEvent(type="state_change", data=AgentState.DONE)

    def run_autonomous(self, goal: str) -> Iterator[AgentEvent]:
        """Runs the fully autonomous Devin-style goal execution cycle using advanced controls.

        Workflow:
        1. Decompose high-level goal into hierarchical TaskGraph DAG.
        2. Sequence and run ready subtasks.
        3. Trigger VerificationPipeline (static scanning, dependency audits, local test suite).
        4. Trigger DebateEngine consensus review pass.
        5. Log iteration telemetry through NLATelemetry.
        """
        session_id = uuid.uuid4().hex[:12]
        yield AgentEvent(type="state_change", data="planning")
        yield AgentEvent(type="content", data=f"[bold magenta]◆ Initializing Autonomous Goal Graph (Session: {session_id})...[/bold magenta]\n")

        # 1. Initialize and Decompose goal
        task_graph = TaskGraph(session_id=session_id, workspace=self.workspace, provider=self.provider)
        yield AgentEvent(type="content", data="[cyan]Decomposing objective recursively...[/cyan]\n")

        root_node = task_graph.decompose(goal)
        yield AgentEvent(type="content", data=f"\n{task_graph.to_markdown()}\n\n")

        # 2. Iterate task loop
        pipeline = VerificationPipeline(workspace=self.workspace)
        debate_engine = DebateEngine(provider=self.provider)

        while True:
            ready_tasks = task_graph.get_ready_tasks()
            if not ready_tasks:
                # If there are still pending/failed tasks, we are blocked
                progress = task_graph.get_progress()
                if progress["pending"] > 0 or progress["failed"] > 0 or progress["blocked"] > 0:
                    yield AgentEvent(type="content", data="[red]⚠️ Autonomous execution loop blocked or some sub-tasks failed.[/red]\n")
                    break
                else:
                    # All tasks complete
                    break

            for task in ready_tasks:
                yield AgentEvent(type="content", data=f"\n[bold yellow]▶ Executing Sub-Task: {task.title} ({task.id})[/bold yellow]\n")

                subtask_attempts = 0
                max_subtask_retries = 2
                success = False
                nla_correction_block = ""

                while subtask_attempts < max_subtask_retries:
                    task.status = "running"
                    task_graph.save()
                    yield AgentEvent(type="state_change", data="executing")

                    subtask_attempts += 1
                    if subtask_attempts > 1:
                        yield AgentEvent(type="content", data=f"[bold purple]🧠 NLA Telemetry Self-Healing Attempt {subtask_attempts-1}/{max_subtask_retries}...[/bold purple]\n")

                    # Execute single subtask
                    plan_content = f"Technical sub-goal: {task.description}"
                    if nla_correction_block:
                        plan_content += f"\n\n{nla_correction_block}"

                    execution_err = None
                    try:
                        for event in self.executor.execute_plan(task.description, plan_content):
                            # Relay executor events
                            if event.type == "content_chunk" or event.type == "content":
                                yield event
                    except (ValueError, RuntimeError, OSError) as e:
                        execution_err = str(e)

                    failure_reason = None
                    if execution_err:
                        failure_reason = f"Execution Error: {execution_err}"
                    else:
                        # 3. Post-execution DevOps local test suite & static scan validation
                        yield AgentEvent(type="content", data="[cyan]🔍 Running local DevOps static validation & test verification...[/cyan]\n")
                        report = pipeline.run_full_pipeline()

                        if not report.tests_passed:
                            failure_reason = f"DevOps verification failed! Tests did not pass. Stacktrace: {report.traceback_analysis or 'No trace parsed'}"
                        elif report.secrets_found:
                            failure_reason = f"Security Alert: Hardcoded credentials/secrets found: {', '.join(s.pattern_name for s in report.secrets_found)}"
                        else:
                            # 4. Multi-Agent Debate review
                            yield AgentEvent(type="content", data="[cyan]⚖️ Convening parallel multi-agent expert review panel...[/cyan]\n")
                            # Gather recent diff context safely
                            changes_text = f"Subtask applied changes: {task.description}"
                            if (self.workspace / ".git").exists():
                                try:
                                    import subprocess
                                    # Try HEAD~1 first, fall back to HEAD for repos with < 2 commits
                                    diff_res = subprocess.run(
                                        ["git", "diff", "HEAD~1", "HEAD"],
                                        cwd=str(self.workspace),
                                        capture_output=True,
                                        text=True,
                                        timeout=10
                                    )
                                    if diff_res.returncode != 0:
                                        # Fallback for repos with < 2 commits
                                        diff_res = subprocess.run(
                                            ["git", "diff", "HEAD"],
                                            cwd=str(self.workspace),
                                            capture_output=True,
                                            text=True,
                                            timeout=10
                                        )
                                    if diff_res.returncode == 0:
                                        changes_text = diff_res.stdout or changes_text
                                except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
                                    logger.warning(f"Failed to get git diff for debate context: {e}")

                            verdict = debate_engine.run_debate(code_changes=changes_text, context=task.description)
                            if not verdict.final_approved:
                                failure_reason = f"Code review debate consensus failed: {verdict.consensus_summary}. Score: {verdict.consensus_score}/100"
                            elif verdict.reworked_code:
                                # Safe and robust parser to write reworked file changes back to disk
                                try:
                                    import re
                                    # Try parsing delineations like: ### File: src/main.py followed by a code block
                                    matches = list(re.finditer(
                                        r'(?:###\s*File:\s*|#\s*File:\s*|File:\s*)([^\n`]+)\n+```[a-zA-Z]*\n(.*?)\n```',
                                        verdict.reworked_code,
                                        re.DOTALL | re.IGNORECASE
                                    ))
                                    if matches:
                                        for match in matches:
                                            file_rel_path = match.group(1).strip()
                                            # Validate path stays within workspace
                                            target_file = self.workspace / file_rel_path
                                            try:
                                                resolved = target_file.resolve()
                                                if not str(resolved).startswith(str(self.workspace.resolve()) + os.sep):
                                                    logger.warning(f"Path traversal blocked in debate reworked code: {file_rel_path}")
                                                    continue
                                            except (OSError, ValueError):
                                                continue
                                            if target_file.exists():
                                                target_file.write_text(match.group(2), encoding="utf-8")
                                                yield AgentEvent(type="content", data=f"[green]✍️ Applied debate consensus refactoring to: {file_rel_path}[/green]\n")
                                    else:
                                        # Fallback: if a single code block is returned and only one file was modified in the diff, overwrite that file
                                        modified_files = []
                                        if (self.workspace / ".git").exists():
                                            import subprocess
                                            # Try HEAD~1 first, fall back to HEAD for repos with < 2 commits
                                            status_res = subprocess.run(
                                                ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
                                                cwd=str(self.workspace),
                                                capture_output=True,
                                                text=True
                                            )
                                            if status_res.returncode != 0:
                                                status_res = subprocess.run(
                                                    ["git", "diff", "--name-only", "HEAD"],
                                                    cwd=str(self.workspace),
                                                    capture_output=True,
                                                    text=True
                                                )
                                            if status_res.returncode == 0:
                                                modified_files = [f.strip() for f in status_res.stdout.splitlines() if f.strip()]

                                        code_block_match = re.search(r'```[a-zA-Z]*\n(.*?)\n```', verdict.reworked_code, re.DOTALL)
                                        code_to_write = code_block_match.group(1) if code_block_match else verdict.reworked_code.strip()

                                        if len(modified_files) == 1 and code_to_write:
                                            mf = modified_files[0].strip()
                                            target_file = self.workspace / mf
                                            try:
                                                resolved = target_file.resolve()
                                                if not str(resolved).startswith(str(self.workspace.resolve()) + os.sep):
                                                    logger.warning(f"Path traversal blocked in debate modified file: {mf}")
                                                else:
                                                    target_file.write_text(code_to_write, encoding="utf-8")
                                                    yield AgentEvent(type="content", data=f"[green]✍️ Applied debate consensus refactoring to: {mf}[/green]\n")
                                            except (OSError, ValueError):
                                                pass
                                except (OSError, ValueError) as write_ex:
                                    logger.warning(f"Failed to write reworked debate code to disk: {write_ex}")

                    if not failure_reason:
                        # Mark as completed
                        task.status = "completed"
                        task.result = "Passed execution, DevOps pipelines, and multi-agent code debates successfully."
                        task_graph.save()

                        yield AgentEvent(type="content", data=f"[bold green]✅ Sub-Task '{task.title}' completed successfully![/bold green]\n")
                        yield AgentEvent(type="content", data=f"{task_graph.to_markdown()}\n")
                        success = True
                        break
                    else:
                        # Sub-Task failed this attempt
                        yield AgentEvent(type="content", data=f"[red]❌ Attempt {subtask_attempts} failed: {failure_reason}[/red]\n")

                        if subtask_attempts <= max_subtask_retries:
                            # Leverage NLA Telemetry to self-heal
                            try:
                                records = self.executor.agent.nla_telemetry.load_records()
                                if records:
                                    last_rec = records[-1]
                                    last_thought = last_rec.thought_process
                                    last_strategy = last_rec.strategy_selected
                                else:
                                    last_thought = "None recorded"
                                    last_strategy = "unknown"

                                nla_correction_block = f"""
### 🧠 NLA Telemetry Self-Healing Directive
The previous attempt failed. Here is the NLA reasoning telemetry analysis of the failure:
- **Previous Failure Reason:** {failure_reason}
- **Previous Strategy:** {last_strategy}
- **NLA Activation Thought Trace:** {last_thought[:400]}...

**Correction Directive:** Adjust the strategy to bypass this failure. Refrain from repeating the previous error. Ensure all modifications are verified and error handling is robust.
"""
                            except (OSError, ValueError, RuntimeError):
                                nla_correction_block = f"""
### 🧠 NLA Telemetry Self-Healing Directive
The previous attempt failed due to: {failure_reason}.
**Correction Directive:** Correct the code/strategy carefully to fix this error.
"""
                        else:
                            # Out of retries
                            task.status = "failed"
                            task.result = failure_reason
                            task_graph.save()
                            break

        progress = task_graph.get_progress()
        final_success = progress["completed"] == progress["total"]

        yield AgentEvent(type="content", data=f"\n[bold green]🎉 Fully Autonomous Goal Graph Finished (Success: {final_success})[/bold green]\n")
        yield AgentEvent(type="state_change", data=AgentState.DONE)
        yield AgentEvent(type="done", data={"session_id": session_id, "success": final_success})
