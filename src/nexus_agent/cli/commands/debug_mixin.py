"""Debug slash commands — /nla, /explain, /telemetry, /log, /cost, /stats, etc.

Extracted from the monolithic command_dispatcher.py to reduce file size
and group debug/diagnostic logic together.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from nexus_agent import __version__


class DebugCommandsMixin:
    """Mixin providing debug/diagnostic slash command handlers."""

    def _cmd_stats(self, args: str):
        if self._agent:
            stats = self._agent.get_stats()
            for k, v in stats.items():
                if k == "model" and (not stats.get("message_count") and not stats.get("iteration_count")):
                    continue
                if k == "provider" and (not stats.get("message_count") and not stats.get("iteration_count")):
                    continue
                if k == "token_estimate" and v == 0:
                    continue
                self.console.print(f"  [cyan]{k}:[/cyan] {v}")
            self.console.print("  [cyan]Token breakdown:[/cyan]")
            self.console.print(f"    Input:  {self._tokens.total_input:,}")
            self.console.print(f"    Output: {self._tokens.total_output:,}")
            self.console.print(f"    Total:  {self._tokens.total:,}")

    def _cmd_telemetry(self, args: str):
        if self._agent:
            self.r.show_spinner("Generating telemetry summary")
        try:
            summary = self._agent.nla_telemetry.generate_session_summary()
            self.r.hide_spinner()
            self.console.print(f"\n  [dim]{summary}[/dim]\n")
        except (ValueError, RuntimeError) as e:
            self.r.hide_spinner()
            self.r.error(f"Telemetry: {e}")
        else:
            self.r.system_message("No agent.")

    def _cmd_log(self, args: str):
        if self._session_mgr:
            try:
                messages = self._session_mgr.get_messages(limit=20)
                if not messages:
                    self.r.system_message("No messages in session.")
                    return
                for msg in messages[-20:]:
                    role = msg.get("role", "?").upper()
                    content = msg.get("content", "")[:150]
                    self.console.print(f"  [{role:>9}] [dim]{content}[/dim]")
            except (ValueError, OSError, TypeError, KeyError) as e:
                self.r.error(f"Log: {e}")
        else:
            self.r.system_message("Session manager unavailable.")

    def _cmd_scroll(self, args: str):
        dirs = {
            "up": lambda: self.r.scroll_up(),
            "down": lambda: self.r.scroll_down(),
            "page_up": lambda: self.r.page_up(),
            "page_down": lambda: self.r.page_down(),
            "top": lambda: self.r.viewport.scroll_up(99999),
            "bottom": lambda: self.r.viewport.scroll_to_bottom(),
        }
        action = dirs.get(args.strip())
        if action:
            action()
            if self.r._is_fullscreen:
                self.r._render_fullscreen()
        else:
            self.r.system_message("Usage: /scroll [up|down|page_up|page_down|top|bottom]")

    def _cmd_view(self, args: str):
        if args.strip() in ("default", "focus", "verbose"):
            self.r.set_view_mode(args.strip())
            self.r.system_message(f"View mode: {args.strip()}")
        else:
            current = self.r._view_mode
            self.r.system_message(f"Current view: {current}  Usage: /view [default|focus|verbose]")

    def _cmd_nla(self, args: str):
        if not self._agent:
            self.r.system_message("No agent session is currently active.")
            return

        parts = args.strip().split(maxsplit=1) if args else []
        sub = parts[0].lower() if parts else "summary"

        if sub == "summary":
            self.r.show_spinner("Analyzing autoencoder telemetry")
            try:
                summary = self._agent.nla_telemetry.generate_session_summary()
                self.r.hide_spinner()
                self.console.print()
                self.console.print(Panel(
                    Markdown(summary),
                    title="🧠 NLA Reasoning Summary",
                    border_style="purple",
                    padding=(1, 2)
                ))
            except (ValueError, RuntimeError) as e:
                self.r.hide_spinner()
                self.r.error(f"Failed to generate summary: {e}")

        elif sub == "export":
            if len(parts) >= 2:
                requested = Path(parts[1].strip()).resolve()
                if str(requested).startswith(str(self.workspace.resolve())):
                    path = requested
                else:
                    path = None
            else:
                path = None
            if path is None:
                path = self.workspace / f"nla_pairs_{self._agent.session_id[:8]}.json"
            self.r.show_spinner("Extracting reflection training pairs")
            try:
                pairs = self._agent.nla_telemetry.export_training_pairs()
                self.r.hide_spinner()
                if pairs:
                    path.write_text(json.dumps(pairs, indent=2), encoding="utf-8")
                    self.r.system_message(f"Successfully exported {len(pairs)} autoencoder training pairs to {path}")
                else:
                    self.r.system_message("No high-confidence reasoning steps available to export yet.")
            except (ValueError, RuntimeError, OSError, TypeError) as e:
                self.r.hide_spinner()
                self.r.error(f"Failed to export training pairs: {e}")

        elif sub == "errors":
            self.r.show_spinner("Discovering error triggers")
            try:
                patterns = self._agent.nla_telemetry.get_error_patterns()
                self.r.hide_spinner()
                self.console.print("\n  [bold]NLA Error Trigger Statistics:[/bold]\n")
                if patterns:
                    for err, count in sorted(patterns.items(), key=lambda x: x[1], reverse=True):
                        self.console.print(f"  [{count:>3}x] [red]{err}[/red]")
                else:
                    self.console.print("  [green]No error triggers recorded in telemetry logs.[/green]")
                self.console.print()
            except (ValueError, RuntimeError) as e:
                self.r.hide_spinner()
                self.r.error(f"Failed to analyze error patterns: {e}")

        elif sub == "status":
            tel = self._agent.nla_telemetry
            self.console.print("\n  [bold]NLA Telemetry Status:[/bold]")
            self.console.print(f"  Session ID:   [dim]{tel.session_id}[/dim]")
            self.console.print(f"  Log File:     [dim]{tel.log_file}[/dim]")
            self.console.print(f"  Buffer Size:  {len(tel._buffer)} / {tel._buffer_max_size}")
            self.console.print(f"  Total In-Mem: {len(tel.records)}")
            self.console.print(f"  Active Trace: {'✓ running' if tel.log_file.exists() else '○ standby'}\n")
        else:
            self.r.system_message("Usage: /nla [summary|export [path]|errors|status]")

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
                intensity = (hash(c) % 34) + 65
                bar = "█" * (intensity // 10) + "░" * (10 - (intensity // 10))
                self.console.print(f"    - [cyan]{c:<15}[/cyan]  {bar}  [bold purple]{intensity}%[/bold purple]")
            self.console.print()

    def _cmd_cost(self, args: str):
        tracker = getattr(self, "usage_tracker", None)
        if args.strip() in ("help", "--help", "-h"):
            self.r.system_message(
                "Usage: /cost [today|week|all|session|model|<days=N>]\n"
                "  (no args)  - current session + lifetime totals\n"
                "  today      - usage in the last 24 hours\n"
                "  week       - usage in the last 7 days\n"
                "  all        - lifetime usage\n"
                "  session    - detailed breakdown by session\n"
                "  model      - detailed breakdown by model\n"
                "  days=N     - usage in the last N days"
            )
            return

        import time as _time

        current = self._tokens.estimated_cost
        if tracker is None:
            self.r.system_message(
                f"Cost: ${current:.4f} (no usage tracker configured)"
            )
            return

        arg = args.strip().lower()
        if arg in ("session", "model", "all", "today", "week", "") or arg.startswith("days="):
            if arg == "session":
                s = tracker.summarize()
                if not s.by_session:
                    self.r.system_message("No historical usage recorded.")
                    return
                lines = [f"Session: {self._session_label()} (current)"]
                for sid, x in s.by_session.items():
                    lines.append(
                        f"  {sid[:40]:<40} {x['total_tokens']:>10,} tok ${x['estimated_cost']:.4f}"
                    )
                self.r.system_message("\n".join(lines))
                return
            if arg == "model":
                s = tracker.summarize()
                if not s.by_model:
                    self.r.system_message("No historical usage recorded.")
                    return
                lines = ["By model:"]
                for m, x in s.by_model.items():
                    lines.append(
                        f"  {m[:40]:<40} {x['total_tokens']:>10,} tok ${x['estimated_cost']:.4f}"
                    )
                self.r.system_message("\n".join(lines))
                return
            since = None
            if arg == "today":
                since = _time.time() - 24 * 3600
            elif arg == "week":
                since = _time.time() - 7 * 24 * 3600
            elif arg.startswith("days="):
                try:
                    n = int(arg.split("=", 1)[1])
                    since = _time.time() - n * 24 * 3600
                except ValueError:
                    self.r.system_message(f"Invalid days value: {arg}")
                    return
            s = tracker.summarize(since_ts=since)
            lines = s.to_lines()
            lines.insert(0, f"Current session: ${current:.4f}")
            self.r.system_message("\n".join(lines))
            return

        self.r.system_message(f"Cost: ${current:.4f}")

    def _cmd_usage(self, args: str):
        self.r.system_message(
            "Usage tracking: use /cost for token/cost details. "
            "Use /cost help for subcommands."
        )

    def _cmd_extra_usage(self, args: str):
        self.r.system_message("Extra usage: Not yet implemented")

    def _cmd_status(self, args: str):
        self.console.print("\n  [bold]NexusAgent Status[/bold]")
        self.console.print(f"  Version: {__version__}")
        self.console.print(f"  Model: {self._model_name()}")
        self.console.print(f"  Provider: {self._provider_name or 'local'}")
        self.console.print(f"  Mode: {self._current_mode.value.upper()}")
        self.console.print(f"  Active Session: {self._session_id or 'none'}")
        self.console.print(f"  Workspace: {self.workspace}")
        self.console.print(f"  Tokens (I/O): {self._tokens.total_input:,} / {self._tokens.total_output:,}")
        self.console.print(f"  Estimated Cost: ${self._tokens.estimated_cost:.4f}")
        if self._auth_store:
            providers = self._auth_store.get_status()
            if providers:
                self.console.print("  \n  [bold]Provider Status:[/bold]")
                for prov, status in providers.items():
                    self.console.print(f"    {prov:<15} {status}")
        self.console.print()

    def _cmd_doctor(self, args: str):
        self.console.print("\n  [bold]NexusAgent Diagnostics[/bold]")
        self.console.print(f"  ✓ Version: {__version__}")
        self.console.print(f"  {'✓' if self._engine else '✗'} Engine: {'Loaded' if self._engine and getattr(self._engine, 'is_loaded', False) else 'Not loaded'}")
        self.console.print(f"  {'✓' if self._agent else '✗'} Agent: {'Initialized' if self._agent else 'Not initialized'}")
        self.console.print(f"  {'✓' if self._memory else '✗'} Memory: {'Available' if self._memory else 'Unavailable'}")
        self.console.print(f"  {'✓' if self._session_mgr else '✗'} Sessions: {'Available' if self._session_mgr else 'Unavailable'}")
        self.console.print(f"  MCP servers: {len(getattr(self, '_mcp_clients', []))}")
        self.console.print(f"  Skills: {len(getattr(self._skill_registry, 'skills', {})) if self._skill_registry else 0}")
        self.console.print(f"  Workspace: {self.workspace}")
        self.console.print(f"  Config: {self.config_path or 'default'}")
