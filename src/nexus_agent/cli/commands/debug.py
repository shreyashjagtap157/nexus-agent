"""Debug slash commands — /telemetry, /log, /doctor, /nla, /stats, etc."""

from __future__ import annotations

import json
from pathlib import Path

from rich.markdown import Markdown
from rich.panel import Panel

from nexus_agent import __version__
from nexus_agent.cli.commands._base import BaseCommands


class DebugCommands(BaseCommands):
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


    def _cmd_memory(self, args: str):
        if not args:
            if self._memory:
                self.console.print("  [bold]Memory subsystems:[/bold]")
                self.console.print("  Working:     Active task scratchpad")
                self.console.print("  Long-term:   Persistent knowledge (SQLite FTS5)")
                self.console.print("  Episodic:    Session history")
                self.console.print("  Profile:     Learned preferences")
                if self._project_memory:
                    self.console.print("  Project:    Project-level memory")
                self.console.print("\n  [dim]Usage: /memory [global|local] <query>[/dim]")
            else:
                self.r.system_message("Memory unavailable.")
            return
        if args.startswith("local"):
            mem = self._project_memory
            q = args[5:].strip()
            label = "local"
        elif args.startswith("global"):
            mem = self._memory
            q = args[6:].strip()
            label = "global"
        else:
            q = args
            label = None
            mem = None
        if mem:
            if q:
                results = mem.search(q)
                if results:
                    for r in results[:5]:
                        src = r.get("source", "?")
                        cat = r.get("category", "general")
                        content = r.get("content", "")[:120]
                        src_label = label if label else src
                        self.console.print(f"  [{src_label}:{cat}] [dim]{content}[/dim]")
                else:
                    self.r.system_message(f"No memories found: {q}")
            else:
                self.r.system_message(f"Usage: /memory {label or 'global'} <query>")
        elif label == "local" and not q:
            self.r.system_message("Usage: /memory local <query>")
        elif label == "global" and not q:
            self.r.system_message("Usage: /memory global <query>")
        elif label is None and q:
            results_g = self._memory.search(q) if self._memory else []
            results_l = self._project_memory.search(q) if self._project_memory else []
            seen: set[str] = set()
            combined = []
            for r in results_g + results_l:
                key = r.get("content", "")[:80]
                if key not in seen:
                    seen.add(key)
                    combined.append(r)
            if combined:
                for r in combined[:5]:
                    src = r.get("source", "?")
                    cat = r.get("category", "general")
                    content = r.get("content", "")[:120]
                    self.console.print(f"  [global:{src}:{cat}] [dim]{content}[/dim]")
            else:
                self.r.system_message(f"No memories found: {q}")
        else:
            self.r.system_message("Memory unavailable.")


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
            # Validate path stays within workspace
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


    def _cmd_cost(self, args: str):
        self.r.system_message(f"Cost: ${self._tokens.estimated_cost:.4f}")


    def _cmd_usage(self, args: str):
        self.console.print("\n  [bold]Session Token Usage[/bold]")
        self.console.print(f"  Input:  {self._tokens.total_input:,}")
        self.console.print(f"  Output: {self._tokens.total_output:,}")
        self.console.print(f"  Total:  {self._tokens.total:,}")
        self.console.print(f"  Est. Cost: ${self._tokens.estimated_cost:.4f}\n")


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

    # ── Placeholder stubs for unimplemented commands ──
