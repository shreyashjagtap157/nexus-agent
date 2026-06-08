"""Command dispatcher — slash command routing and handlers for NexusApp."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from nexus_agent import __version__
from nexus_agent.cli.renderer import (
    HAS_MSVCRT,
    TokenUsage,
    alternate_screen,
    clear_to_end,
    disable_mouse,
    enable_mouse,
    hide_cursor,
    main_screen,
    move_to,
    show_cursor,
)
from nexus_agent.core.config import save_config
from nexus_agent.cli.commands.provider_mixin import ProviderCommandsMixin
from nexus_agent.cli.commands.session_mixin import SessionCommandsMixin
from nexus_agent.cli.commands.debug_mixin import DebugCommandsMixin
from nexus_agent.cli.commands.tool_mixin import ToolCommandsMixin
from nexus_agent.cli.commands.misc_mixin import MiscCommandsMixin
from nexus_agent.cli.commands.agent_mixin import AgentCommandsMixin
from nexus_agent.cli.commands.config_mixin import ConfigCommandsMixin
from nexus_agent.cli.commands.interactive_mixin import InteractiveCommandsMixin
from nexus_agent.cli.commands.runtime_mixin import RuntimeCommandsMixin
from nexus_agent.cli.commands.model_mixin import ModelCommandsMixin

SLASH_COMMANDS = [
    {"name": "/help", "description": "Show available commands"},
    {"name": "/plan", "description": "Generate implementation plan (read-only)"},
    {"name": "/build", "description": "Execute implementation plan"},
    {"name": "/orchestrate", "description": "Plan → Approve → Execute → Verify"},
    {"name": "/autonomous", "description": "Full autonomous goal execution"},
    {"name": "/review", "description": "Multi-agent code review on git diff"},
    {"name": "/model", "description": "Manage, show, switch, or unload models"},
    {"name": "/model list", "description": "List available stored models"},
    {"name": "/model switch", "description": "Switch active model to specified name"},
    {"name": "/model unload", "description": "Unload current active model from memory"},
    {"name": "/model add", "description": "Register a new model name and path"},
    {"name": "/model remove", "description": "Deregister a model from database"},
    {"name": "/tools", "description": "Show enabled toolset and allow toggling"},
    {"name": "/skills", "description": "List available skills (project/global)"},
    {"name": "/mode", "description": "Set agent mode (auto|plan|build|review)"},
    {"name": "/effort", "description": "Set reasoning effort (low|medium|high|xhigh|max)"},
    {"name": "/goal", "description": "Set active coding objective"},
    {"name": "/sandbox", "description": "View/set sandbox execution mode"},
    {"name": "/context", "description": "Show context window token breakdown"},
    {"name": "/session", "description": "Show active session info"},
    {"name": "/session list", "description": "List saved sessions in DB"},
    {"name": "/session resume", "description": "Resume session with specified ID"},
    {"name": "/session new", "description": "Start a new session"},
    {"name": "/stats", "description": "Conversation statistics"},
    {"name": "/memory", "description": "Search/edit CLAUDE.md memory files"},
    {"name": "/memory vector stats", "description": "Vector store statistics (count, engine mode, dimensions)"},
    {"name": "/memory vector query", "description": "Semantic similarity search via vector embeddings"},
    {"name": "/memory vector migrate", "description": "Re-embed all existing FTS5 memories into the vector store"},
    {"name": "/memory vector download", "description": "Download ONNX embedding model for higher-quality vectors"},
    {"name": "/reflect", "description": "Critique last assistant response"},
    {"name": "/plugin", "description": "Manage and list loaded plugins"},
    {"name": "/reload-plugins", "description": "Reload plugins from disk"},
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
    {"name": "/background", "description": "Run a prompt in a parallel isolated session"},
    {"name": "/sessions", "description": "Interactive session picker (list, search, resume)"},
    {"name": "/import", "description": "Import a session from a JSON file"},
    {"name": "/fast", "description": "Toggle fast mode on or off"},
    {"name": "/cost", "description": "Show token usage statistics"},
    {"name": "/usage", "description": "Show plan usage limits"},
    {"name": "/extra-usage", "description": "Configure extra usage allowance"},
    {"name": "/status", "description": "Show version, model, account info"},
    {"name": "/theme", "description": "Change color theme"},
    {"name": "/color", "description": "Set the prompt bar color"},
    {"name": "/vim", "description": "Toggle vim editing mode"},
    {"name": "/unload", "description": "Unload the current model from memory"},
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
    {"name": "/update", "description": "Update NexusAgent to the latest version (pip install --upgrade)"},
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
    {"name": "/config show", "description": "Display current configuration"},
    {"name": "/config set", "description": "Set config key to value persistently"},
    {"name": "/config get", "description": "Get active config value"},
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
    {"name": "/connect", "description": "Connect to an LLM provider interactively"},
    {"name": "/disconnect", "description": "Disconnect from current provider, return to local mode"},
    {"name": "/nla", "description": "Natural Language Autoencoder reasoning telemetry & offline learning"},
    {"name": "/explain", "description": "Verbalize underlying concepts and strategies of the last step"},
]


class CommandDispatcherMixin(ProviderCommandsMixin, SessionCommandsMixin, DebugCommandsMixin, ToolCommandsMixin, MiscCommandsMixin, AgentCommandsMixin, ConfigCommandsMixin, InteractiveCommandsMixin, RuntimeCommandsMixin, ModelCommandsMixin):
    """Mixin that provides slash command routing and all /cmd_* handlers."""

    SLASH_COMMANDS = SLASH_COMMANDS






    def _read_line(self, prompt_text: str, hidden: bool = False) -> str | None:
        """Read a line of input with the given prompt. If hidden, mask chars with *."""
        sys.stdout.write("\033[1B")
        sys.stdout.write(prompt_text)
        sys.stdout.flush()
        result = ""
        while True:
            ch = self._read_byte()
            if ch in (b"\r", b"\n"):
                break
            elif ch in (b"\x7f", b"\x08"):
                if result:
                    result = result[:-1]
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
            elif ch == b"\x1b":
                sys.stdout.write("\033[2K\r\033[1A")
                sys.stdout.flush()
                return None
            elif ch == b"\x03":
                raise KeyboardInterrupt
            else:
                try:
                    c = ch.decode("utf-8")
                    if c.isprintable():
                        result += c
                        sys.stdout.write("*" if hidden else c)
                        sys.stdout.flush()
                except (ValueError, UnicodeDecodeError):
                    pass
        sys.stdout.write("\033[2K\r\033[1A")
        sys.stdout.flush()
        return result

    def _handle_slash_command(self, command: str):
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        handlers = {
            "/help":        self._cmd_help,
            "/plan":        self._cmd_plan,
            "/build":       self._cmd_build,
            "/orchestrate": self._cmd_orchestrate,
            "/autonomous":  self._cmd_autonomous,
            "/review":      self._cmd_review,
            "/model":       self._cmd_model,
            "/mode":        self._cmd_mode,
            "/effort":      self._cmd_effort,
            "/goal":        self._cmd_goal,
            "/sandbox":     self._cmd_sandbox,
            "/context":     self._cmd_context,
            "/session":     self._cmd_session,
            "/stats":       self._cmd_stats,
            "/memory":      self._cmd_memory,
            "/reflect":     self._cmd_reflect,
            "/task":        self._cmd_task,
            "/debate":      self._cmd_debate,
            "/verify":      self._cmd_verify,
            "/diff":        self._cmd_diff,
            "/branch":      self._cmd_branch,
            "/commit":      self._cmd_commit,
            "/pr":          self._cmd_pr,
            "/checkpoint":  self._cmd_checkpoint,
            "/checkpoints": self._cmd_checkpoints,
            "/rollback":    self._cmd_rollback,
            "/clear":       self._cmd_clear,
            "/reset":       self._cmd_clear,
            "/new":         self._cmd_clear,
            "/compact":     self._cmd_compact,
            "/fork":        self._cmd_fork,
            "/resume":      self._cmd_resume,
            "/continue":    self._cmd_resume,
            "/rename":      self._cmd_rename,
            "/copy":        self._cmd_copy,
            "/btw":         self._cmd_btw,
            "/add-dir":     self._cmd_add_dir,
            "/rewind":      self._cmd_rewind,
            "/background":  self._cmd_background,
            "/sessions":    self._cmd_sessions,
            "/import":      self._cmd_import,
            "/fast":        self._cmd_fast,
            "/cost":        self._cmd_cost,
            "/usage":       self._cmd_usage,
            "/extra-usage": self._cmd_extra_usage,
            "/status":      self._cmd_status,
            "/theme":       self._cmd_theme,
            "/color":       self._cmd_color,
            "/vim":         self._cmd_vim,
            "/exit":        self._cmd_quit,
            "/desktop":     self._cmd_desktop,
            "/mobile":      self._cmd_mobile,
            "/release-notes": self._cmd_release_notes,
            "/tasks":       self._cmd_tasks,
            "/plugin":        self._cmd_plugin,
            "/reload-plugins": self._cmd_reload_plugins,

            "/pr-comments": self._cmd_pr_comments,
            "/security-review": self._cmd_security_review,
            "/init":        self._cmd_init,
            "/permissions": self._cmd_permissions,
            "/login":       self._cmd_login,
            "/logout":      self._cmd_logout,
            "/keybindings": self._cmd_keybindings,
            "/terminal-setup": self._cmd_terminal_setup,
            "/statusline":  self._cmd_statusline,
            "/privacy-settings": self._cmd_privacy_settings,
            "/upgrade":     self._cmd_upgrade,
            "/update":      self._cmd_update,
            "/feedback":    self._cmd_feedback,
            "/bug":         self._cmd_feedback,
            "/ide":         self._cmd_ide,
            "/chrome":      self._cmd_chrome,
            "/agents":      self._cmd_agents,
            "/hooks":       self._cmd_hooks,
            "/install-github-app": self._cmd_install_github_app,
            "/install-slack-app":  self._cmd_install_slack_app,
            "/remote-control": self._cmd_remote_control,
            "/remote-env":  self._cmd_remote_env,
            "/voice":       self._cmd_voice,
            "/insights":    self._cmd_insights,
            "/passes":      self._cmd_passes,
            "/doctor":      self._cmd_doctor,
            "/search":      self._cmd_search,
            "/index":       self._cmd_index,
            "/browser":     self._cmd_browser,
            "/mcp":         self._cmd_mcp,
            "/skill":       self._cmd_skill,
            "/config":      self._cmd_config,
            "/settings":    self._cmd_config,
            "/{":          self._cmd_display_settings,
            "/devops":      self._cmd_devops,
            "/telemetry":   self._cmd_telemetry,
            "/log":         self._cmd_log,
            "/export":      self._cmd_export,
            "/retry":       self._cmd_retry,
            "/runtime":     self._cmd_runtime,
            "/undo":        self._cmd_undo,
            "/scroll":      self._cmd_scroll,
            "/view":        self._cmd_view,
            "/tui":         self._cmd_tui,
            "/quit":        self._cmd_quit,
            "/unload":      self._cmd_unload,
            "/tools":       self._cmd_tools,
            "/skills":      self._cmd_skill,
            "/connect":     self._cmd_connect,
            "/disconnect":  self._cmd_disconnect,
            "/nla":         self._cmd_nla,
            "/explain":     self._cmd_explain,
        }

        handler = handlers.get(cmd)
        if handler:
            handler(args)
        else:
            # Try plugin commands
            tracker = getattr(self, "plugin_manager", None)
            if tracker:
                found_plugin = False
                for p_name, p_info in tracker.plugins.items():
                    if cmd in p_info.commands:
                        p_info.commands[cmd](self, args)
                        found_plugin = True
                        break
                if found_plugin:
                    self._refresh_status()
                    return

            self.r.error("Unknown command. Type /help")
        self._refresh_status()
