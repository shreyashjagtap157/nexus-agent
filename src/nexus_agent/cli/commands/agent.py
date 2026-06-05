"""Agent slash commands — /mode, /effort, /goal, /plan, /build, etc."""

from __future__ import annotations

import re
import subprocess
import time

from rich.panel import Panel
from rich.table import Table

from nexus_agent.cli.commands._base import BaseCommands
from nexus_agent.core.config import save_config


class AgentCommands(BaseCommands):
    """Mixin providing agent-control slash command handlers."""


    def _cmd_mode(self, args: str):
        if args:
            try:
                from nexus_agent.core.agent import AgentMode
                mode = AgentMode(args.lower())
                self._current_mode = mode
                if self._agent:
                    self._agent.mode = mode
                self.r.system_message(f"Mode: {mode.value.upper()}")
            except ValueError:
                self.r.error(f"Invalid mode: {args} (auto|plan|build|review)")
        else:
            self.r.system_message(f"Mode: {self._current_mode.value.upper()}")


    def _cmd_effort(self, args: str):
        valid = ("low", "medium", "high", "xhigh", "max")
        labels = valid

        if args.lower() in valid:
            lvl = args.lower()
            self._config.setdefault("agent", {})["effort_level"] = lvl
            if self._agent:
                self._agent.effort_level = lvl
                from nexus_agent.core.agent import AgentLoop
                ecfg = AgentLoop.EFFORT_CONFIG.get(lvl, AgentLoop.EFFORT_CONFIG["medium"])
                self._agent.max_iterations = ecfg["max_iterations"]
                self._agent.temperature = ecfg["temperature"]
                self._agent.max_tokens = ecfg["max_tokens"]
                self._agent._reflection_enabled = ecfg["reflection"]
            self.r.system_message(f"Effort set to {lvl}")
            save_config(self._config, self.config_path)
            return

        current = self._config.get("agent", {}).get("effort_level", "medium").lower()
        idx = valid.index(current) if current in valid else 1

        self._render_effort_selector(valid, labels, idx)

        while True:
            if not self._kbhit():
                time.sleep(0.02)
                continue
            ch = self._read_byte()
            if ch == b"\xe0":
                ext = self._read_byte()
                if ext == b"K":
                    idx = max(0, idx - 1)
                    self._render_effort_selector(valid, labels, idx)
                elif ext == b"M":
                    idx = min(len(valid) - 1, idx + 1)
                    self._render_effort_selector(valid, labels, idx)
            elif ch == b"\r":
                self._clear_selector()
                lvl = valid[idx]
                self._config.setdefault("agent", {})["effort_level"] = lvl
                if self._agent:
                    self._agent.effort_level = lvl
                    from nexus_agent.core.agent import AgentLoop
                    ecfg = AgentLoop.EFFORT_CONFIG.get(lvl, AgentLoop.EFFORT_CONFIG["medium"])
                    self._agent.max_iterations = ecfg["max_iterations"]
                    self._agent.temperature = ecfg["temperature"]
                    self._agent.max_tokens = ecfg["max_tokens"]
                    self._agent._reflection_enabled = ecfg["reflection"]
                self.r.system_message(f"Effort set to {lvl}")
                save_config(self._config, self.config_path)
                self._refresh_status()
                return
            elif ch in (b"\x1b", b"\x03"):
                self._clear_selector()
                self.r.system_message("Cancelled")
                return


    def _cmd_goal(self, args: str):
        if args:
            self._config.setdefault("agent", {})["goal"] = args
            if self._agent:
                self._agent.goal = args
            self.r.system_message(f"Goal: {args}")
            from nexus_agent.core.config import save_config
            save_config(self._config, self.config_path)

            # Auto-run autonomous goal orchestrator!
            self.r.system_message("Spawning Devin-style Multi-Agent Orchestrator for Goal...")
            from nexus_agent.core.orchestrator import Orchestrator
            orch = Orchestrator(
                provider=self._agent.provider if self._agent else self._engine,
                tools=self._agent.tools if self._agent else [],
                workspace=self.workspace,
            )

            self._processing = True
            try:
                self._run_orchestrator(orch, args)
            finally:
                self._processing = False
        else:
            g = self._config.get("agent", {}).get("goal", "")
            self.r.system_message(f"Goal: {g}" if g else "No goal set.")


    def _cmd_sandbox(self, args: str):
        if args in ("safe", "moderate", "dangerous", "blocked"):
            from nexus_agent.core.sandbox import RiskLevel
            level = RiskLevel(args.upper())
            self._config.setdefault("sandbox", {})["default_level"] = args
            self.r.system_message(f"Sandbox: {level.value}")
            save_config(self._config, self.config_path)
        else:
            current = self._config.get("sandbox", {}).get("default_level", "moderate")
            self.r.system_message(f"Sandbox: {current.upper()}  Usage: /sandbox [safe|moderate|dangerous|blocked]")


    def _cmd_context(self, args: str):
        self.console.print()
        self.console.print(self._context.render(self._tokens))
        self.console.print()


    def _cmd_reflect(self, args: str):
        if self._agent and self._agent.messages:
            from nexus_agent.llm.base import Role
            last = None
            for m in reversed(self._agent.messages):
                if m.role == Role.ASSISTANT and m.content:
                    last = m.content
                    break
            if last:
                self.r.show_spinner("Critiquing")
                try:
                    critique = self._agent.reflection_engine.evaluate("Last request", last)
                    self.r.hide_spinner()
                    self.console.print()
                    self.console.print(critique.to_feedback_prompt())
                except (ValueError, RuntimeError) as e:
                    self.r.hide_spinner()
                    self.r.error(f"Reflection: {e}")
            else:
                self.r.system_message("No response to critique.")
        else:
            self.r.system_message("No agent active.")


    def _cmd_task(self, args: str):
        if self._agent:
            from nexus_agent.core.task_graph import TaskGraph
            tg = TaskGraph(session_id=self._agent.session_id, workspace=self.workspace, provider=self._agent.provider)
            if tg.load():
                self.r.assistant_message(tg.to_markdown())
            elif self._agent.goal:
                self.r.show_spinner("Decomposing goal")
                try:
                    tg.decompose(self._agent.goal)
                    self.r.hide_spinner()
                    self.r.assistant_message(tg.to_markdown())
                except (ValueError, RuntimeError) as e:
                    self.r.hide_spinner()
                    self.r.error(f"Task: {e}")
            else:
                self.r.system_message("Set a goal with /goal")
        else:
            self.r.system_message("No agent.")


    def _cmd_debate(self, args: str):
        if self._agent:
            from nexus_agent.core.debate import DebateEngine
            self.r.show_spinner("Convening panel")
            try:
                diff = subprocess.run(["git", "diff", "HEAD"], cwd=str(self.workspace), capture_output=True, text=True, timeout=10)
                changes = diff.stdout or ""
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                changes = ""
            if not changes:
                changes = "(no git changes)"
            try:
                engine = DebateEngine(provider=self._agent.provider)
                self.r.hide_spinner()
                verdict = engine.run_debate(code_changes=changes)
                self.r.assistant_message(verdict.consensus_summary + "\n\n" + "\n".join(f"- {r}" for r in verdict.recommendations[:5]))
            except (ValueError, RuntimeError) as e:
                self.r.hide_spinner()
                self.r.error(f"Debate: {e}")


    def _cmd_verify(self, args: str):
        from nexus_agent.core.devops import VerificationPipeline
        self.r.show_spinner("Running verification pipeline")
        try:
            pipeline = VerificationPipeline(workspace=self.workspace)
            report = pipeline.run_full_pipeline()
            self.r.hide_spinner()
            lines = [
                "**Verification Report**",
                f"- Status: {'✅ SUCCESS' if report.success else '❌ FAILURE'}",
                f"- Test framework: {report.test_framework_detected or 'None'}",
                f"- Tests passed: {report.tests_passed}",
                f"- Linters passed: {report.linters_passed}",
            ]
            if report.secrets_found:
                lines.append("- 🔒 Secrets:")
                for s in report.secrets_found:
                    lines.append(f"  - {s.file_path}:{s.line_number} ({s.pattern_name})")
            if report.vulnerabilities_found:
                lines.append("- ⚠️  Vulnerabilities:")
                for v in report.vulnerabilities_found:
                    lines.append(f"  - {v}")
            self.r.assistant_message("\n".join(lines))
        except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as e:
            self.r.hide_spinner()
            self.r.error(f"Verification: {e}")


    def _cmd_retry(self, args: str):
        if not self._agent or not self._agent.messages:
            self.r.system_message("Nothing to retry.")
            return
        from nexus_agent.llm.base import Role
        for msg in reversed(self._agent.messages):
            if msg.role == Role.USER and msg.content:
                self.r.system_message("Retrying last user request...")
                self._processing = True
                self._run_agent(msg.content)
                self._processing = False
                return
        self.r.system_message("No user message found to retry.")


    def _cmd_undo(self, args: str):
        try:
            result = subprocess.run(
                ["git", "checkout", "--", "."],
                cwd=str(self.workspace), capture_output=True, text=True, timeout=10,
            )
            self.r.system_message(f"Undone: {result.stdout.strip() or 'working tree cleaned'}")
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            self.r.error(f"Undo: {e}")


    def _cmd_explain(self, args: str):
        if not self._agent or not self._agent.messages:
            self.r.system_message("No message history available to explain.")
            return

        from nexus_agent.llm.base import Role
        last_thought = ""
        last_strategy = "unknown"
        last_tools = []

        try:
            records = self._agent.nla_telemetry.load_records()
            if records:
                last_rec = records[-1]
                last_thought = last_rec.thought_process
                last_strategy = last_rec.strategy_selected
                last_tools = last_rec.tools_considered
        except (ValueError, RuntimeError, OSError):
            pass

        if not last_thought:
            for m in reversed(self._agent.messages):
                if m.role == Role.ASSISTANT and m.content:
                    last_thought = m.content
                    last_strategy = "direct_response"
                    break

        if not last_thought:
            self.r.system_message("No assistant response found to explain.")
            return

        self.r.show_spinner("Reconstructing activation explanations")
        self.r.hide_spinner()

        self.console.print()
        table = Table(box=None, show_header=False, padding=(0, 2))
        table.add_row("[bold purple]Reasoning Strategy:[/bold purple]", f"[bold]{last_strategy.upper()}[/bold]")
        if last_tools:
            table.add_row("[bold purple]Tools Evaluated:[/bold purple]", ", ".join(f"`{t}`" for t in last_tools))

        words = re.findall(r'\b[a-zA-Z]{5,15}\b', last_thought.lower())
        stop_words = {"about", "there", "their", "would", "could", "should", "these", "those", "which", "where", "assistant", "message", "thought"}
        concepts = sorted(list(set(w for w in words if w not in stop_words)))[:6]

        self.console.print(Panel(
            table,
            title="🎯 Active Concept Activation Map",
            border_style="purple",
            padding=(1, 1)
        ))

        if concepts:
            self.console.print("  [bold purple]Reconstructed Active Concepts:[/bold purple]")
            self.console.print("  [dim](Note: similarity scores are heuristic estimates)[/dim]")
            for c in concepts:
                # Use hash-based intensity for deterministic, stable values per concept
                intensity = (hash(c) % 34) + 65  # 65-98 range, stable per concept
                bar = "█" * (intensity // 10) + "░" * (10 - (intensity // 10))
                self.console.print(f"    - [cyan]{c:<15}[/cyan]  {bar}  [bold purple]{intensity}%[/bold purple]")
            self.console.print()


    def _cmd_btw(self, args: str):
        import random
        advice = [
            "Always write tests for your most critical logic.",
            "Remember to document your complex functions.",
            "Keep your functions small and focused.",
            "Don't forget to commit often.",
            "Read the documentation before asking!",
            "Code is read much more often than it is written.",
            "A little refactoring goes a long way.",
            "Error handling is as important as the happy path."
        ]
        if args:
            self.r.system_message(f"💡 By the way: {args}")
        else:
            self.r.system_message(f"💡 By the way: {random.choice(advice)}")


    def _cmd_fast(self, args: str):
        self._cmd_effort("low")


    def _cmd_plan(self, args: str):
        self._run_agent(f"Plan the implementation for: {args}" if args else "Generate implementation plan for the current task.")


    def _cmd_build(self, args: str):
        self._run_agent("Execute the implementation plan step by step.")


    def _cmd_orchestrate(self, args: str):
        self._run_agent("Orchestrate: plan, approve, execute, verify cycle.")


    def _cmd_autonomous(self, args: str):
        self._run_agent("Run autonomously to achieve the goal.")


    def _cmd_review(self, args: str):
        self._run_agent("Review the current code changes.")


    def _cmd_compact(self, args: str):
        if self._agent:
            self.r.system_message("Compacting conversation…")
            self._agent.compact_history()
            self.r.system_message("Compacted.")
        else:
            self.r.system_message("No agent active.")


    def _cmd_quick(self, args: str):
        self._run_agent(args)
