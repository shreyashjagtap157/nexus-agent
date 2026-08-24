"""Miscellaneous slash commands — /help, /quit, /feedback, /plugin, etc.

Extracted from the monolithic command_dispatcher.py.
"""

from __future__ import annotations

import datetime
from pathlib import Path

from nexus_agent import __version__


class MiscCommandsMixin:
    """Mixin providing miscellaneous slash command handlers."""

    def _cmd_help(self, args: str):
        self.r.divider()
        self.console.print("[bold]Slash Commands:[/bold]")
        from rich.table import Table
        table = Table(show_header=False, box=None, padding=(0, 2))
        for c in self.SLASH_COMMANDS:
            table.add_row(f"  [bold]{c['name']}[/bold]", f"[dim]{c['description']}[/dim]")
        self.console.print(table)
        self.console.print()
        self.console.print("[bold]Keyboard Shortcuts:[/bold]")
        kb = Table(show_header=False, box=None, padding=(0, 2))
        kb.add_row("  [bold]Enter[/bold]", "[dim]Send message / execute command[/dim]")
        kb.add_row("  [bold]Ctrl+C[/bold]", "[dim]Abort current request[/dim]")
        kb.add_row("  [bold]Ctrl+D[/bold]", "[dim]Exit NexusAgent[/dim]")
        kb.add_row("  [bold]Esc[/bold]", "[dim]Cancel selection / close menu[/dim]")
        kb.add_row("  [bold]Tab[/bold]", "[dim]Autocomplete slash command or @file[/dim]")
        kb.add_row("  [bold]↑/↓[/bold]", "[dim]Navigate command history[/dim]")
        kb.add_row("  [bold]/[/bold]  ", "[dim]Open slash command menu[/dim]")
        kb.add_row("  [bold]Ctrl+L[/bold]", "[dim]Clear terminal[/dim]")
        kb.add_row("  [bold]Ctrl+W[/bold]", "[dim]Delete word backward[/dim]")
        kb.add_row("  [bold]Ctrl+U[/bold]", "[dim]Delete line[/dim]")
        self.console.print(kb)
        self.r.divider()

    def _cmd_devops(self, args: str):
        self._cmd_verify(args)

    def _cmd_init(self, args: str):
        """Initialize a .nexus-agent.yaml project config in the current directory."""
        import yaml
        project_config = Path(".nexus-agent.yaml")
        if project_config.exists():
            self.r.system_message("Project config already exists. Use /config to modify.")
            return
        default_project = {
            "project": {
                "name": Path.cwd().name,
                "description": "",
            },
            "agent": {
                "effort_level": "medium",
                "mode": "auto",
            },
            "permissions": {
                "mode": "ask",
            },
        }
        project_config.write_text(yaml.dump(default_project, default_flow_style=False), encoding="utf-8")
        self.r.system_message(f"Created {project_config} — edit with /config or the file directly.")

    def _cmd_quit(self, args: str):
        self._is_running.clear()

    def _cmd_desktop(self, args: str):
        self.r.system_message("Desktop handoff: Not yet implemented")

    def _cmd_mobile(self, args: str):
        self.r.system_message("Mobile: Not yet implemented")

    def _cmd_release_notes(self, args: str):
        self.r.system_message(f"Release notes for v{__version__}: See CHANGELOG.md")

    def _cmd_tasks(self, args: str):
        """Toggle the Task Inspector visibility."""
        self.r.task_inspector.toggle()
        status = "visible" if self.r.task_inspector.visible else "hidden"
        self.r.system_message(f"Task Inspector is now {status}")

    def _cmd_pr_comments(self, args: str):
        self.r.system_message("PR comments: Not yet implemented")

    def _cmd_security_review(self, args: str):
        """Run a security scan of the current workspace."""
        try:
            from nexus_agent.core.devops import SecretScanner
            scanner = SecretScanner(Path.cwd())
            results = scanner.scan()
            if not results:
                self.r.system_message("No secrets detected in workspace.")
                return
            self.console.print(f"\n  [bold red]Security Review — {len(results)} potential issue(s):[/bold red]")
            for r in results[:20]:
                loc = f"{r.file_path}:{r.line_number}"
                self.console.print(f"  [red]![/red] [{r.pattern_name}] {loc}")
            if len(results) > 20:
                self.console.print(f"  [dim](...and {len(results) - 20} more)[/dim]")
            self.console.print()
        except Exception as exc:
            self.r.system_message(f"Security review failed: {exc}")

    def _cmd_login(self, args: str):
        self.r.system_message("Login/Logout feature coming soon.")

    def _cmd_logout(self, args: str):
        self.r.system_message("Login/Logout feature coming soon.")

    def _cmd_keybindings(self, args: str):
        self.r.system_message("Keybindings: Edit ~/.nexus-agent/keybindings.json")

    def _cmd_terminal_setup(self, args: str):
        self.r.system_message("Terminal setup: Configure in ~/.nexus-agent/config.yaml")

    def _cmd_privacy_settings(self, args: str):
        self.r.system_message("Privacy settings: Configure in ~/.nexus-agent/config.yaml under 'privacy'")

    def _cmd_upgrade(self, args: str):
        """Check for NexusAgent updates on PyPI."""
        try:
            from nexus_agent.core.updater import check_for_update, get_installed_version
            current = get_installed_version()
            info = check_for_update(current)
            if info.available:
                self.r.system_message(
                    f"Update available: v{info.latest} (current: v{info.current}).\n"
                    f"Run: pip install --upgrade nexus-agent"
                )
            else:
                self.r.system_message("You are running the latest version.")
        except Exception as exc:
            self.r.system_message(f"Update check failed: {exc}")

    def _cmd_update(self, args: str):
        """Alias for /upgrade — check for and display available updates."""
        self._cmd_upgrade(args)

    def _cmd_feedback(self, args: str):
        if not args:
            self.r.system_message("Usage: /feedback <your feedback>")
            return
        feedback_dir = Path.home() / ".nexus" / "feedback"
        feedback_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = feedback_dir / f"feedback_{ts}.txt"
        file_path.write_text(args, encoding="utf-8")
        self.r.system_message(f"Feedback saved to {file_path}")

    def _cmd_ide(self, args: str):
        self.r.system_message("IDE integration: Configure VS Code/Cursor in config.yaml under 'editor'")

    def _cmd_chrome(self, args: str):
        self.r.system_message("Chrome: Configure debugging port in config.yaml under 'browser'")

    def _cmd_plugin(self, args: str):
        """List or manage plugins."""
        if not hasattr(self, '_plugin_manager') or not self._plugin_manager:
            self.r.system_message("Plugin manager unavailable.")
            return
        pm = self._plugin_manager
        plugins = getattr(pm, 'plugins', {})
        if not plugins:
            self.r.system_message("No plugins loaded. Place .py files in ~/.nexus-agent/plugins/")
            return
        self.console.print("\n  [bold]Loaded Plugins:[/bold]")
        for name, info in plugins.items():
            desc = getattr(info, 'description', '') or ''
            self.console.print(f"  - [bold]{name}[/bold]: {desc}")
        self.console.print()

    def _cmd_reload_plugins(self, args: str):
        """Reload all plugins from disk."""
        if not hasattr(self, '_plugin_manager') or not self._plugin_manager:
            self.r.system_message("Plugin manager unavailable.")
            return
        try:
            self._plugin_manager.discover_plugins()
            count = len(getattr(self._plugin_manager, 'plugins', {}))
            self.r.system_message(f"Plugins reloaded — {count} plugin(s) loaded.")
        except Exception as exc:
            self.r.system_message(f"Plugin reload failed: {exc}")

    def _cmd_agents(self, args: str):
        if not hasattr(self, "_skill_registry") or not self._skill_registry:
            self.r.system_message("Skill registry unavailable.")
            return
        skills = self._skill_registry.skills
        if not skills:
            self.r.system_message("No skills registered.")
            return
        self.console.print("\n  [bold]Registered Agent Personas:[/bold]")
        for name in sorted(skills.keys()):
            self.console.print(f"  - {name}")
        self.console.print()

    def _cmd_hooks(self, args: str):
        self.r.system_message("Hooks: Configure in config.yaml under 'hooks'")

    def _cmd_install_github_app(self, args: str):
        self.r.system_message("GitHub App: Run `nexus install-github-app`")

    def _cmd_install_slack_app(self, args: str):
        self.r.system_message("Slack App: Run `nexus install-slack-app`")

    def _cmd_remote_control(self, args: str):
        self.r.system_message("Remote control: Enable via config.yaml under 'remote'")

    def _cmd_remote_env(self, args: str):
        self.r.system_message("Remote env: Configure in config.yaml under 'remote'")

    def _cmd_voice(self, args: str):
        self.r.system_message("Voice input: Not yet implemented")

    def _cmd_insights(self, args: str):
        if not hasattr(self, "_tokens"):
            self.r.system_message("Token usage stats unavailable.")
            return
        t = self._tokens
        self.r.system_message(f"Token usage: Read={t.total_input:,}, Write={t.total_output:,}, Cache={t.cache_creation + t.cache_read:,}")

    def _cmd_passes(self, args: str):
        """Show reasoning passes from the last agent run."""
        if not hasattr(self, '_nla_telemetry') or not self._nla_telemetry:
            self.r.system_message("No telemetry data available.")
            return
        try:
            records = self._nla_telemetry.get_session_records()
            if not records:
                self.r.system_message("No reasoning passes recorded this session.")
                return
            self.console.print(f"\n  [bold]Reasoning Passes — {len(records)} record(s):[/bold]")
            for i, rec in enumerate(records[-10:], 1):
                thought = getattr(rec, 'thought_process', '')[:80]
                conf = getattr(rec, 'confidence', 0)
                self.console.print(f"  {i}. [dim]{thought}...[/dim] (confidence: {conf:.0%})")
            self.console.print()
        except Exception as exc:
            self.r.system_message(f"Failed to read passes: {exc}")
