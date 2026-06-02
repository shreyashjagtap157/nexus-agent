"""Multi-Agent Orchestrator — Coordinates specialized sub-agents.

Orchestrates sequential planning, user approvals, execution, and verification
using Planner and Executor sub-agents (inspired by jules/antigravity patterns).

Adds Phase 9 state-of-the-art fully autonomous goal execution using task graphs,
DevOps pipelines, and parallel multi-agent debates.
"""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from nexus_agent.core.agent import AgentEvent, AgentState
from nexus_agent.core.debate import DebateEngine
from nexus_agent.core.devops import VerificationPipeline
from nexus_agent.core.executor import Executor
from nexus_agent.core.planner import Planner
from nexus_agent.core.task_graph import TaskGraph
from nexus_agent.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class Orchestrator:
    """Multi-Agent Orchestrator.

    Coordinates specialized sub-agents:
    1. Spawn Planner to generate a technical plan (read-only).
    2. Prompt for user feedback or approval (gated).
    3. Spawn Executor to write code, test, and verify.
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
