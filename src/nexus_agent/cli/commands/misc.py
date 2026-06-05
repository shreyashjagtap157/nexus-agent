"""Miscellaneous slash commands — /help, /quit, /feedback, etc."""

from __future__ import annotations

from rich.table import Table

from nexus_agent import __version__
from nexus_agent.cli.commands._base import BaseCommands


class MiscCommands(BaseCommands):
    """Mixin providing miscellaneous slash command handlers."""


    def _cmd_help(self, args: str):
        self.r.divider()
        self.console.print("[bold]Slash Commands:[/bold]")
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
        self.r.system_message("Project initialization: Not yet implemented (use /setup or follow the wizard)")


    def _cmd_add_dir(self, args: str):
        self.r.system_message("Add-dir: Not yet implemented")


    def _cmd_quit(self, args: str):
        self._is_running.clear()


    def _cmd_desktop(self, args: str):
        self.r.system_message("Desktop handoff: Not yet implemented")


    def _cmd_mobile(self, args: str):
        self.r.system_message("Mobile: Not yet implemented")


    def _cmd_release_notes(self, args: str):
        self.r.system_message(f"Release notes for v{__version__}: See CHANGELOG.md")


    def _cmd_tasks(self, args: str):
        self.r.system_message("Tasks: Not yet implemented")


    def _cmd_pr_comments(self, args: str):
        self.r.system_message("PR comments: Not yet implemented")


    def _cmd_security_review(self, args: str):
        self.r.system_message("Security review: Not yet implemented")


    def _cmd_login(self, args: str):
        self.r.system_message("Login/Logout feature coming soon.")


    def _cmd_logout(self, args: str):
        self.r.system_message("Login/Logout feature coming soon.")


    def _cmd_upgrade(self, args: str):
        self.r.system_message("Checking for updates... You are on the latest version.")


    def _cmd_feedback(self, args: str):
        import datetime
        from pathlib import Path
        if not args:
            self.r.system_message("Usage: /feedback <your feedback>")
            return
        feedback_dir = Path.home() / ".nexus" / "feedback"
        feedback_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = feedback_dir / f"feedback_{ts}.txt"
        file_path.write_text(args, encoding="utf-8")
        self.r.system_message(f"Feedback saved to {file_path}")


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


    def _cmd_plugin(self, args: str):
        self.r.system_message("Plugin system is being implemented.")


    def _cmd_reload_plugins(self, args: str):
        self.r.system_message("Plugin system is being implemented.")


    def _cmd_hooks(self, args: str):
        self.r.system_message("Hooks: Not yet implemented")


    def _cmd_install_github_app(self, args: str):
        self.r.system_message("GitHub App: Not yet implemented")


    def _cmd_install_slack_app(self, args: str):
        self.r.system_message("Slack App: Not yet implemented")


    def _cmd_remote_control(self, args: str):
        self.r.system_message("Remote control: Not yet implemented")


    def _cmd_remote_env(self, args: str):
        self.r.system_message("Remote env: Not yet implemented")


    def _cmd_voice(self, args: str):
        self.r.system_message("Voice: Not yet implemented")


    def _cmd_insights(self, args: str):
        if not hasattr(self, "_tokens"):
            self.r.system_message("Token usage stats unavailable.")
            return
        t = self._tokens
        self.r.system_message(f"Token usage: Read={t.total_input:,}, Write={t.total_output:,}, Cache={t.cache_creation + t.cache_read:,}")


    def _cmd_passes(self, args: str):
        self.r.system_message("Passes: Not yet implemented")


    def _cmd_copy(self, args: str):
        if not args:
            self.r.system_message("Usage: /copy {last,session,N}")
            return
        
        try:
            import pyperclip
        except ImportError:
            self.r.error("Clipboard support requires pyperclip. Run 'pip install pyperclip' to enable.")
            return

        
        blocks = getattr(self.r.transcript, 'blocks', [])
        if not blocks:
            self.r.system_message("Nothing to copy.")
            return
        
        text_to_copy = ""
        if args == "last":
            last_assistant = next((b for b in reversed(blocks) if b.block_type == "assistant"), None)
            if last_assistant:
                text_to_copy = last_assistant.content
            else:
                self.r.system_message("No assistant message found to copy.")
                return
        elif args == "session":
            lines = []
            for b in blocks:
                if b.block_type == "user":
                    lines.append(f"User: {b.content}")
                elif b.block_type == "assistant":
                    lines.append(f"Assistant: {b.content}")
                elif b.block_type == "tool_call":
                    lines.append(f"Tool Call: {b.name}({b.args})")
                elif b.block_type == "tool_result":
                    lines.append(f"Tool Result [{b.name}]: {b.content}")
                elif b.block_type == "system":
                    lines.append(f"System: {b.content}")
            text_to_copy = "\n".join(lines)
        else:
            try:
                n = int(args)
                selected = blocks[-n:] if n > 0 else []
                lines = []
                for b in selected:
                    if b.block_type == "user":
                        lines.append(f"User: {b.content}")
                    elif b.block_type == "assistant":
                        lines.append(f"Assistant: {b.content}")
                    elif b.block_type == "tool_call":
                        lines.append(f"Tool Call: {b.name}({b.args})")
                    elif b.block_type == "tool_result":
                        lines.append(f"Tool Result [{b.name}]: {b.content}")
                    elif b.block_type == "system":
                        lines.append(f"System: {b.content}")
                text_to_copy = "\n".join(lines)
            except ValueError:
                self.r.system_message("Invalid argument. Use 'last', 'session', or a number N.")
                return
        
        if text_to_copy:
            pyperclip.copy(text_to_copy)
            self.r.system_message(f"Copied {args} to clipboard.")
        else:
            self.r.system_message("Nothing to copy.")
