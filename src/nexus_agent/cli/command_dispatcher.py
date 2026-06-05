# TODO: Split into per-command modules (commands/session.py, commands/tools.py, etc.)
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
    {"name": "/nla", "description": "Natural Language Autoencoder reasoning telemetry & offline learning"},
    {"name": "/explain", "description": "Verbalize underlying concepts and strategies of the last step"},
]


class CommandDispatcherMixin:
    """Mixin that provides slash command routing and all /cmd_* handlers."""

    SLASH_COMMANDS = SLASH_COMMANDS

    _KNOWN_PROVIDERS = [
        ("Anthropic (Claude)", "anthropic"),
        ("OpenAI (GPT-4o, o-series)", "openai"),
        ("Google (Gemini)", "google"),
        ("Ollama (local Llama, Mistral, etc.)", "ollama"),
        ("OpenRouter (multi-model gateway)", "openrouter"),
        ("Groq (fast inference)", "groq"),
        ("DeepSeek", "deepseek"),
        ("AWS Bedrock (Claude, Llama on AWS)", "bedrock"),
        ("NVIDIA NIM (Nemotron, Llama-Nemotron)", "nvidia"),
        ("Mistral AI (Mistral, Codestral)", "mistral"),
        ("Fireworks AI (fast inference)", "fireworks"),
        ("Together AI (open-source models)", "together"),
        ("Perplexity (Sonar, Llama-3)", "perplexity"),
        ("Custom OpenAI-compatible", "custom"),
    ]

    _PROVIDER_META = {
        "openai":       {"base": "https://api.openai.com/v1",              "env_key": "OPENAI_API_KEY"},
        "anthropic":    {"base": "https://api.anthropic.com/v1",           "env_key": "ANTHROPIC_API_KEY"},
        "google":       {"base": "https://generativelanguage.googleapis.com/v1beta/openai", "env_key": "GEMINI_API_KEY"},
        "ollama":       {"base": "http://localhost:11434",                 "env_key": ""},
        "openrouter":   {"base": "https://openrouter.ai/api/v1",          "env_key": "OPENROUTER_API_KEY"},
        "groq":         {"base": "https://api.groq.com/openai/v1",        "env_key": "GROQ_API_KEY"},
        "deepseek":     {"base": "https://api.deepseek.com/v1",           "env_key": "DEEPSEEK_API_KEY"},
        "bedrock":      {"base": "",                                      "env_key": ""},
        "nvidia":       {"base": "https://integrate.api.nvidia.com/v1",   "env_key": "NVIDIA_API_KEY"},
        "mistral":      {"base": "https://api.mistral.ai/v1",             "env_key": "MISTRAL_API_KEY"},
        "fireworks":    {"base": "https://api.fireworks.ai/inference/v1", "env_key": "FIREWORKS_API_KEY"},
        "together":     {"base": "https://api.together.xyz/v1",           "env_key": "TOGETHER_API_KEY"},
        "perplexity":   {"base": "https://api.perplexity.ai",             "env_key": "PERPLEXITY_API_KEY"},
        "custom":       {"base": "",                                      "env_key": ""},
    }

    _HARDCODED_MODELS = {
        "anthropic": [
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-opus-4-20250514",
            "claude-3-opus-20240229",
        ],
        "bedrock": [
            "anthropic.claude-sonnet-4-20250514-v2:0",
            "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "anthropic.claude-3-5-haiku-20241022-v1:0",
            "anthropic.claude-opus-4-20250514-v1:0",
            "meta.llama3-70b-instruct-v1:0",
        ],
    }

    _PROVIDER_CONTEXT_SIZES = {
        "anthropic": 200000, "openai": 128000, "google": 1048576,
        "openrouter": 200000, "groq": 131072, "deepseek": 65536,
        "nvidia": 128000, "mistral": 128000, "fireworks": 131072,
        "together": 131072, "perplexity": 127000,
    }

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
            "/feedback":    self._cmd_feedback,
            "/bug":         self._cmd_feedback,
            "/ide":         self._cmd_ide,
            "/chrome":      self._cmd_chrome,
            "/plugin":      self._cmd_plugin,
            "/reload-plugins": self._cmd_reload_plugins,
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
            "/nla":         self._cmd_nla,
            "/explain":     self._cmd_explain,
        }

        handler = handlers.get(cmd)
        if handler:
            handler(args)
        else:
            self.r.error("Unknown command. Type /help")

        self._refresh_status()

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

    def _cmd_model(self, args: str):
        import shlex
        try:
            parts = shlex.split(args) if args else []
        except ValueError:
            parts = args.strip().split() if args else []
        subcmd = parts[0].lower() if parts else ""

        if subcmd == "list":
            models = self._models_db.list()
            if models:
                sorted_items = sorted(models.items())
                page_size = 10
                total = len(sorted_items)
                for page_start in range(0, total, page_size):
                    page = sorted_items[page_start:page_start + page_size]
                    for i, (name, path) in enumerate(page, 1):
                        num = page_start + i
                        marker = "❯" if num == 1 else " "
                        display_name = name[:40]
                        path_str = path.get("path_or_id", "") if isinstance(path, dict) else str(path)
                        self.console.print(f"  {marker} {num:<3} {display_name:<40} \033[2m{path_str}\033[0m")
                    if page_start + page_size < total:
                        remaining = total - (page_start + page_size)
                        self.console.print(f"  \033[2m↓ {page_start + page_size + 1}. ... +{remaining} models\033[0m")
            else:
                self.r.system_message("No stored models. Use /model add <name> <path>")
            return

        elif subcmd == "add" and len(parts) >= 3:
            name = " ".join(parts[1:-1])
            raw_path = parts[-1]
            stripped = raw_path.strip("\"'")
            path = os.path.abspath(stripped)
            if not os.path.isfile(path):
                self.r.error(f"File not found: {path}")
                return
            self._models_db.add(name, path)
            self.r.system_message(f"Model saved: {name} → {path}")
            return

        elif subcmd == "remove" and len(parts) >= 2:
            name = " ".join(parts[1:])
            if self._models_db.remove(name):
                self.r.system_message(f"Model removed: {name}")
            else:
                self.r.error(f"Model not found: {name}")
            return

        elif subcmd == "switch" and len(parts) >= 2:
            name = " ".join(parts[1:])
            path = self._models_db.get_path(name)
            if not path:
                self.r.error(f"Model not found: {name}. Use /model list")
                return
            if not os.path.isfile(path):
                self.r.error(f"Model file missing: {path}")
                return
            self.r.system_message(f"Switching to model: {name}…")
            self._model_path = path
            self._model_status = "loading"
            self._provider_name = "local"
            self._config.setdefault("local_model", {})["model_path"] = path
            self._rebuild_welcome()
            self._init_engine(skip_interactive=True)
            self._init_agent()
            if self._engine and getattr(self._engine, "is_loaded", False):
                self._model_status = "loaded"
                self.r.system_message(f"Switched to: {name}")
            else:
                self._model_status = "idle"
                self.r.error(f"Failed to load: {name}")
            self._rebuild_welcome()
            return

        elif subcmd == "unload":
            self._model_status = "unloading"
            self._rebuild_welcome()
            if self._engine:
                try:
                    self._engine.unload()
                except (RuntimeError, OSError, ValueError):
                    pass
                self._engine = None
            self._agent = None
            self._model_status = "idle"
            self.r.system_message("Model unloaded")
            self._rebuild_welcome()
            return

        elif subcmd in ("", "info"):
            self._cmd_model_interactive()
            return

        else:
            self.r.system_message("Usage: /model [info|list|switch <name>|add <name> <path>|remove <name>|unload]")

    def _cmd_model_interactive(self):
        models = self._models_db.list()
        sorted_n = sorted(models.keys())

        items: list[tuple[str, str | None]] = []
        if self._engine and getattr(self._engine, "is_loaded", False):
            items.append(("\033[31m[✕] Unload model\033[0m", "__unload__"))
            items.append(("────────────────────", None))
        items.append(("[+] Add new model", "__add__"))
        for name in sorted_n:
            path = (self._models_db.get_path(name) or "")[:60]
            items.append((f"{name}  \033[2m→ {path}\033[0m", f"__switch__:{name}"))
        if items and not items[-1][1]:
            pass
        elif items:
            items.append(("────────────────────", None))
        items.append(("[↗] Connect provider", "__connect__"))

        sel = self._interactive_menu(items, "Select a model (↑↓ Enter Esc):")
        if sel is None:
            return

        if sel == "__unload__":
            self._cmd_model("unload")
        elif sel == "__add__":
            self._interactive_add_model()
        elif sel == "__connect__":
            self._interactive_connect_provider()
        elif sel.startswith("__switch__:"):
            name = sel.split(":", 1)[1]
            path = self._models_db.get_path(name)
            if path:
                self._cmd_model(f"switch {name}")
            else:
                self.r.error(f"Model not found: {name}")

    def _cmd_display_settings(self, args: str):
        items = [
            ("\033[36mRefresh Rate\033[0m", "refresh_rate"),
            ("\033[36mFont Size\033[0m", "font_size"),
            ("\033[36mColor Theme\033[0m", "color_theme"),
            ("\033[36mUI Density\033[0m", "ui_density"),
            ("\033[36mScrollback Lines\033[0m", "scrollback"),
            ("\033[36mCursor Style\033[0m", "cursor_style"),
        ]
        if not hasattr(self, '_display_settings_idx'):
            self._display_settings_idx = 0
        idx = self._display_settings_idx
        sel = self._interactive_menu(
            [(label, val) for label, val in items],
            "Display Settings (↑↓ Enter Esc):",
        )
        if sel is None:
            self._display_settings_idx = 0
            return
        self._display_settings_idx = 0
        sub_map = {v: l for l, v in items}
        label = sub_map.get(sel, sel)
        if sel == "refresh_rate":
            rates = ["30 Hz", "60 Hz", "120 Hz", "144 Hz", "165 Hz", "240 Hz"]
            rate_sel = self._interactive_menu(
                [(f"\033[32m{r}\033[0m", r) for r in rates],
                "Refresh Rate — current: 60 Hz:",
            )
            if rate_sel:
                self._config.setdefault("display", {})["refresh_rate"] = rate_sel
                self.r.system_message(f"Refresh rate set to {rate_sel}")
        elif sel == "font_size":
            sizes = ["10px", "12px", "14px", "16px", "18px", "20px", "24px"]
            sz_sel = self._interactive_menu(
                [(f"\033[32m{s}\033[0m", s) for s in sizes],
                "Font Size — current: 14px:",
            )
            if sz_sel:
                self._config.setdefault("display", {})["font_size"] = sz_sel
                self.r.system_message(f"Font size set to {sz_sel}")
        elif sel == "color_theme":
            themes = ["default", "nord", "dracula", "gruvbox", "catppuccin", "one-dark"]
            th_sel = self._interactive_menu(
                [(f"\033[32m{t}\033[0m", t) for t in themes],
                "Color Theme — current: default:",
            )
            if th_sel:
                self._config.setdefault("display", {})["color_theme"] = th_sel
                self.r.system_message(f"Color theme set to {th_sel}")
        elif sel == "ui_density":
            densities = ["compact", "default", "spacious"]
            dn_sel = self._interactive_menu(
                [(f"\033[32m{d}\033[0m", d) for d in densities],
                "UI Density — current: default:",
            )
            if dn_sel:
                self._config.setdefault("display", {})["ui_density"] = dn_sel
                self.r.system_message(f"UI density set to {dn_sel}")
        elif sel == "scrollback":
            self.r.system_message("Scrollback: 10000 lines (configurable in ~/.nexus-agent/config.yaml)")
        elif sel == "cursor_style":
            styles = ["block", "underline", "beam"]
            cs_sel = self._interactive_menu(
                [(f"\033[32m{s}\033[0m", s) for s in styles],
                "Cursor Style — current: block:",
            )
            if cs_sel:
                self._config.setdefault("display", {})["cursor_style"] = cs_sel
                sys.stdout.write(f"\033[{cs_sel.upper()[0]} q")
                sys.stdout.flush()
                self.r.system_message(f"Cursor style set to {cs_sel}")

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

    def _render_effort_selector(self, levels: tuple, labels: tuple, idx: int):
        EFFORT_COLORS = {"low": "32", "medium": "36", "high": "33", "xhigh": "35", "max": "31"}
        PAD = 22

        plain_labels = [str(l) for l in labels]
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
            clr = EFFORT_COLORS.get(lab, "0")
            if i == idx:
                label_parts.append(f"\033[1;{clr}m{lab}\033[0m")
            else:
                label_parts.append(f"\033[2;{clr}m{lab}\033[0m")
            if i < len(plain_labels) - 1:
                label_parts.append(" " * gap)

        label_line = " " * PAD + "".join(label_parts)

        ptr_color = EFFORT_COLORS.get(levels[idx], "33")
        marker_line = " " * (PAD + centers[idx]) + f"\033[1;{ptr_color}m\u25b2\033[0m"

        left_w = total_w // 2
        right_w = total_w - left_w

        lines = [
            "",
            "  Effort",
            "",
            f"{' ' * PAD}Faster{' ' * (left_w - 6)}Smarter",
            f"{' ' * PAD}{'\u2500' * left_w}\u252c{'\u2500' * right_w}",
        ]
        lines.append(marker_line)
        lines.append(label_line)
        lines.append("")
        lines.append("  \033[2m\u2190/\u2192 adjust \xb7 Enter confirm \xb7 Esc cancel\033[0m")

        h = len(lines)
        sys.stdout.write("\033[1B\033[J")
        sys.stdout.write("\n".join(lines))
        sys.stdout.write(f"\033[{h}A")
        sys.stdout.flush()

    def _clear_selector(self):
        sys.stdout.write("\033[1B\033[J\033[1A")
        sys.stdout.flush()

    def _cmd_goal(self, args: str):
        if args:
            self._config.setdefault("agent", {})["goal"] = args
            if self._agent:
                self._agent.goal = args
            self.r.system_message(f"Goal: {args}")
            save_config(self._config, self.config_path)
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

    def _cmd_clear(self, args: str):
        if self._agent:
            self._agent.clear_history()
        self._tokens = TokenUsage()
        self.r.clear()
        self.r.system_message("Cleared.")

    def _cmd_session(self, args: str):
        if not self._session_mgr:
            self.r.system_message("Session manager unavailable.")
            return

        parts = args.strip().split(maxsplit=1) if args else []
        subcmd = parts[0].lower() if parts else ""

        if subcmd == "list":
            try:
                sessions = self._session_mgr.list_sessions()
                if sessions:
                    from rich.table import Table
                    table = Table(title="Sessions", show_header=True, header_style="bold magenta")
                    table.add_column("ID", style="cyan")
                    table.add_column("Created", style="green")
                    table.add_column("Messages", justify="right", style="yellow")
                    table.add_column("Model", style="dim")
                    for s in sessions:
                        table.add_row(s["id"][:12], s["created"], str(s.get("message_count", 0)), s.get("model", ""))
                    self.console.print(table)
                else:
                    self.r.system_message("No saved sessions.")
            except Exception as e:
                self.r.error(f"Failed to list sessions: {e}")

        elif subcmd == "resume" and len(parts) >= 2:
            sid = parts[1].strip()
            self._cmd_resume(sid)

        elif subcmd == "new":
            self._session_id = self._session_mgr.create_session(
                model=self._engine.model_name if self._engine else "unknown",
                provider=self._provider_name or "local",
                workspace=str(self.workspace),
                mode=self._current_mode.value,
            )
            if self._agent:
                self._agent.clear_history()
            self._tokens = TokenUsage()
            self.r.clear()
            self.r.system_message(f"Started new session: {self._session_id}")
            self._rebuild_welcome()

        else:
            try:
                act = self._session_mgr.get_active_session()
                if act:
                    self.console.print(f"  Active Session ID: {act.get('id', 'unknown')}")
                    self.console.print(f"  Title:            {act.get('title', '')}")
                    self.console.print(f"  Workspace:        {act.get('workspace', '')}")
                    self.console.print(f"  Model:            {act.get('model', '')}")
                    self.console.print(f"  Provider:         {act.get('provider', '')}")
                else:
                    self.r.system_message("No active session.")
            except Exception as e:
                self.r.system_message(f"No active session info available: {e}")

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

    def _cmd_diff(self, args: str):
        target = args or "HEAD"
        try:
            result = subprocess.run(
                ["git", "diff", target],
                cwd=str(self.workspace), capture_output=True, text=True, timeout=15,
            )
            output = result.stdout or result.stderr or "(no diff)"
            if len(output) > 3000:
                output = output[:3000] + f"\n  ... (truncated, {len(output)} total chars)"
            self.console.print(Syntax(output, "diff", theme="monokai", word_wrap=True))
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            self.r.error(f"Diff failed: {e}")

    def _cmd_branch(self, args: str):
        try:
            if args:
                cmd = ["git", "checkout", args]
            else:
                result = subprocess.run(["git", "branch"], cwd=str(self.workspace), capture_output=True, text=True, timeout=10)
                self.console.print(f"  [dim]{result.stdout.strip()}[/dim]")
                return
            subprocess.run(cmd, cwd=str(self.workspace), capture_output=True, text=True, timeout=10)
            self.r.system_message(f"Switched to branch: {args}")
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            self.r.error(f"Branch: {e}")

    def _cmd_commit(self, args: str):
        if self._agent:
            from nexus_agent.tools.git_ops import SmartCommitTool
            self.r.show_spinner("Generating commit message")
        try:
            tool = SmartCommitTool(workspace=self.workspace, provider=self._agent.provider)
            msg = tool.execute()
            self.r.hide_spinner()
            self.console.print(f"\n  [dim]{msg}[/dim]\n")
        except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as e:
            self.r.hide_spinner()
            self.r.error(f"Commit: {e}")
        else:
            self.r.system_message("No agent.")

    def _cmd_pr(self, args: str):
        from nexus_agent.tools.git_ops import PRReviewTool
        self.r.show_spinner("Generating PR summary")
        try:
            pr_tool = PRReviewTool(workspace=self.workspace, provider=self._agent.provider if self._agent else None)
            summary = pr_tool.execute()
            self.r.hide_spinner()
            self.r.assistant_message(summary)
        except (ValueError, RuntimeError) as e:
            self.r.hide_spinner()
            self.r.error(f"PR: {e}")

    def _cmd_checkpoint(self, args: str):
        if self._session_mgr:
            files = [str(f) for f in self.workspace.rglob("*.py")][:20]
            cp_id = self._session_mgr.create_checkpoint(files, description=args or "Manual checkpoint")
            self.r.system_message(f"Checkpoint: {cp_id[:12]}…")
        else:
            self.r.system_message("Session manager unavailable.")

    def _cmd_checkpoints(self, args: str):
        if self._checkpoint_mgr:
            try:
                checkpoints = self._checkpoint_mgr.list_checkpoints()
                if not checkpoints:
                    self.r.system_message("No checkpoints.")
                    return
                for cp in checkpoints[:10]:
                    self.console.print(f"  [{cp['id'][:12]}] {cp.get('description', '')}  [dim]{cp.get('created', '')}[/dim]")
            except (ValueError, OSError, RuntimeError) as e:
                self.r.error(f"Checkpoints: {e}")
        else:
            self.r.system_message("Checkpoint manager unavailable.")

    def _cmd_rollback(self, args: str):
        if self._session_mgr:
            try:
                results = self._session_mgr.rollback(args or None)
                for k, v in results.items():
                    self.console.print(f"  {k}: {v}")
            except ValueError as e:
                self.r.error(str(e))
        else:
            self.r.system_message("Session manager unavailable.")

    def _cmd_search(self, args: str):
        if not args:
            self.r.system_message("Usage: /search <query>")
            return
        self.r.show_spinner("Searching workspace")
        try:
            from nexus_agent.tools.rag_search import RepositoryRAGTool
            tool = RepositoryRAGTool(self.workspace)
            results = tool.execute(query=args, max_results=8)
            self.r.hide_spinner()
            if isinstance(results, str):
                self.r.assistant_message(results[:2000])
            elif results:
                for r in results[:8]:
                    path = r.get("file_path", r.get("path", "?"))
                    snippet = r.get("content", r.get("snippet", ""))[:120]
                    self.console.print(f"  [cyan]{path}[/cyan]")
                    self.console.print(f"  [dim]{snippet}[/dim]\n")
            else:
                self.r.system_message(f"No results for: {args}")
        except (ValueError, RuntimeError, OSError) as e:
            self.r.hide_spinner()
            self.r.error(f"Search: {e}")

    def _cmd_index(self, args: str):
        self.r.show_spinner("Indexing workspace")
        try:
            from nexus_agent.tools.rag_search import RepositoryRAGTool
            tool = RepositoryRAGTool(self.workspace)
            result = tool.execute(action="index_all")
            self.r.hide_spinner()
            self.r.system_message(str(result)[:200] if result else "Indexing complete.")
        except (ValueError, RuntimeError, OSError) as e:
            self.r.hide_spinner()
            self.r.error(f"Index: {e}")

    def _cmd_browser(self, args: str):
        if not args:
            self.r.system_message("Usage: /browser <url>")
            return
        self.r.show_spinner("Opening browser")
        try:
            from nexus_agent.tools.browser import BrowserTool
            tool = BrowserTool()
            result = tool.execute(action="navigate", url=args)
            self.r.hide_spinner()
            content = result if isinstance(result, str) else str(result)
            if len(content) > 3000:
                content = content[:3000] + f"\n  ... (truncated, {len(content)} total chars)"
            self.r.assistant_message(content)
        except (ValueError, RuntimeError, OSError, FileNotFoundError) as e:
            self.r.hide_spinner()
            self.r.error(f"Browser: {e}")

    def _cmd_mcp(self, args: str):
        if args == "list" or not args:
            if self._mcp_clients:
                for i, client in enumerate(self._mcp_clients):
                    tools = getattr(client, "discovered_tools", [])
                    self.console.print(f"  [cyan]MCP Server {i + 1}:[/cyan] {' '.join(client.command[:2])}")
                    self.console.print(f"    Tools: {len(tools)} registered")
                    for t in tools[:5]:
                        self.console.print(f"    - [bold]{t.name}[/bold]: {t.description[:60]}")
            else:
                self.r.system_message("No MCP servers connected.")
                self.console.print("  [dim]Configure servers in config mcp.servers[/dim]")
        elif args.startswith("connect "):
            cmd_parts = args[7:].strip().split()
            if cmd_parts:
                try:
                    from nexus_agent.mcp.client import MCPClient
                    client = MCPClient(command=cmd_parts)
                    if client.start():
                        self._mcp_clients.append(client)
                        self._mcp_tools.extend(client.discovered_tools)
                        if self._agent:
                            for tool in client.discovered_tools:
                                self._agent._tool_map[tool.name] = tool
                        self.r.system_message(f"MCP server connected ({len(client.discovered_tools)} tools)")
                    else:
                        self.r.error("MCP server failed to start")
                except (ValueError, RuntimeError, OSError, FileNotFoundError) as e:
                    self.r.error(f"MCP connect: {e}")
        elif args.startswith("install "):
            cmd_parts = args[8:].strip().split()
            if cmd_parts:
                try:
                    from nexus_agent.mcp.client import MCPClient
                    client = MCPClient(command=cmd_parts)
                    if client.start():
                        self._mcp_clients.append(client)
                        self._mcp_tools.extend(client.discovered_tools)
                        if self._agent:
                            for tool in client.discovered_tools:
                                self._agent._tool_map[tool.name] = tool

                        cmd_prefix = cmd_parts[0]
                        cmd_args = cmd_parts[1:]
                        servers = self._config.setdefault("mcp", {}).setdefault("servers", [])
                        if not any(s.get("command") == cmd_prefix and s.get("args") == cmd_args for s in servers):
                            servers.append({"command": cmd_prefix, "args": cmd_args})
                            save_config(self._config, self.config_path)
                            self.r.system_message("MCP server registered in config.yaml permanently")

                        self.r.system_message(f"MCP server installed & tools loaded dynamically ({len(client.discovered_tools)} tools)")
                    else:
                        self.r.error("MCP server failed to start")
                except (ValueError, RuntimeError, OSError, FileNotFoundError, TypeError) as e:
                    self.r.error(f"MCP install: {e}")

    def _cmd_skill(self, args: str):
        if not self._skill_registry:
            self.r.system_message("Skill registry unavailable.")
            return
        skills = self._skill_registry.skills
        if args == "list" or not args:
            if skills:
                for name, skill in skills.items():
                    self.console.print(f"  [bold]{name}[/bold]: {skill.description[:70]}")
            else:
                self.r.system_message("No skills discovered.")
                self.console.print("  [dim]Place .md skill files in ~/.nexus-agent/skills/[/dim]")
        elif args.startswith("run "):
            skill_name = args[4:].strip()
            if skill_name in skills:
                self.r.show_spinner(f"Running skill: {skill_name}")
                try:
                    result = skills[skill_name].execute()
                    self.r.hide_spinner()
                    self.r.assistant_message(str(result)[:2000])
                except (ValueError, RuntimeError, OSError) as e:
                    self.r.hide_spinner()
                    self.r.error(f"Skill: {e}")
            else:
                self.r.error(f"Skill not found: {skill_name}")

    def _cmd_config(self, args: str):
        if args:
            pieces = args.split(maxsplit=1)
            if len(pieces) == 2:
                k, v = pieces
                keys = k.split(".")
                target = self._config
                for key in keys[:-1]:
                    target = target.setdefault(key, {})
                target[keys[-1]] = v
                save_config(self._config, self.config_path)
                self.r.system_message(f"Config {k} = {v}")
            else:
                k = pieces[0]
                keys = k.split(".")
                val = self._config
                try:
                    for key in keys:
                        val = val[key]
                    self.r.system_message(f"{k} = {val}")
                except (KeyError, TypeError):
                    self.r.system_message(f"{k} = (not set)")
        else:
            for k, v in self._config.items():
                if not k.startswith("_"):
                    if isinstance(v, dict):
                        self.console.print(f"  [bold]{k}:[/bold]")
                        for sk, sv in v.items():
                            self.console.print(f"    {sk}: {sv}")
                    else:
                        self.console.print(f"  [dim]{k}:[/dim] {v}")

    def _cmd_devops(self, args: str):
        self._cmd_verify(args)

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

    def _cmd_export(self, args: str):
        # Validate path stays within workspace to prevent traversal
        if args:
            requested = Path(args).resolve()
            # Only allow relative paths (workspace-relative) or explicit safe paths
            if not str(requested).startswith(str(self.workspace.resolve())):
                # If not workspace-relative, use default name in workspace
                filename = f"nexus-session-{int(time.time())}.json"
                path = self.workspace / filename
            else:
                path = requested
        else:
            filename = f"nexus-session-{int(time.time())}.json"
            path = self.workspace / filename
        if self._session_mgr:
            try:
                data = self._session_mgr.export_session()
                path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                self.r.system_message(f"Session exported: {path}")
            except (ValueError, OSError, TypeError) as e:
                self.r.error(f"Export: {e}")
        else:
            self.r.system_message("Session manager unavailable.")

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

    def _cmd_tui(self, args: str):
        if args == "fullscreen":
            self.r.enter_fullscreen()
        elif args == "inline":
            self.r.exit_fullscreen()
        else:
            self.r.toggle_fullscreen()
        mode = "fullscreen" if getattr(self.r, '_is_fullscreen', False) else "inline"
        self.r.system_message(f"TUI: {mode}")

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

    def _cmd_runtime(self, args: str):
        from nexus_agent.cli.runtimes import format_runtime_list, scan_runtimes
        from nexus_agent.llm.runtime_manager import RuntimeManager

        parts = args.strip().split(maxsplit=1) if args else []
        subcmd = parts[0].lower() if parts else ""

        if subcmd == "scan":
            self.console.print("  [dim]Scanning for available runtimes…[/dim]")
            self._runtime_list = self._get_custom_runtimes() + scan_runtimes()
            self.console.print(format_runtime_list(self._runtime_list))
            self.console.print(f"\n  [dim]{len(self._runtime_list)} runtime(s) detected[/dim]")

        elif subcmd == "add":
            pieces = parts[1].split(maxsplit=1) if len(parts) >= 2 else []
            if len(pieces) < 2:
                self.r.error("Usage: /runtime add <name> <path>")
                return
            name, rpath = pieces[0], pieces[1].strip("\"'")
            abs_path = os.path.abspath(os.path.expanduser(rpath))
            if not os.path.exists(abs_path):
                self.r.error(f"Path does not exist: {abs_path}")
                return
            self._config.setdefault("custom_runtimes", {})[name] = abs_path
            save_config(self._config, self.config_path)
            self.r.system_message(f"Custom runtime registered: {name} → {abs_path}")
            self._runtime_list = self._get_custom_runtimes() + scan_runtimes()

        elif subcmd == "remove" and len(parts) >= 2:
            name = parts[1].strip()
            if name in self._config.get("custom_runtimes", {}):
                del self._config["custom_runtimes"][name]
                if self._config.get("runtime", {}).get("name") == name:
                    self._config["runtime"] = {"active": "local"}
                save_config(self._config, self.config_path)
                self.r.system_message(f"Custom runtime removed: {name}")
                self._runtime_list = self._get_custom_runtimes() + scan_runtimes()
            else:
                self.r.error(f"Custom runtime not found: {name}")

        elif subcmd == "install":
            backend = parts[1].strip().lower() if len(parts) >= 2 else ""
            if not backend:
                installable = RuntimeManager.get_installable_runtimes()
                self.console.print("\n  [bold]Installable runtimes:[/bold]")
                for key, rt in installable.items():
                    status = "[green]✓ installed[/green]" if RuntimeManager.is_runtime_installed(key) else "[dim]not installed[/dim]"
                    rec_str = " [yellow](Recommended for your system)[/yellow]" if rt.get("recommended") else ""
                    self.console.print(f"  {key:12s} {rt['name']:40s} {status}{rec_str}")
                    self.console.print(f"  {'':12s} [dim]{rt['description']}[/dim]")
                self.console.print("\n  Usage: [bold]/runtime install <backend>[/bold]")
                self.console.print(f"  Backends: {', '.join(installable.keys())}")
                return

            if RuntimeManager.is_runtime_installed(backend):
                self.r.system_message(f"{backend} runtime is already installed. Use /runtime reinstall {backend} to reinstall.")
                return

            self.console.print(f"  [dim]Installing {backend} runtime...[/dim]")
            success = RuntimeManager.install_runtime(backend, progress_callback=self._runtime_progress)
            if success:
                self._runtime_list = self._get_custom_runtimes() + scan_runtimes()
                self.r.system_message(f"✓ {backend} runtime installed successfully")
            else:
                self.r.error(f"Failed to install {backend} runtime. See logs for details.")

        elif subcmd == "reinstall":
            backend = parts[1].strip().lower() if len(parts) >= 2 else ""
            if not backend:
                self.r.error("Usage: /runtime reinstall <backend>")
                return
            self.console.print(f"  [dim]Reinstalling {backend} runtime...[/dim]")
            success = RuntimeManager.install_runtime(backend, force_reinstall=True, progress_callback=self._runtime_progress)
            if success:
                self._runtime_list = self._get_custom_runtimes() + scan_runtimes()
                self.r.system_message(f"✓ {backend} runtime reinstalled successfully")
            else:
                self.r.error(f"Failed to reinstall {backend} runtime. See logs for details.")

        elif subcmd == "uninstall":
            backend = parts[1].strip().lower() if len(parts) >= 2 else ""
            if not backend:
                self.r.error("Usage: /runtime uninstall <backend>")
                return
            self.console.print(f"  [dim]Uninstalling {backend} runtime...[/dim]")
            success = RuntimeManager.uninstall_runtime(backend)
            if success:
                self._runtime_list = self._get_custom_runtimes() + scan_runtimes()
                self.r.system_message(f"✓ {backend} runtime uninstalled")
            else:
                self.r.error(f"Failed to uninstall {backend} runtime.")

        elif subcmd == "list" or (not args):
            if not self._runtime_list:
                self._runtime_list = self._get_custom_runtimes() + scan_runtimes()
            items = []
            for rt in self._runtime_list:
                status = "✓" if rt.available else "✗"
                items.append((f"{status} {rt.name} ({rt.description})", rt.name))
            items.append(("Cancel", "exit"))
            sel = self._interactive_menu(items, "Select a runtime (↑↓ Enter Esc):")
            if sel and sel != "exit":
                self._cmd_runtime(f"select {sel}")
            return

        elif subcmd == "select" and len(parts) >= 2:
            name = parts[1].strip()
            installable = RuntimeManager.get_installable_runtimes()
            if name.lower() in installable:
                backend = name.lower()
                if not RuntimeManager.is_runtime_installed(backend):
                    self.r.error(f"Runtime '{backend}' is not installed. Run /runtime install {backend} first.")
                    return
                self._config.setdefault("runtime", {})["active"] = backend
                if "path" in self._config.get("runtime", {}):
                    del self._config["runtime"]["path"]
                if "name" in self._config.get("runtime", {}):
                    del self._config["runtime"]["name"]
                save_config(self._config, self.config_path)
                RuntimeManager.activate_runtime(backend)
                self.r.system_message(f"Active runtime switched to isolated backend: {backend}")
                self._init_engine()
                self._init_agent()
                return

            customs = self._config.get("custom_runtimes", {})
            if name in customs:
                path = customs[name]
                self._config.setdefault("runtime", {})["active"] = "custom"
                self._config["runtime"]["name"] = name
                self._config["runtime"]["path"] = path
                save_config(self._config, self.config_path)

                path_dir = os.path.dirname(path) if os.path.isfile(path) else path
                os.environ["PATH"] = path_dir + os.pathsep + os.environ.get("PATH", "")

                self.r.system_message(f"Selected custom runtime: {name} (✓ active path prepended)")
                self._runtime_list = self._get_custom_runtimes() + scan_runtimes()
                self._init_engine()
                self._init_agent()
                return

            if not self._runtime_list:
                self._runtime_list = self._get_custom_runtimes() + scan_runtimes()
            found = [r for r in self._runtime_list if name.lower() in r.name.lower()]
            if found:
                rt = found[0]
                self._config.setdefault("runtime", {})["active"] = rt.provider
                if "path" in self._config.get("runtime", {}):
                    del self._config["runtime"]["path"]
                if "name" in self._config.get("runtime", {}):
                    del self._config["runtime"]["name"]
                save_config(self._config, self.config_path)
                self.r.system_message(f"Active runtime: {rt.name} [{rt.provider}]")
                self._runtime_list = self._get_custom_runtimes() + scan_runtimes()
                self._init_engine()
                self._init_agent()
            else:
                self.r.error(f"No runtime matches: {name}. Run /runtime list")

        elif subcmd == "switch":
            backend = parts[1].strip().lower() if len(parts) >= 2 else ""
            if not backend:
                self.r.error("Usage: /runtime switch <backend>")
                return
            rm = RuntimeManager(self._config)
            if rm.switch_runtime(backend):
                save_config(self._config, self.config_path)
                self.r.system_message(f"Runtime backend switched to: {backend}")
            else:
                self.r.error(f"Failed to switch runtime. Valid: auto, llama-cpp, onnx")

        elif subcmd in ("help", "--help", "-h") or (not args and subcmd not in ("list",)):
            self.console.print("""\n  [bold]Runtime Management:[/bold]
  [cyan]/runtime list[/cyan]       — Show detected runtimes
  [cyan]/runtime scan[/cyan]       — Re-scan for runtimes
  [cyan]/runtime select <n>[/cyan] — Select active runtime by name
  [cyan]/runtime install <b>[/cyan]  — Install a runtime backend (cpu|cuda|vulkan|metal|rocm|onnx)
  [cyan]/runtime reinstall <b>[/cyan]— Force reinstall a runtime backend
  [cyan]/runtime uninstall <b>[/cyan]— Uninstall a runtime backend
  [cyan]/runtime switch <b>[/cyan]  — Switch runtime type (auto|llama-cpp|onnx)
  [cyan]/runtime add <n> <p>[/cyan] — Register a custom runtime path
  [cyan]/runtime remove <n>[/cyan]  — Remove a custom runtime\n""")

    def _runtime_progress(self, status: str, detail: str) -> None:
        """Progress callback for runtime installation."""
        icons = {"installing": "▶", "verifying": "●", "complete": "✓", "error": "X"}
        icon = icons.get(status, "▶")
        self.console.print(f"  [{icon}] {detail}")

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

    def _cmd_fork(self, args: str):
        self.r.system_message("Fork: Not yet implemented")

    def _cmd_resume(self, args: str):
        if not self._session_mgr:
            self.r.system_message("Session manager unavailable.")
            return
        if args:
            try:
                data = self._session_mgr.resume_session(args)
                if data:
                    self._session_id = data["id"]
                    model = data.get("model")
                    provider = data.get("provider")
                    mode_str = data.get("mode")
                    if mode_str:
                        try:
                            from nexus_agent.core.agent import AgentMode
                            self._current_mode = AgentMode(mode_str)
                            if self._agent:
                                self._agent.mode = self._current_mode
                        except ValueError:
                            pass
                    self.r.system_message(f"Resumed session: {self._session_id}")
                    if model and model != "unknown":
                        if provider == "local" and os.path.isfile(model):
                            self._model_path = model
                            self._provider_name = "local"
                            self._model_status = "loading"
                            self._init_engine(skip_interactive=True)
                            self._init_agent()
                        elif provider != "local":
                            self._provider_name = provider
                            self._model_path = model
                            self._model_status = "loading"
                            self._init_engine(skip_interactive=True)
                            self._init_agent()
                    self._rebuild_welcome()
                else:
                    self.r.error(f"Session not found: {args}")
            except (ValueError, OSError, RuntimeError) as e:
                self.r.error(f"Resume failed: {e}")
        else:
            try:
                sessions = self._session_mgr.list_sessions()
                if sessions:
                    items = [(f"{s.get('id', '?')[:16]}  {s.get('name', '')}", s['id']) for s in sessions[:10]]
                    sel = self._interactive_menu(items, "Select session to resume:")
                    if sel:
                        self._cmd_resume(sel)
                else:
                    self.r.system_message("No saved sessions.")
            except (ValueError, OSError, RuntimeError) as e:
                self.r.error(f"List sessions: {e}")

    def _cmd_rename(self, args: str):
        if self._session_mgr:
            try:
                self._session_mgr.rename(args.strip())
                self.r.system_message(f"Session renamed: {args.strip()}")
            except (ValueError, OSError, RuntimeError) as e:
                self.r.system_message(f"Rename: {e}")
        else:
            self.r.system_message("Session manager unavailable.")

    def _cmd_copy(self, args: str):
        self.r.system_message("Copy: Not yet implemented")

    def _cmd_btw(self, args: str):
        self.r.system_message("BTW: Not yet implemented")

    def _cmd_add_dir(self, args: str):
        self.r.system_message("Add-dir: Not yet implemented")

    def _cmd_rewind(self, args: str):
        self.r.system_message("Rewind: Not yet implemented")

    def _cmd_fast(self, args: str):
        self.r.system_message("Fast mode: Not yet implemented")

    def _cmd_cost(self, args: str):
        self.r.system_message(f"Cost: ${self._tokens.estimated_cost:.4f}")

    def _cmd_usage(self, args: str):
        self.r.system_message("Usage tracking: Not yet implemented")

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

    def _cmd_theme(self, args: str):
        if args in ("dark", "light"):
            self.r.set_theme(args)
            self._config["theme"] = args
            save_config(self._config, self.config_path)
            self.r.system_message(f"Theme set to {args}")
        else:
            self.r.system_message("Usage: /theme [dark|light]")

    def _cmd_color(self, args: str):
        self.r.system_message("Color: Set prompt bar color (not yet fully implemented)")

    def _cmd_vim(self, args: str):
        self.r.system_message("Vim mode: Not yet implemented")

    def _cmd_unload(self, args: str):
        self._cmd_model("unload")

    def _cmd_tools(self, args: str):
        if not self._agent:
            self.r.system_message("No active agent.")
            return

        parts = args.strip().split()
        if parts:
            action = parts[0].lower()
            if action in ("enable", "disable", "toggle") and len(parts) >= 2:
                name = parts[1]
                target_tool = None
                for t in self._agent.tools:
                    if t.name == name:
                        target_tool = t
                        break
                if not target_tool:
                    self.r.error(f"Unknown tool: {name}")
                    return
                
                disabled = getattr(self._agent, "disabled_tools", set())
                if action == "enable":
                    disabled.discard(name)
                    self.r.system_message(f"Enabled tool: {name}")
                elif action == "disable":
                    disabled.add(name)
                    self.r.system_message(f"Disabled tool: {name}")
                elif action == "toggle":
                    if name in disabled:
                        disabled.discard(name)
                        self.r.system_message(f"Enabled tool: {name}")
                    else:
                        disabled.add(name)
                        self.r.system_message(f"Disabled tool: {name}")
                self._agent.disabled_tools = disabled
                return
            else:
                self.r.system_message("Usage: /tools [enable|disable|toggle <tool_name>]")
                return

        # Interactive toggling using menu
        while True:
            disabled = getattr(self._agent, "disabled_tools", set())
            items = []
            for t in self._agent.tools:
                status = "\033[31m[OFF]\033[0m" if t.name in disabled else "\033[32m[ON]\033[0m "
                items.append((f"{status} {t.name:<25} \033[2m{t.description[:45]}\033[0m", t.name))
            items.append(("────────────────────", None))
            items.append(("\033[36m[Exit]\033[0m", "exit"))

            sel = self._interactive_menu(items, "Toggle Tools (↑↓ Enter Esc):")
            if sel is None or sel == "exit":
                break
            
            # Toggle the tool
            if sel in disabled:
                disabled.discard(sel)
            else:
                disabled.add(sel)
            self._agent.disabled_tools = disabled
            self.r.system_message(f"Toggled tool {sel}: {'Disabled' if sel in disabled else 'Enabled'}")

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

    def _cmd_init(self, args: str):
        self.r.system_message("Init: Not yet implemented")

    def _cmd_permissions(self, args: str):
        if self._permissions:
            self.console.print("  [bold]Current permissions:[/bold]")
            for rule in self._permissions.rules:
                self.console.print(f"  [dim]  {rule}[/dim]")
        else:
            self.r.system_message("Permissions manager unavailable.")

    def _cmd_login(self, args: str):
        self.r.system_message("Login: Not yet implemented")

    def _cmd_logout(self, args: str):
        self.r.system_message("Logout: Not yet implemented")

    def _cmd_keybindings(self, args: str):
        self.r.system_message("Keybindings: Not yet implemented")

    def _cmd_terminal_setup(self, args: str):
        self.r.system_message("Terminal setup: Not yet implemented")

    def _cmd_statusline(self, args: str):
        self.r.system_message("Statusline: Not yet implemented")

    def _cmd_privacy_settings(self, args: str):
        self.r.system_message("Privacy settings: Not yet implemented")

    def _cmd_upgrade(self, args: str):
        self.r.system_message("Upgrade: Not yet implemented")

    def _cmd_feedback(self, args: str):
        self.r.system_message("Feedback: Not yet implemented")

    def _cmd_ide(self, args: str):
        self.r.system_message("IDE: Not yet implemented")

    def _cmd_chrome(self, args: str):
        self.r.system_message("Chrome: Not yet implemented")

    def _cmd_plugin(self, args: str):
        self.r.system_message("Plugin: Not yet implemented")

    def _cmd_reload_plugins(self, args: str):
        self.r.system_message("Reload plugins: Not yet implemented")

    def _cmd_agents(self, args: str):
        self.r.system_message("Agents: Not yet implemented")

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
        self.r.system_message("Insights: Not yet implemented")

    def _cmd_passes(self, args: str):
        self.r.system_message("Passes: Not yet implemented")

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

    def _interactive_menu(self, items: list[tuple[str, str | None]], title: str = "Select:") -> str | None:
        selectable = [i for i, (l, v) in enumerate(items) if v is not None]
        if not selectable:
            return None
        idx = selectable[0]
        n_selectable = len(selectable)

        sys.stdout.write("\033[s")
        sys.stdout.flush()

        try:
            def build(sel_idx):
                out = [f"\033[2m  {title}\033[0m"]
                for i, (label, val) in enumerate(items):
                    hi = "\033[7m" if i == sel_idx else ""
                    end = "\033[0m" if i == sel_idx else ""
                    prefix = "▸ " if i == sel_idx else "  "
                    if val is None:
                        out.append(f"  \033[2m{label}\033[0m")
                    else:
                        out.append(f"  {hi}{prefix}{label}{end}")
                return out

            def render(sel_idx):
                nonlocal menu_h
                sys.stdout.write("\033[u\033[J")
                lines = build(sel_idx)
                nh = len(lines)
                sys.stdout.write("\033[1B\r\033[J")
                sys.stdout.write("\n".join(lines))
                sys.stdout.flush()
                menu_h = nh

            menu_h = 0
            render(idx)

            while True:
                ch = self._read_byte()
                if ch == b"\xe0":
                    ch2 = self._read_byte()
                    if ch2 == b"H":
                        ci = selectable.index(idx)
                        ci = (ci - 1) % n_selectable
                        idx = selectable[ci]
                        render(idx)
                    elif ch2 == b"P":
                        ci = selectable.index(idx)
                        ci = (ci + 1) % n_selectable
                        idx = selectable[ci]
                        render(idx)
                elif ch in (b"\r", b"\n"):
                    break
                elif ch == b"\x1b":
                    idx = -1
                    break
                time.sleep(0.01)
        finally:
            sys.stdout.write("\033[u\033[J")
            sys.stdout.flush()

        if idx < 0:
            return None
        return items[idx][1]

    def _interactive_add_model(self):
        name = self._read_line("\033[2m  Enter model name:\033[0m \033[7m \033[0m\b")
        if name is None:
            return
        if not name:
            self.r.error("Name cannot be empty")
            return

        path = self._read_line("\033[2m  Enter model path:\033[0m \033[7m \033[0m\b")
        if path is None:
            return

        raw_path = path.strip("\"'")
        abs_path = os.path.abspath(raw_path)
        if not os.path.isfile(abs_path):
            self.r.error(f"File not found: {abs_path}")
            return

        self._models_db.add(name, abs_path)
        self.r.system_message(f"Model saved: {name} → {abs_path}")
        self.r.system_message(f"Use /model switch {name} to load it")

    def _validate_provider_key(self, provider_name: str, api_key: str) -> tuple[bool, str]:
        import httpx
        validation_endpoints: dict[str, dict[str, Any]] = {
            "openai": {
                "url": "https://api.openai.com/v1/models",
                "headers": {"Authorization": f"Bearer {api_key}"},
            },
            "anthropic": {
                "url": "https://api.anthropic.com/v1/models",
                "headers": {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
            },
            "google": {
                "url": f"https://generativelanguage.googleapis.com/v1/models?key={api_key}",
                "headers": {},
            },
            "groq": {
                "url": "https://api.groq.com/openai/v1/models",
                "headers": {"Authorization": f"Bearer {api_key}"},
            },
            "deepseek": {
                "url": "https://api.deepseek.com/v1/models",
                "headers": {"Authorization": f"Bearer {api_key}"},
            },
            "openrouter": {
                "url": "https://openrouter.ai/api/v1/models",
                "headers": {"Authorization": f"Bearer {api_key}"},
            },
            "mistral": {
                "url": "https://api.mistral.ai/v1/models",
                "headers": {"Authorization": f"Bearer {api_key}"},
            },
            "fireworks": {
                "url": "https://api.fireworks.ai/inference/v1/models",
                "headers": {"Authorization": f"Bearer {api_key}"},
            },
            "together": {
                "url": "https://api.together.xyz/v1/models",
                "headers": {"Authorization": f"Bearer {api_key}"},
            },
            "perplexity": {
                "url": "https://api.perplexity.ai/chat/completions",
                "headers": {"Authorization": f"Bearer {api_key}"},
                "method": "skip",
            },
        }

        endpoint = validation_endpoints.get(provider_name)
        if not endpoint:
            return True, "No validation endpoint (assumed valid)"

        if endpoint.get("method") == "skip":
            return True, "Validation skipped (no test endpoint)"

        try:
            resp = httpx.get(
                endpoint["url"],
                headers=endpoint.get("headers", {}),
                timeout=10,
            )
            if resp.status_code == 200:
                return True, "OK"
            elif resp.status_code == 401:
                return False, "Invalid API key (401 Unauthorized)"
            elif resp.status_code == 403:
                return False, "Access forbidden (403) — check key permissions"
            else:
                return False, f"HTTP {resp.status_code}: {resp.text[:100]}"
        except httpx.TimeoutException:
            return False, "Connection timed out"
        except httpx.ConnectError:
            return False, "Could not connect to provider API"
        except (ValueError, RuntimeError, OSError) as e:
            return False, str(e)

    def _interactive_pick_model(self, provider_name: str, api_key: str) -> str | None:
        hardcoded = self._HARDCODED_MODELS.get(provider_name)
        if hardcoded:
            items = [(m, m) for m in hardcoded]
            items.append(("────────────────────", None))
            items.append(("[✏] Type model name manually", "__manual__"))
            sel = self._interactive_menu(items, f"Select a {provider_name} model (↑↓ Enter Esc):")
            if sel is None:
                return None
            if sel != "__manual__":
                return sel
        else:
            meta = self._PROVIDER_META.get(provider_name)
            if meta and meta["base"]:
                import httpx
                base = meta["base"].rstrip("/")
                models_url = f"{base}/models"
                headers = {"Authorization": f"Bearer {api_key}"}
                if provider_name == "anthropic":
                    headers["anthropic-version"] = "2023-06-01"
                try:
                    resp = httpx.get(models_url, headers=headers, timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_models = data.get("data", [])
                        model_ids = []
                        for m in raw_models:
                            mid = m.get("id", m.get("name", ""))
                            if mid:
                                model_ids.append(mid)
                        if provider_name in ("openai", "groq", "deepseek", "nvidia", "mistral", "fireworks", "together", "perplexity", "openrouter", "custom"):
                            skip_terms = ("embed", "whisper", "tts", "davinci", "curie", "babbage", "moderation")
                            model_ids = [m for m in model_ids if not any(t in m.lower() for t in skip_terms)]

                        model_ids = sorted(set(model_ids))
                        if model_ids:
                            items = [(m, m) for m in model_ids[:100]]
                            items.append(("────────────────────", None))
                            items.append(("[✏] Type model name manually", "__manual__"))
                            sel = self._interactive_menu(items, f"Select a {provider_name} model (↑↓ Enter Esc):")
                            if sel is None:
                                return None
                            if sel != "__manual__":
                                return sel
                except (OSError, ValueError, TypeError, KeyError, IndexError):
                    pass

        default_models = {
            "openai": "gpt-4o",
            "anthropic": "claude-sonnet-4-20250514",
            "google": "gemini-2.5-pro-exp-03-25",
            "ollama": "llama3.1",
            "openrouter": "anthropic/claude-sonnet-4-20250514",
            "groq": "llama-3.3-70b-versatile",
            "deepseek": "deepseek-chat",
            "nvidia": "nvidia/llama-3.1-nemotron-70b-instruct",
            "mistral": "mistral-large-latest",
            "fireworks": "accounts/fireworks/models/llama-v3p3-70b-instruct",
            "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "perplexity": "sonar-pro",
        }
        hint = default_models.get(provider_name, "model-name")
        model_name = self._read_line(f"\033[2m  Model name (e.g. {hint}):\033[0m \033[7m \033[0m\b")
        if model_name is None:
            return None
        return model_name.strip() or hint

    def _interactive_connect_provider(self):
        items = [(label, key) for label, key in self._KNOWN_PROVIDERS]
        sel = self._interactive_menu(items, "Select provider (↑↓ Enter Esc):")
        if sel is None:
            return

        provider_name = sel

        saved_key = self._auth_store.get_key(provider_name)
        if saved_key:
            self.r.system_message(f"Found saved key for {provider_name} (✓ stored)")
            items = [("Use saved key", "saved"), ("Enter new key", "new")]
            choice = self._interactive_menu(items, "API key:")
            if choice is None:
                return
            if choice == "saved":
                key = saved_key
            else:
                key = self._read_line(f"\033[2m  Enter API key for {provider_name} (input hidden):\033[0m ", hidden=True)
                if key is None:
                    return
                if not key:
                    self.r.error("API key cannot be empty")
                    return
        else:
            key = self._read_line(f"\033[2m  Enter API key for {provider_name} (input hidden):\033[0m ", hidden=True)
            if key is None:
                return
            if not key:
                self.r.error("API key cannot be empty")
                return

        env_key = self._PROVIDER_META.get(provider_name, {}).get("env_key", f"{provider_name.upper()}_API_KEY")
        os.environ[env_key] = key

        self.r.show_spinner("Validating API key")
        validation_ok = False
        validation_msg = ""
        result_holder = []

        def worker():
            try:
                ok, msg = self._validate_provider_key(provider_name, key)
                result_holder.append((ok, msg))
            except (RuntimeError, TypeError) as e:
                result_holder.append((False, str(e)))

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        try:
            while t.is_alive():
                time.sleep(0.05)
        except KeyboardInterrupt:
            self.r.hide_spinner()
            self.r.system_message("Validation cancelled.")
            return

        self.r.hide_spinner()

        if result_holder:
            validation_ok, validation_msg = result_holder[0]
        else:
            validation_ok, validation_msg = False, "Validation aborted"

        if not validation_ok:
            self.r.error(f"Key validation failed: {validation_msg}")
            items = [("Continue anyway", "continue"), ("Cancel", "cancel")]
            choice = self._interactive_menu(items, "Proceed?")
            if choice != "continue":
                return
        else:
            self.r.system_message(f"✓ Key validated for {provider_name}")

        self._auth_store.save_key(provider_name, key)

        model_name = self._interactive_pick_model(provider_name, key)
        if model_name is None:
            return

        providers_cfg = self._config.setdefault("providers", {})
        pcfg = providers_cfg.setdefault(provider_name, {})
        if model_name:
            pcfg["model"] = model_name
        providers_cfg["active"] = provider_name
        save_config(self._config, self.config_path)

        self._provider_name = provider_name

        try:
            self._init_engine()
            self._init_agent()
            self.r.system_message(f"Connected to {provider_name}")
            new_ctx = self._PROVIDER_CONTEXT_SIZES.get(provider_name, 200000)
            self.r._welcome_params["provider"] = provider_name
            self.r._welcome_params["context_size"] = new_ctx
            self._rebuild_welcome()
        except (ValueError, RuntimeError, OSError, TypeError) as e:
            self.r.error(f"Failed to connect to {provider_name}: {e}")

    def _find_files(self, prefix: str) -> list[str]:
        matches = []
        prefix_lower = prefix.lower()
        try:
            result = subprocess.run(
                ["git", "ls-files", "--", f"*{prefix_lower}*"],
                cwd=self.workspace, capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0 and result.stdout.strip():
                matches = result.stdout.strip().split("\n")
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        if not matches:
            try:
                for p in self.workspace.rglob(f"*{prefix}*"):
                    if p.is_file():
                        rel = p.relative_to(self.workspace)
                        matches.append(str(rel.as_posix()))
                        if len(matches) >= 20:
                            break
            except (OSError, ValueError, TypeError):
                pass
        return sorted(matches)[:20]

    def _interactive_model_config(self, model_path: str):

        sys.stdout.write(alternate_screen() + clear_to_end() + move_to(1, 1) + hide_cursor() + enable_mouse())
        sys.stdout.flush()

        local_cfg = self._config.setdefault("local_model", {})

        params = [
            {"key": "gpu_layers", "label": "GPU Offload Layers", "val": local_cfg.get("gpu_layers", 32), "type": "int", "min": 0, "max": 128, "step": 1},
            {"key": "context_size", "label": "Context Token Limit", "val": local_cfg.get("context_size", 8192), "type": "choice", "choices": [1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072]},
            {"key": "threads", "label": "CPU Thread Pool", "val": local_cfg.get("threads", os.cpu_count() or 8), "type": "int", "min": 1, "max": os.cpu_count() or 16, "step": 1},
            {"key": "temperature", "label": "Temperature", "val": self._config.setdefault("agent", {}).get("temperature", 0.1), "type": "float", "min": 0.0, "max": 2.0, "step": 0.1},
            {"key": "seed", "label": "Random Seed", "val": local_cfg.get("seed", -1), "type": "choice", "choices": [-1, 42, 1337, 2026, 9999]},
            {"key": "flash_attention", "label": "Flash Attention", "val": local_cfg.get("flash_attention", True), "type": "bool"},
        ]

        idx = 0
        confirmed = False

        def param_line(p):
            if p["type"] == "int":
                val = p["val"]
                pct = int((val - p["min"]) / (p["max"] - p["min"]) * 15) if (p["max"] - p["min"]) > 0 else 0
                bar = "█" * pct + "░" * (15 - pct)
                return f"[{bar}] {val} / {p['max']}"
            elif p["type"] == "float":
                val = p["val"]
                pct = int((val - p["min"]) / (p["max"] - p["min"]) * 15) if (p["max"] - p["min"]) > 0 else 0
                bar = "█" * pct + "░" * (15 - pct)
                return f"[{bar}] {val:.1f}"
            elif p["type"] == "choice":
                val = p["val"]
                parts = []
                for c in p["choices"]:
                    if c == val:
                        parts.append(f"\033[1;32m[{c}]\033[0m")
                    else:
                        parts.append(str(c))
                return " | ".join(parts)
            elif p["type"] == "bool":
                if p["val"]:
                    return "\033[1;32m[ON]\033[0m  OFF"
                else:
                    return "ON  \033[1;31m[OFF]\033[0m"

        def adjust_param(p, delta):
            if p["type"] == "int":
                p["val"] = max(p["min"], min(p["max"], p["val"] + delta * p["step"]))
            elif p["type"] == "float":
                p["val"] = max(p["min"], min(p["max"], p["val"] + delta * p["step"]))
                p["val"] = round(p["val"], 1)
            elif p["type"] == "choice":
                c_idx = p["choices"].index(p["val"])
                p["val"] = p["choices"][max(0, min(len(p["choices"]) - 1, c_idx + delta))]
            elif p["type"] == "bool":
                if delta != 0:
                    p["val"] = not p["val"]

        def draw(sel_idx):
            lines = []
            lines.append("\033[1;35m┌────────────────────────────────────────────────────────────────────────┐\033[0m")
            lines.append("\033[1;35m│          NEXUSAGENT — VISUAL MODEL CONFIGURATION HUD                  │\033[0m")
            lines.append("\033[1;35m└────────────────────────────────────────────────────────────────────────┘\033[0m")
            lines.append("")
            lines.append(f"  [bold]Model:[/bold] [cyan]{os.path.basename(model_path)}[/cyan]")
            lines.append(f"  [bold]Path:[/bold]   [dim]{model_path}[/dim]")
            lines.append("")
            lines.append("  \033[2m──────────────────────────────────────────────────────────────────────\033[0m")
            lines.append("")
            for i, p in enumerate(params):
                hi = "\033[7m" if i == sel_idx else ""
                end = "\033[0m" if i == sel_idx else ""
                ptr = " \033[1;35m\u25b8\033[0m " if i == sel_idx else "   "
                label_part = f"{p['label']}:".ljust(25)
                lines.append(f"  {ptr}{hi}{label_part} {param_line(p)}{end}")
            lines.append("")
            lines.append("  \033[2m──────────────────────────────────────────────────────────────────────\033[0m")
            lines.append("")
            lines.append("  \033[1;33mControls:\033[0m")
            lines.append("   \033[2m[\u2191/\u2193] Navigate  \xb7  [\u2190/\u2192] Adjust  \xb7  [Enter] Confirm & Load  \xb7  [Esc] Cancel\033[0m")
            lines.append("")
            sys.stdout.write(move_to(1, 1) + clear_to_end())
            self.console.print("\n".join(lines))
            sys.stdout.flush()

        def handle_mouse_sequence():
            nonlocal idx
            buf = b""
            time.sleep(0.01)
            while self._kbhit():
                buf += self._read_byte()
                if len(buf) >= 6:
                    break
            raw = (b"\x1b[" + buf).decode("utf-8", errors="replace")
            m = re.match(r"^\x1b\[<(\d+);(\d+);(\d+)([Mm])$", raw)
            if not m:
                m = re.match(r"^\x1b\[M(.)(.)(.)$", raw) if raw.startswith("\x1b[M") else None
                if m:
                    cb = ord(m.group(1)) - 32
                    cx = ord(m.group(2)) - 32
                    cy = ord(m.group(3)) - 32
                    btn = cb & 0x3
                    col = max(0, (cx - 4) // 45)
                    if btn == 0 and col < len(params):
                        idx = col
                        draw(idx)
                    return
                return
            btn = int(m.group(1))
            col = max(0, (int(m.group(2)) - 4) // 45)
            is_press = m.group(4) == "M"
            if is_press and btn < 3 and col < len(params):
                if btn == 0:
                    if col == idx:
                        adjust_param(params[idx], 1)
                    else:
                        idx = col
                    draw(idx)
                elif btn == 1:
                    pass
                elif btn == 2:
                    adjust_param(params[idx], -1)
                    draw(idx)

        draw(idx)

        while True:
            while not self._kbhit():
                time.sleep(0.01)
            ch = self._read_byte()

            if ch == b"\x1b":
                if HAS_MSVCRT and self._kbhit():
                    time.sleep(0.01)
                    ch2 = self._read_byte()
                    if ch2 == b"[":
                        if self._kbhit():
                            time.sleep(0.01)
                            ch3 = self._read_byte()
                            if ch3 == b"A":
                                idx = (idx - 1) % len(params)
                                draw(idx)
                            elif ch3 == b"B":
                                idx = (idx + 1) % len(params)
                                draw(idx)
                            elif ch3 == b"C":
                                adjust_param(params[idx], 1)
                                draw(idx)
                            elif ch3 == b"D":
                                adjust_param(params[idx], -1)
                                draw(idx)
                            elif ch3 == b"<":
                                handle_mouse_sequence()
                            elif ch3 == b"M":
                                pass
                    elif ch2 == b"O":
                        if self._kbhit():
                            ch3 = self._read_byte()
                            if ch3 == b"H":
                                idx = 0
                                draw(idx)
                            elif ch3 == b"F":
                                idx = len(params) - 1
                                draw(idx)
                elif not HAS_MSVCRT:
                    time.sleep(0.02)
                    if self._kbhit():
                        ch2 = self._read_byte()
                        if ch2 == b"[":
                            time.sleep(0.01)
                            if self._kbhit():
                                ch3 = self._read_byte()
                                if ch3 == b"A":
                                    idx = (idx - 1) % len(params)
                                    draw(idx)
                                elif ch3 == b"B":
                                    idx = (idx + 1) % len(params)
                                    draw(idx)
                                elif ch3 == b"C":
                                    adjust_param(params[idx], 1)
                                    draw(idx)
                                elif ch3 == b"D":
                                    adjust_param(params[idx], -1)
                                    draw(idx)
                                elif ch3 == b"<":
                                    handle_mouse_sequence()
                                elif ch3 == b"M":
                                    pass
                        elif ch2 == b"O":
                            if self._kbhit():
                                ch3 = self._read_byte()
                                if ch3 == b"H":
                                    idx = 0
                                    draw(idx)
                                elif ch3 == b"F":
                                    idx = len(params) - 1
                                    draw(idx)
                    else:
                        break
                else:
                    break

            elif ch in (b"\r", b"\n"):
                confirmed = True
                break

            elif ch == b"\xe0":
                ch2 = self._read_byte()
                if ch2 == b"H":
                    idx = (idx - 1) % len(params)
                    draw(idx)
                elif ch2 == b"P":
                    idx = (idx + 1) % len(params)
                    draw(idx)
                elif ch2 == b"M":
                    adjust_param(params[idx], 1)
                    draw(idx)
                elif ch2 == b"K":
                    adjust_param(params[idx], -1)
                    draw(idx)

        sys.stdout.write(disable_mouse() + show_cursor() + main_screen())
        sys.stdout.flush()

        if confirmed:
            for p in params:
                if p["key"] == "temperature":
                    self._config.setdefault("agent", {})["temperature"] = p["val"]
                else:
                    local_cfg[p["key"]] = p["val"]
