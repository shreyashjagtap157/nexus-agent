"""Shared interactive UI helpers — canonical implementations.

Consolidated from duplicated methods that existed in both ``_base.py``
and ``interactive_mixin.py``.  Mix this into any class that needs
interactive menus, model config HUD, or provider connection flows.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
from typing import Any

from nexus_agent.core.config import save_config


class InteractiveUIMixin:
    """Canonical interactive UI helpers — menus, model config, provider connect."""

    # ── Interactive menu ──────────────────────────────────────────────

    def _interactive_menu(
        self,
        items: list[tuple[str, str | None]],
        title: str = "Select:",
    ) -> str | None:
        """Arrow-key selectable menu rendered with raw ANSI escapes.

        *items* is a list of ``(label, value)`` pairs.  Pairs with
        ``value=None`` act as non-selectable separators.  Returns the
        selected value or ``None`` if the user pressed Esc.
        """
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
                    prefix = "\u25b8 " if i == sel_idx else "  "
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

    # ── Add model interactively ──────────────────────────────────────

    def _interactive_add_model(self):
        """Walk the user through adding a new local model to the database."""
        name = self._read_line(
            "\033[2m  Enter model name:\033[0m \033[7m \033[0m\b"
        )
        if name is None:
            return
        if not name:
            self.r.error("Name cannot be empty")
            return

        path = self._read_line(
            "\033[2m  Enter model path:\033[0m \033[7m \033[0m\b"
        )
        if path is None:
            return

        raw_path = path.strip("\"'")
        abs_path = os.path.abspath(raw_path)
        if not os.path.isfile(abs_path):
            self.r.error(f"File not found: {abs_path}")
            return

        self._models_db.add(name, abs_path)
        self.r.system_message(f"Model saved: {name} \u2192 {abs_path}")
        self.r.system_message(f"Use /model switch {name} to load it")

    # ── Provider key validation ──────────────────────────────────────

    def _validate_provider_key(
        self, provider_name: str, api_key: str
    ) -> tuple[bool, str]:
        """Validate an API key by hitting the provider's models endpoint.

        Returns ``(ok, message)``.
        """
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
                "url": (
                    "https://generativelanguage.googleapis.com/v1/models"
                    f"?key={api_key}"
                ),
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
                return (
                    False,
                    "Access forbidden (403) \u2014 check key permissions",
                )
            else:
                return False, f"HTTP {resp.status_code}: {resp.text[:100]}"
        except httpx.TimeoutException:
            return False, "Connection timed out"
        except httpx.ConnectError:
            return False, "Could not connect to provider API"
        except (ValueError, RuntimeError, OSError) as e:
            return False, str(e)

    # ── Interactive model picker ─────────────────────────────────────

    def _interactive_pick_model(
        self, provider_name: str, api_key: str
    ) -> str | None:
        """Let the user pick a model from the provider's available list
        or type one manually."""
        hardcoded = self._HARDCODED_MODELS.get(provider_name)
        if hardcoded:
            items = [(m, m) for m in hardcoded]
            items.append(("\u2500" * 20, None))
            items.append(("[✏] Type model name manually", "__manual__"))
            sel = self._interactive_menu(
                items,
                f"Select a {provider_name} model (\u2191\u2193 Enter Esc):",
            )
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
                        skip_terms = (
                            "embed",
                            "whisper",
                            "tts",
                            "davinci",
                            "curie",
                            "babbage",
                            "moderation",
                        )
                        if provider_name in (
                            "openai",
                            "groq",
                            "deepseek",
                            "nvidia",
                            "mistral",
                            "fireworks",
                            "together",
                            "perplexity",
                            "openrouter",
                            "custom",
                        ):
                            model_ids = [
                                m
                                for m in model_ids
                                if not any(t in m.lower() for t in skip_terms)
                            ]
                        model_ids = sorted(set(model_ids))
                        if model_ids:
                            items = [(m, m) for m in model_ids[:100]]
                            items.append(("\u2500" * 20, None))
                            items.append(
                                ("[✏] Type model name manually", "__manual__")
                            )
                            sel = self._interactive_menu(
                                items,
                                f"Select a {provider_name} model (\u2191\u2193 Enter Esc):",
                            )
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
        model_name = self._read_line(
            f"\033[2m  Model name (e.g. {hint}):\033[0m \033[7m \033[0m\b"
        )
        if model_name is None:
            return None
        return model_name.strip() or hint

    # ── Interactive provider connection ──────────────────────────────

    def _interactive_connect_provider(self):
        """Full interactive flow: pick provider → enter/use-saved key →
        validate → pick model → connect."""
        items = [(label, key) for label, key in self._KNOWN_PROVIDERS]
        sel = self._interactive_menu(
            items, "Select provider (\u2191\u2193 Enter Esc):"
        )
        if sel is None:
            return

        provider_name = sel

        saved_key = self._auth_store.get_key(provider_name)
        if saved_key:
            self.r.system_message(
                f"Found saved key for {provider_name} (\u2713 stored)"
            )
            items = [("Use saved key", "saved"), ("Enter new key", "new")]
            choice = self._interactive_menu(items, "API key:")
            if choice is None:
                return
            if choice == "saved":
                key = saved_key
            else:
                key = self._read_line(
                    f"\033[2m  Enter API key for {provider_name}"
                    " (input hidden):\033[0m ",
                    hidden=True,
                )
                if key is None:
                    return
                if not key:
                    self.r.error("API key cannot be empty")
                    return
        else:
            key = self._read_line(
                f"\033[2m  Enter API key for {provider_name}"
                " (input hidden):\033[0m ",
                hidden=True,
            )
            if key is None:
                return
            if not key:
                self.r.error("API key cannot be empty")
                return

        env_key = self._PROVIDER_META.get(provider_name, {}).get(
            "env_key", f"{provider_name.upper()}_API_KEY"
        )
        os.environ[env_key] = key

        self.r.show_spinner("Validating API key")
        validation_ok = False
        validation_msg = ""
        result_holder: list[tuple[bool, str]] = []

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
            self.r.system_message(f"\u2713 Key validated for {provider_name}")

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

    # ── File search helper ───────────────────────────────────────────

    def _find_files(self, prefix: str) -> list[str]:
        """Return up to 20 workspace files matching *prefix*."""
        matches: list[str] = []
        prefix_lower = prefix.lower()
        try:
            result = subprocess.run(
                ["git", "ls-files", "--", f"*{prefix_lower}*"],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=3,
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

    # ── Interactive model configuration HUD ──────────────────────────

    def _interactive_model_config(self, model_path: str):
        """Full-screen visual model parameter configurator.

        Arrow keys to navigate/adjust, Enter to confirm, Esc to cancel.
        Supports mouse clicks on Windows via MSVCRT.
        """
        from nexus_agent.cli.renderer import (
            HAS_MSVCRT,
            alternate_screen,
            clear_to_end,
            disable_mouse,
            enable_mouse,
            hide_cursor,
            main_screen,
            move_to,
            show_cursor,
        )

        sys.stdout.write(
            alternate_screen()
            + clear_to_end()
            + move_to(1, 1)
            + hide_cursor()
            + enable_mouse()
        )
        sys.stdout.flush()

        local_cfg = self._config.setdefault("local_model", {})

        params = [
            {
                "key": "gpu_layers",
                "label": "GPU Offload Layers",
                "val": local_cfg.get("gpu_layers", 32),
                "type": "int",
                "min": 0,
                "max": 128,
                "step": 1,
            },
            {
                "key": "context_size",
                "label": "Context Token Limit",
                "val": local_cfg.get("context_size", 8192),
                "type": "choice",
                "choices": [1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072],
            },
            {
                "key": "threads",
                "label": "CPU Thread Pool",
                "val": local_cfg.get("threads", os.cpu_count() or 8),
                "type": "int",
                "min": 1,
                "max": os.cpu_count() or 16,
                "step": 1,
            },
            {
                "key": "temperature",
                "label": "Temperature",
                "val": self._config.setdefault("agent", {}).get(
                    "temperature", 0.1
                ),
                "type": "float",
                "min": 0.0,
                "max": 2.0,
                "step": 0.1,
            },
            {
                "key": "seed",
                "label": "Random Seed",
                "val": local_cfg.get("seed", -1),
                "type": "choice",
                "choices": [-1, 42, 1337, 2026, 9999],
            },
            {
                "key": "flash_attention",
                "label": "Flash Attention",
                "val": local_cfg.get("flash_attention", True),
                "type": "bool",
            },
        ]

        idx = 0
        confirmed = False

        def param_line(p):
            if p["type"] == "int":
                val = p["val"]
                rng = p["max"] - p["min"]
                pct = int((val - p["min"]) / rng * 15) if rng > 0 else 0
                bar = "\u2588" * pct + "\u2591" * (15 - pct)
                return f"[{bar}] {val} / {p['max']}"
            elif p["type"] == "float":
                val = p["val"]
                rng = p["max"] - p["min"]
                pct = int((val - p["min"]) / rng * 15) if rng > 0 else 0
                bar = "\u2588" * pct + "\u2591" * (15 - pct)
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
                p["val"] = max(
                    p["min"], min(p["max"], p["val"] + delta * p["step"])
                )
            elif p["type"] == "float":
                p["val"] = max(
                    p["min"],
                    min(p["max"], p["val"] + delta * p["step"]),
                )
                p["val"] = round(p["val"], 1)
            elif p["type"] == "choice":
                c_idx = p["choices"].index(p["val"])
                p["val"] = p["choices"][
                    max(0, min(len(p["choices"]) - 1, c_idx + delta))
                ]
            elif p["type"] == "bool":
                if delta != 0:
                    p["val"] = not p["val"]

        def draw(sel_idx):
            lines = []
            lines.append(
                "\033[1;35m\u250c"
                + "\u2500" * 72
                + "\u2510\033[0m"
            )
            lines.append(
                "\033[1;35m\u2502          NEXUSAGENT \u2014"
                " VISUAL MODEL CONFIGURATION HUD"
                "                  \u2502\033[0m"
            )
            lines.append(
                "\033[1;35m\u2514"
                + "\u2500" * 72
                + "\u2518\033[0m"
            )
            lines.append("")
            lines.append(
                f"  [bold]Model:[/bold]"
                f" [cyan]{os.path.basename(model_path)}[/cyan]"
            )
            lines.append(
                f"  [bold]Path:[/bold]   [dim]{model_path}[/dim]"
            )
            lines.append("")
            lines.append(
                "  \033[2m" + "\u2500" * 70 + "\033[0m"
            )
            lines.append("")
            for i, p in enumerate(params):
                hi = "\033[7m" if i == sel_idx else ""
                end = "\033[0m" if i == sel_idx else ""
                ptr = " \033[1;35m\u25b8\033[0m " if i == sel_idx else "   "
                label_part = f"{p['label']}:".ljust(25)
                lines.append(f"  {ptr}{hi}{label_part} {param_line(p)}{end}")
            lines.append("")
            lines.append(
                "  \033[2m" + "\u2500" * 70 + "\033[0m"
            )
            lines.append("")
            lines.append("  \033[1;33mControls:\033[0m")
            lines.append(
                "   \033[2m[\u2191/\u2193] Navigate  \u00b7"
                "  [\u2190/\u2192] Adjust  \u00b7"
                "  [Enter] Confirm & Load  \u00b7  [Esc] Cancel\033[0m"
            )
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
                m = (
                    re.match(r"^\x1b\[M(.)(.)(.)$", raw)
                    if raw.startswith("\x1b[M")
                    else None
                )
                if m:
                    cb = ord(m.group(1)) - 32
                    cx = ord(m.group(2)) - 32
                    cy = ord(m.group(3)) - 32
                    btn_num = cb & 0x3
                    col = max(0, (cx - 4) // 45)
                    if btn_num == 0 and col < len(params):
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
                    self._config.setdefault("agent", {})["temperature"] = p[
                        "val"
                    ]
                else:
                    local_cfg[p["key"]] = p["val"]
