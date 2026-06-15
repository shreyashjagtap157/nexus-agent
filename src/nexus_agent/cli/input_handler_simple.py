"""Input handler — simple blocking input with basic command support."""

from __future__ import annotations

import sys

from nexus_agent.cli.commands._base import SLASH_COMMANDS


class MinimalInputHandlerMixin:
    """Mixin providing simple input handling — no blessed, no cursor tracking."""

    SLASH_COMMANDS = SLASH_COMMANDS

    def _read_input(self) -> str | None:
        """Read a line of input using blocking input(). Simple and reliable."""
        try:
            line = input("> ")
            return line.strip() if line.strip() else None
        except (KeyboardInterrupt, EOFError):
            return None

    def _handle_slash_command(self, command: str):
        """Handle slash commands - delegate to BaseCommands for full handler, handle basics here."""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        parts[1] if len(parts) > 1 else ""

        if cmd == "/help":
            self._minimal_help()
        elif cmd in ("/exit", "/quit"):
            print("Goodbye.")
            sys.exit(0)
        elif cmd == "/clear":
            self.r.console.clear()
            self._rebuild_welcome()
        elif cmd == "/status":
            effort = self._config.get("agent", {}).get("effort_level", "medium").lower()
            self.r.system_message(f"Mode: {self._current_mode.value.upper()} | Effort: {effort.upper()}")
        else:
            # For other commands, try to delegate to BaseCommands handler
            try:
                from nexus_agent.cli.commands._base import BaseCommands
                if hasattr(BaseCommands, '_handle_slash_command'):
                    # Call the base implementation
                    BaseCommands._handle_slash_command(self, command)
                    return
            except (ImportError, AttributeError):
                pass
            self.r.error(f"Unknown command: {cmd}. Type /help for available commands.")

    def _minimal_help(self):
        """Display available commands."""
        self.r.divider()
        self.console.print("[bold]Available Commands:[/bold]")
        # Show commands in columns
        cmds = list(self.SLASH_COMMANDS)
        for i in range(0, len(cmds), 2):
            c1 = cmds[i] if i < len(cmds) else ""
            c2 = cmds[i+1] if i+1 < len(cmds) else None
            if c2:
                self.console.print(f"  [bold]{c1['name']:<15}[/bold] [dim]{c1['description']}[/dim]    [bold]{c2['name']:<15}[/bold] [dim]{c2['description']}[/dim]")
            else:
                self.console.print(f"  [bold]{c1['name']:<15}[/bold] [dim]{c1['description']}[/dim]")
        self.r.divider()
