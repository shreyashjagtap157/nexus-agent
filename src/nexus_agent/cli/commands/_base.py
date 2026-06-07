"""Base shared helpers for slash command handlers."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
from typing import Any

from blessed import Terminal
from rich.box import ROUNDED
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from nexus_agent.core.config import save_config

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

    # Per-instance state used by `/copy` and similar commands.
    # Initialized here so the attributes always exist (avoids AttributeError
    # in any mixin that reads them).
    _copied_text: str = ""
    _last_responses: list[str] = []  # most-recent assistant outputs (newest first)

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
        icons = {"installing": "▶", "verifying": "●", "complete": "✓", "error": "X"}
        icon = icons.get(status, "▶")
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


    def _interactive_menu(self, items: list[tuple[str, str | None]], title: str = "Select:") -> str | None:
        idx = 0
        selectable = [i for i, (label, val) in enumerate(items) if val is not None]
        if not selectable:
            return None
        n_selectable = len(selectable)

        with Live(auto_refresh=False, console=self.console, screen=False) as live:

            def build(sel_idx):
                table = Table(show_header=False, box=ROUNDED, padding=(0, 1))
                table.add_column("Items")
                table.add_row(Text(f'  {title}', style="dim"))
                if items:
                    sep = "\u2500" * 20
                    table.add_row(Text(f"  {sep}", style="dim"))
                for i, (label, val) in enumerate(items):
                    if val is None:
                        table.add_row(Text(f'    {label}', style="dim"))
                    else:
                        prefix = "\u25b8" if i == sel_idx else " "
                        entry = f"    {prefix}  {label}"
                        if i == sel_idx:
                            table.add_row(Text(f'{entry}', style="reverse"))
                        else:
                            table.add_row(Text(entry))
                return table

            live.update(build(idx))

            while True:
                ch = self._read_byte()
                if ch == b"\xe0":
                    ch2 = self._read_byte()
                    if ch2 == b"H":
                        ci = selectable.index(idx)
                        ci = (ci - 1) % n_selectable
                        idx = selectable[ci]
                        live.update(build(idx))
                    elif ch2 == b"P":
                        ci = selectable.index(idx)
                        ci = (ci + 1) % n_selectable
                        idx = selectable[ci]
                        live.update(build(idx))
                elif ch in (b"\r", b"\n"):
                    break
                elif ch == b"\x1b":
                    idx = -1
                    break

        if idx < 0:
            return None
        return items[idx][1]


    def _interactive_add_model(self):
        self.r.console.print("  Enter model name: ", end="")
        name = self._read_line("")
        if name is None:
            return
        if not name:
            self.r.error("Name cannot be empty")
            return

        self.r.console.print("  Enter model path: ", end="")
        path = self._read_line("")
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
        self.r.console.print(f"  Model name (e.g. {hint}): ", end="")
        model_name = self._read_line("")
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
                self.r.console.print(f"  Enter API key for {provider_name} (input hidden): ", end="")
                key = self._read_line("", hidden=True)
                if key is None:
                    return
                if not key:
                    self.r.error("API key cannot be empty")
                    return
        else:
            self.r.console.print(f"  Enter API key for {provider_name} (input hidden): ", end="")
            key = self._read_line("", hidden=True)
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
            self.r.rebuild_welcome(self._tokens, self._metrics)
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
                bar = "\u2588" * pct + "\u2591" * (15 - pct)
                return f"[{bar}] {val} / {p['max']}"
            elif p["type"] == "float":
                val = p["val"]
                pct = int((val - p["min"]) / (p["max"] - p["min"]) * 15) if (p["max"] - p["min"]) > 0 else 0
                bar = "\u2588" * pct + "\u2591" * (15 - pct)
                return f"[{bar}] {val:.1f}"
            elif p["type"] == "choice":
                val = p["val"]
                parts = []
                for c in p["choices"]:
                    if c == val:
                        parts.append(f"[{c}]")
                    else:
                        parts.append(str(c))
                return " | ".join(parts)
            elif p["type"] == "bool":
                return "[ON]  OFF" if p["val"] else "ON  [OFF]"

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

        def build_table():
            table = Table(show_header=False, box=ROUNDED, padding=(0, 1))
            table.add_column("Param", style="bold", width=28)
            table.add_column("Value")
            for i, p in enumerate(params):
                name = p["label"]
                value_text = param_line(p)
                if i == idx:
                    table.add_row(
                        Text(f"  \u25b8 {name}", style="reverse"),
                        Text(f"  {value_text}", style="reverse"),
                    )
                else:
                    table.add_row(
                        Text(f"   {name}"),
                        Text(f"  {value_text}"),
                    )
            return Panel(
                table,
                title=Text(" NexusAgent \u2014 Visual Model Configuration ", style="bold magenta"),
                border_style="bright_magenta",
                subtitle=Text(
                    " [\u2191/\u2193] Navigate  \u00b7  [\u2190/\u2192] Adjust  \u00b7  [Enter] Confirm  \u00b7  [Esc] Cancel",
                    style="dim",
                ),
            )

        with _term.fullscreen(), _term.hidden_cursor(), _term.mouse_support():
            with Live(auto_refresh=False, console=self.console, screen=False) as live:
                live.update(build_table())

                while True:
                    key = _term.inkey(timeout=0.1)
                    if not key:
                        continue

                    if key.is_sequence:
                        if key.code == _term.KEY_UP:
                            idx = (idx - 1) % len(params)
                        elif key.code == _term.KEY_DOWN:
                            idx = (idx + 1) % len(params)
                        elif key.code == _term.KEY_LEFT:
                            adjust_param(params[idx], -1)
                        elif key.code == _term.KEY_RIGHT:
                            adjust_param(params[idx], 1)
                        elif key.code == _term.KEY_HOME:
                            idx = 0
                        elif key.code == _term.KEY_END:
                            idx = len(params) - 1
                        elif key.code == _term.KEY_ESCAPE:
                            break
                        live.update(build_table())
                    elif str(key) in ("\r", "\n"):
                        confirmed = True
                        break

        if confirmed:
            for p in params:
                if p["key"] == "temperature":
                    self._config.setdefault("agent", {})["temperature"] = p["val"]
                else:
                    local_cfg[p["key"]] = p["val"]

