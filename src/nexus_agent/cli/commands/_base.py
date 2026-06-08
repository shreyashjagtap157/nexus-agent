"""Base shared helpers for slash command handlers."""

from __future__ import annotations

import os
import sys
from typing import Any

from blessed import Terminal


_term = Terminal()

SLASH_COMMANDS = [
    {"name": "/help", "description": "Show available commands"},
    {"name": "/plan", "description": "Generate implementation plan (read-only)"},
    {"name": "/build", "description": "Execute implementation plan"},
    {"name": "/orchestrate", "description": "Plan → Approve → Execute → Verify"},
    {"name": "/autonomous", "description": "Full autonomous goal execution"},
    {"name": "/review", "description": "Multi-agent code review on git diff"},
    {"name": "/model", "description": "Manage, show, switch, or unload models"},
    {"name": "/mode", "description": "Set agent mode (auto|plan|build|review)"},
    {"name": "/effort", "description": "Set reasoning effort (low|medium|high|xhigh|max)"},
    {"name": "/goal", "description": "Set active coding objective"},
    {"name": "/sandbox", "description": "View/set sandbox execution mode"},
    {"name": "/context", "description": "Show context window token breakdown"},
    {"name": "/session", "description": "Show active session info"},
    {"name": "/stats", "description": "Conversation statistics"},
    {"name": "/memory", "description": "Search/edit CLAUDE.md memory files"},
    {"name": "/memory vector stats", "description": "Vector store statistics (count, engine mode, dimensions)"},
    {"name": "/memory vector query", "description": "Semantic similarity search via vector embeddings"},
    {"name": "/memory vector migrate", "description": "Re-embed all existing FTS5 memories into the vector store"},
    {"name": "/memory vector download", "description": "Download ONNX embedding model for higher-quality vectors"},
    {"name": "/reflect", "description": "Critique last assistant response"},
    {"name": "/task", "description": "View task graph progress"},
    {"name": "/debate", "description": "Convene multi-agent expert panel"},
    {"name": "/verify", "description": "Run DevOps pipeline (tests, linters, secrets)"},
    {"name": "/diff", "description": "Show git diff"},
    {"name": "/branch", "description": "Git branch management"},
    {"name": "/commit", "description": "Generate commit message and commit"},
    {"name": "/pr", "description": "Generate PR summary from git diff"},
    {"name": "/checkpoint", "description": "Save session checkpoint"},
    {"name": "/checkpoints", "description": "List available checkpoints"},
    {"name": "/rollback", "description": "Restore previous checkpoint"},
    {"name": "/clear", "description": "Clear conversation history and free context"},
    {"name": "/reset", "description": "Alias for /clear"},
    {"name": "/new", "description": "Alias for /clear"},
    {"name": "/compact", "description": "Compact conversation with optional focus"},
    {"name": "/fork", "description": "Fork the current conversation at this point"},
    {"name": "/resume", "description": "Resume a session by ID or name"},
    {"name": "/continue", "description": "Alias for /resume"},
    {"name": "/rename", "description": "Rename the current session"},
    {"name": "/copy", "description": "Copy last response to clipboard"},
    {"name": "/btw", "description": "Ask a quick side question (ephemeral)"},
    {"name": "/add-dir", "description": "Add a working directory to the session"},
    {"name": "/rewind", "description": "Rewind conversation and/or code to checkpoint"},
    {"name": "/fast", "description": "Toggle fast mode on or off"},
    {"name": "/cost", "description": "Show token usage statistics"},
    {"name": "/usage", "description": "Show plan usage limits"},
    {"name": "/extra-usage", "description": "Configure extra usage allowance"},
    {"name": "/status", "description": "Show version, model, account info"},
    {"name": "/theme", "description": "Change color theme"},
    {"name": "/color", "description": "Set the prompt bar color"},
    {"name": "/vim", "description": "Toggle vim editing mode"},
    {"name": "/exit", "description": "Exit the CLI"},
    {"name": "/desktop", "description": "Hand off session to Desktop app"},
    {"name": "/mobile", "description": "Show QR code for mobile app"},
    {"name": "/release-notes", "description": "View the changelog"},
    {"name": "/tasks", "description": "List and manage background tasks"},
    {"name": "/pr-comments", "description": "Fetch and display GitHub PR comments"},
    {"name": "/security-review", "description": "Analyze pending changes for vulnerabilities"},
    {"name": "/init", "description": "Initialize project with CLAUDE.md guide"},
    {"name": "/permissions", "description": "View or update tool permissions"},
    {"name": "/login", "description": "Sign in to account"},
    {"name": "/logout", "description": "Sign out of account"},
    {"name": "/keybindings", "description": "Edit keybindings configuration"},
    {"name": "/terminal-setup", "description": "Configure terminal keybindings"},
    {"name": "/statusline", "description": "Configure status line display"},
    {"name": "/privacy-settings", "description": "View and update privacy settings"},
    {"name": "/upgrade", "description": "Open upgrade page for higher plan tier"},
    {"name": "/feedback", "description": "Submit feedback about NexusAgent"},
    {"name": "/bug", "description": "Alias for /feedback"},
    {"name": "/ide", "description": "Manage IDE integrations"},
    {"name": "/chrome", "description": "Configure Chrome debugging settings"},
    {"name": "/plugin", "description": "Manage plugins"},
    {"name": "/reload-plugins", "description": "Reload plugins without restart"},
    {"name": "/agents", "description": "Manage sub-agent configurations"},
    {"name": "/hooks", "description": "View hook configurations for tool events"},
    {"name": "/install-github-app", "description": "Set up GitHub Actions app"},
    {"name": "/install-slack-app", "description": "Install Slack app"},
    {"name": "/remote-control", "description": "Enable remote control from web"},
    {"name": "/remote-env", "description": "Configure remote environment"},
    {"name": "/voice", "description": "Toggle voice input mode"},
    {"name": "/insights", "description": "Generate session analysis report"},
    {"name": "/passes", "description": "Share NexusAgent with friends"},
    {"name": "/doctor", "description": "Diagnose installation and settings"},
    {"name": "/search", "description": "Semantic code search across workspace"},
    {"name": "/index", "description": "Rebuild workspace code index"},
    {"name": "/browser", "description": "Navigate to URL and read content"},
    {"name": "/mcp", "description": "List/connect MCP servers"},
    {"name": "/skill", "description": "List/run agent skills"},
    {"name": "/config", "description": "View or set configuration"},
    {"name": "/settings", "description": "Alias for /config"},
    {"name": "/{", "description": "Display settings (refresh rate, fonts, colors)"},
    {"name": "/devops", "description": "Run full CI verification pipeline"},
    {"name": "/telemetry", "description": "View session telemetry summary"},
    {"name": "/log", "description": "View session log"},
    {"name": "/export", "description": "Export session to file"},
    {"name": "/retry", "description": "Retry last operation"},
    {"name": "/runtime", "description": "Scan/list/select LLM runtime backend"},
    {"name": "/undo", "description": "Undo last change via git/checkpoint"},
    {"name": "/scroll", "description": "Scroll transcript (up|down|page_up|page_down|bottom)"},
    {"name": "/view", "description": "Set view mode (default|focus|verbose)"},
    {"name": "/tui", "description": "Toggle fullscreen/inline mode"},
    {"name": "/quit", "description": "Exit NexusAgent"},
    {"name": "/nla", "description": "Natural Language Autoencoder reasoning telemetry & offline learning"},
    {"name": "/explain", "description": "Verbalize underlying concepts and strategies of the last step"},
]


class BaseCommands:
    """Mixin providing shared helpers for slash command handlers."""

    SLASH_COMMANDS = SLASH_COMMANDS

    # Per-instance state used by ``/copy`` and similar commands.
    _copied_text: str = ""
    _last_responses: list[str] = []  # most-recent assistant outputs (newest first)

    def _read_line(self, prompt_text: str, hidden: bool = False) -> str | None:
        """Read a line of input with the given prompt. If hidden, mask chars with *."""
        if prompt_text:
            self.r.console.print(prompt_text, end="")
        result = ""
        while True:
            key = _term.inkey(timeout=0.1)
            if not key:
                continue
            s = str(key)
            if s in ("\r", "\n"):
                self.r.console.print()
                break
            elif s in ("\x7f", "\x08"):
                if result:
                    result = result[:-1]
                    self.r.console.print("\b \b", end="")
            elif key.is_sequence and key.code == _term.KEY_ESCAPE:
                self.r.console.print()
                return None
            elif s == "\x03":
                raise KeyboardInterrupt
            elif s.isprintable():
                result += s
                self.r.console.print("*" if hidden else s, end="")
        return result

    def _handle_slash_command(self, command: str):
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        # Normalize command name to handler method name
        # e.g., "/add-dir" -> "_cmd_add_dir", "/init" -> "_cmd_init"
        raw_name = cmd.lstrip("/")
        handler_name = f"_cmd_{raw_name.replace('-', '_')}"

        handler = getattr(self, handler_name, None)
        if handler and callable(handler):
            handler(args)
        else:
            self.r.error(f"Unknown command: {cmd}. Type /help")

        self._refresh_status()

    def _render_effort_selector(self, levels: tuple, labels: tuple, idx: int):
        effort_colors = {"low": "green", "medium": "cyan", "high": "yellow", "xhigh": "magenta", "max": "red"}
        pad = 22

        plain_labels = [str(label) for label in labels]
        widths = [len(w) for w in plain_labels]
        gap = 4
        total_w = sum(widths) + gap * (len(widths) - 1)

        cumulative = 0
        centers = []
        for w in widths:
            centers.append(cumulative + w // 2)
            cumulative += w + gap

        label_parts = []
        for i, lab in enumerate(plain_labels):
            clr = effort_colors.get(lab, "dim")
            label_style = f"bold {clr}" if i == idx else f"dim {clr}"
            label_parts.append(f"[{label_style}]{lab}[/{label_style}]")
            if i < len(plain_labels) - 1:
                label_parts.append(" " * gap)

        label_line = " " * pad + "".join(label_parts)
        ptr_color = effort_colors.get(levels[idx], "yellow")
        marker_line = " " * (pad + centers[idx]) + "\u25b2"

        bar_chars = ["\u2500"] * total_w
        for i, c in enumerate(centers):
            bar_chars[c] = "\u253c" if i == idx else "\u252c"
        scale_line = " " * pad + "".join(bar_chars)

        gap_len = total_w - len("Faster") - len("Smarter")
        header_line = f"{' ' * pad}Faster{' ' * gap_len}Smarter"

        lines = [
            "  Effort",
            header_line,
            scale_line,
            marker_line,
            label_line,
            f"  \u2190/\u2192 adjust \u00b7 Enter confirm \u00b7 Esc cancel",
        ]

        h = len(lines)
        for line in lines:
            self.console.print(line)
        self._effort_selector_height = h

    def _clear_selector(self):
        if getattr(self, '_effort_selector_height', 0) > 0:
            for _ in range(self._effort_selector_height):
                sys.stdout.write(_term.move_up + _term.clear_eol)
            sys.stdout.flush()
            self._effort_selector_height = 0

    def _run_orchestrator(self, orch: Any, goal: str):
        self._abort_event.clear()
        self.r.show_spinner("Initializing Orchestration")
        try:
            for event in orch.run_autonomous(goal):
                if self._abort_event.is_set():
                    self.r.system_message("[red]Orchestration aborted by user.[/red]")
                    break

                if event.type == "state_change":
                    self._refresh_status()
                    self.r.set_terminal_title(self._status_line())
                elif event.type == "content":
                    self.r.hide_spinner()
                    self.console.print(event.data)
                    self.r.show_spinner("Orchestrating Goal...")
                elif event.type == "error":
                    self.r.hide_spinner()
                    self.r.error(str(event.data))
                elif event.type == "done":
                    self.r.hide_spinner()
                    self.r.system_message("Orchestration finished successfully.")
        except Exception as e:
            self.r.hide_spinner()
            self.r.error(f"Orchestration failed: {e}")
        finally:
            self.r.hide_spinner()
            self._abort_event.clear()

    def _runtime_progress(self, status: str, detail: str) -> None:
        """Progress callback for runtime installation."""
        icons = {"installing": "\u25b6", "verifying": "\u25cf", "complete": "\u2713", "error": "X"}
        icon = icons.get(status, "\u25b6")
        self.console.print(f"  [{icon}] {detail}")

    def _get_custom_runtimes(self):
        from nexus_agent.cli.runtimes import RuntimeInfo

        customs = []
        for name, path in self._config.get("custom_runtimes", {}).items():
            active_name = self._config.get("runtime", {}).get("name", "")
            is_active = (active_name == name)
            status_str = " (active)" if is_active else ""
            customs.append(RuntimeInfo(
                name=f"Custom: {name}{status_str}",
                provider="custom",
                available=True,
                path=path,
                description=f"User-provided custom runtime at {path}",
                priority=100 if is_active else 90,
            ))
        return customs
