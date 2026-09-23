"""First-run setup wizard for NexusAgent.

Walks the user through hardware detection, model recommendation,
permission/memory/guardrail mode selection, and optional cloud API key setup.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from nexus_agent.core.config import get_config_dir, save_user_config
from nexus_agent.llm.model_manager import ModelManager
from nexus_agent.llm.runtime_manager import RuntimeManager

logger = logging.getLogger(__name__)

WELCOME_ART = r"""
  _   _                      _    ___     _
 | \ | | ___  ___ _   _  ___| |  / _ \   /_\   ___
 |  \| |/ _ \/ __| | | |/ _ \ | | (_) | //_\\ / __|
 | |\  |  __/ (__| |_| |  __/ |  \__, |/  _  \ (__
 |_| \_|\___|\___|\__,_|\___|_|    /_/ \_/ \_/\___|
"""

PERMISSION_MODES = {
    "suggest": "Suggest tool calls — user must approve each one (safest, most control)",
    "ask": "Ask for approval on sensitive operations, auto-allow safe ones (balanced)",
    "auto": "Auto-execute all tool calls — user reviews the result afterward (fastest)",
}

MEMORY_MODES = {
    "full": "Full persistent memory — agent remembers across sessions (working + long-term + episodic)",
    "session": "Session-only memory — agent forgets everything when you quit",
}

GUARDRAIL_LEVELS = {
    "off": "No guardrails — load any model regardless of memory impact",
    "relaxed": "Warn if model exceeds 95% of memory budget, but allow loading",
    "balanced": "Warn if model exceeds 85% of memory budget, but allow loading (recommended)",
    "strict": "Block loading if model exceeds 70% of memory budget",
}

CLOUD_PROVIDERS = [
    ("openai", "OpenAI", "sk-...", "OPENAI_API_KEY"),
    ("anthropic", "Anthropic", "sk-ant-...", "ANTHROPIC_API_KEY"),
    ("google", "Google (Gemini)", "...", "GEMINI_API_KEY"),
    ("groq", "Groq", "gsk_...", "GROQ_API_KEY"),
    ("deepseek", "DeepSeek", "sk-...", "DEEPSEEK_API_KEY"),
    ("openrouter", "OpenRouter", "sk-or-...", "OPENROUTER_API_KEY"),
]


class SetupWizard:
    """Interactive first-run setup wizard."""

    def __init__(
        self,
        console: Console | None = None,
        prompt_func: Callable[..., str] | None = None,
        confirm_func: Callable[..., bool] | None = None,
    ):
        self.console = console or Console()
        self._prompt = prompt_func or Prompt.ask
        self._confirm = confirm_func or Confirm.ask
        self.config_updates: dict[str, Any] = {}
        self.hardware: dict[str, Any] = {}
        self._ran = False

    def run(self) -> dict[str, Any]:
        """Run the wizard. Returns config updates dict."""
        if self._ran:
            return self.config_updates
        self._ran = True

        self._show_welcome()
        self._detect_hardware()
        self._choose_runtime()
        self._recommend_model()
        self._choose_permission_mode()
        self._choose_memory_mode()
        self._choose_guardrails()
        provider_key = self._choose_cloud_provider()
        self._show_summary()
        self._save(provider_key)
        return self.config_updates

    def _show_welcome(self) -> None:
        self.console.print(WELCOME_ART, style="cyan", justify="center")
        self.console.print(
            Panel.fit(
                "[bold]Welcome to NexusAgent![/bold]\n\n"
                "This quick setup will detect your hardware, recommend a model,\n"
                "and configure permissions, memory, and safety settings.\n\n"
                "You can change any of these later via [cyan]nexus config set[/cyan] or by editing\n"
                f"the config file at [cyan]{get_config_dir() / 'config.yaml'}[/cyan]",
                border_style="cyan",
            )
        )
        self.console.print()

    def _detect_hardware(self) -> None:
        self.console.print("[bold cyan]◆ Step 1: Hardware Detection[/bold cyan]")
        self.console.print("Scanning your system for available resources...\n")

        manager = ModelManager()
        self.hardware = manager.detect_hardware()

        table = Table(box=box.ROUNDED, show_header=False)
        table.add_column("Resource", style="yellow")
        table.add_column("Value", style="green")

        table.add_row("CPU", self.hardware.get("cpu", "unknown"))
        table.add_row("CPU Threads", str(self.hardware.get("cpu_threads", "?")))
        table.add_row("Total RAM", self.hardware.get("ram_total", "unknown"))
        table.add_row("Available RAM", self.hardware.get("ram_available", "unknown"))
        table.add_row("GPU", str(self.hardware.get("gpu", "Not detected")))
        table.add_row("VRAM", str(self.hardware.get("vram", "N/A")))
        table.add_row("NPU", str(self.hardware.get("npu", "Not detected")))
        table.add_row("Recommended Model Size", self.hardware.get("recommended_model_size", "unknown"))

        self.console.print(table)
        self.console.print()

    def _choose_runtime(self) -> None:
        self.console.print("[bold cyan]◆ Step 2: Runtime Selection & Installation[/bold cyan]")
        self.console.print("NexusAgent can use different LLM backends:\n")

        installable = RuntimeManager.get_installable_runtimes()
        table = Table(box=box.SIMPLE, show_header=True)
        table.add_column("Backend", style="yellow", width=10)
        table.add_column("Description", style="white")
        table.add_column("Status", style="green", width=14)
        for key, rt in installable.items():
            status = "✓ Installed" if RuntimeManager.is_runtime_installed(key) else "Not installed"
            table.add_row(key, rt["description"], status)
        self.console.print(table)
        self.console.print()

        hw = self.hardware
        gpu_name = str(hw.get("gpu", ""))
        gpu_detected = gpu_name != "Not detected"
        has_cuda = False
        if "NVIDIA" in gpu_name:
            import os as _os
            import shutil
            if shutil.which("nvcc") or _os.environ.get("CUDA_PATH") or _os.environ.get("CUDA_HOME"):
                has_cuda = True

        if gpu_detected and has_cuda:
            default_runtime = "cuda"
        elif gpu_detected:
            default_runtime = "cpu"
        else:
            default_runtime = "cpu"

        install_now = self._confirm(
            f"  Would you like to install the [cyan]{default_runtime}[/cyan] runtime now?",
            default=True,
        )
        if install_now:
            if not RuntimeManager.is_runtime_installed(default_runtime):
                self.console.print(f"  [dim]Installing {default_runtime} runtime...[/dim]")
                success = RuntimeManager.install_runtime(default_runtime)
                if success:
                    self.config_updates.setdefault("local_model", {})
                    self.config_updates["local_model"]["runtime"] = default_runtime
                    self.console.print(f"  [green]✓ {default_runtime} runtime installed[/green]")
                else:
                    self.console.print(f"  [yellow]Installation skipped or failed. You can install later via /runtime install {default_runtime}[/yellow]")
            else:
                self.console.print(f"  [green]✓ {default_runtime} runtime already installed[/green]")
                self.config_updates.setdefault("local_model", {})
                self.config_updates["local_model"]["runtime"] = default_runtime

            if gpu_detected and has_cuda and default_runtime == "cuda":
                install_cpu = self._confirm(
                    "  Also install CPU runtime as fallback?",
                    default=True,
                )
                if install_cpu and not RuntimeManager.is_runtime_installed("cpu"):
                    self.console.print("  [dim]Installing CPU runtime...[/dim]")
                    RuntimeManager.install_runtime("cpu")
        else:
            self.config_updates.setdefault("local_model", {})
            self.config_updates["local_model"]["runtime"] = "auto"
        self.console.print()

    def _recommend_model(self) -> None:
        self.console.print("[bold cyan]◆ Step 3: Model Recommendation[/bold cyan]")
        hw = self.hardware
        ram_bytes = hw.get("ram_total_bytes", 0)
        vram_bytes = hw.get("vram_bytes", 0)
        usable = max(ram_bytes, vram_bytes)

        gpu_detected = hw.get("gpu", "Not detected") != "Not detected"
        npu_detected = hw.get("npu", "Not detected") != "Not detected"

        self.console.print(f"Based on your hardware ([green]{hw.get('recommended_model_size', '?')}[/green]):")
        self.console.print()

        if usable >= 64 * 1024**3:
            self.console.print("  [bold]Large models (70B+):[/bold] llama-3.3-70b, qwen2.5-72b, deepseek-v2-67b")
            recommended = "llama-3.3-70b (Q4_K_M)"
        elif usable >= 32 * 1024**3:
            self.console.print("  [bold]Medium models (30B-70B):[/bold] llama-3.1-70b (Q4), mixtral-8x22b (Q4)")
            recommended = "llama-3.1-70b (Q4_K_M)"
        elif usable >= 16 * 1024**3:
            self.console.print("  [bold]Standard models (13B-30B):[/bold] llama-3.1-8b, qwen2.5-14b, phi-4-14b")
            recommended = "llama-3.1-8b (Q4_K_M)"
        elif usable >= 8 * 1024**3:
            self.console.print("  [bold]Small models (7B-13B):[/bold] qwen2.5-7b, gemma-2-9b, llama-3.2-3b")
            recommended = "qwen2.5-7b (Q4_K_M)"
        else:
            self.console.print("  [bold]Tiny models (1B-3B):[/bold] phi-3-mini, gemma-2-2b, qwen2.5-1.5b")
            recommended = "phi-3-mini (Q4_K_M)"

        platform_note = ""
        if gpu_detected:
            platform_note += "\n  [green]GPU detected — GPU offloading will accelerate inference.[/green]"
        if npu_detected:
            platform_note += "\n  [green]NPU detected — ONNX Runtime with DirectML can utilize this.[/green]"
        if platform_note:
            self.console.print(platform_note)

        self.console.print()
        self.console.print(f"  [dim]Recommended starting model: [cyan]{recommended}[/cyan][/dim]")
        self.console.print("  [dim]You can download GGUF models from: [cyan]https://huggingface.co/models?search=gguf[/cyan][/dim]")

        download = self._confirm("  Would you like to open the HF model search page?", default=False)
        if download:
            import webbrowser
            webbrowser.open("https://huggingface.co/models?sort=trending&search=gguf")

        self.config_updates.setdefault("local_model", {})
        self.config_updates["local_model"]["gpu_layers"] = -1 if gpu_detected else 0
        self.config_updates["local_model"]["threads"] = hw.get("cpu_threads", 0)
        self.console.print()

    def _choose_permission_mode(self) -> None:
        self.console.print("[bold cyan]◆ Step 4: Permission Mode[/bold cyan]")
        self.console.print("Controls how the agent asks for approval before executing tools:\n")

        table = Table(box=box.SIMPLE, show_header=True)
        table.add_column("Mode", style="yellow", width=12)
        table.add_column("Description", style="white")
        table.add_row("suggest", PERMISSION_MODES["suggest"])
        table.add_row("ask", PERMISSION_MODES["ask"])
        table.add_row("auto", PERMISSION_MODES["auto"])
        self.console.print(table)
        self.console.print()

        mode = self._prompt(
            "  Choose permission mode",
            choices=["suggest", "ask", "auto"],
            default="ask",
        )
        self.config_updates.setdefault("permissions", {})
        self.config_updates["permissions"]["mode"] = mode
        self.console.print()

    def _choose_memory_mode(self) -> None:
        self.console.print("[bold cyan]◆ Step 5: Memory Mode[/bold cyan]")
        self.console.print("Controls whether the agent remembers across sessions:\n")

        table = Table(box=box.SIMPLE, show_header=True)
        table.add_column("Mode", style="yellow", width=12)
        table.add_column("Description", style="white")
        table.add_row("full", MEMORY_MODES["full"])
        table.add_row("session", MEMORY_MODES["session"])
        self.console.print(table)
        self.console.print()

        mode = self._prompt(
            "  Choose memory mode",
            choices=["full", "session"],
            default="full",
        )
        self.config_updates.setdefault("memory", {})
        self.config_updates["memory"]["enabled"] = mode == "full"
        self.config_updates["memory"]["mode"] = mode
        self.console.print()

    def _choose_guardrails(self) -> None:
        self.console.print("[bold cyan]◆ Step 6: Model Loading Guardrails[/bold cyan]")
        self.console.print("Prevents loading models that exceed your system memory:\n")

        table = Table(box=box.SIMPLE, show_header=True)
        table.add_column("Level", style="yellow", width=12)
        table.add_column("Description", style="white")
        table.add_row("off", GUARDRAIL_LEVELS["off"])
        table.add_row("relaxed", GUARDRAIL_LEVELS["relaxed"])
        table.add_row("balanced", GUARDRAIL_LEVELS["balanced"])
        table.add_row("strict", GUARDRAIL_LEVELS["strict"])
        self.console.print(table)
        self.console.print()

        level = self._prompt(
            "  Choose guardrail level",
            choices=["off", "relaxed", "balanced", "strict"],
            default="balanced",
        )
        self.config_updates.setdefault("local_model", {})
        self.config_updates["local_model"]["guardrails"] = level
        self.console.print()

    def _choose_cloud_provider(self) -> str | None:
        self.console.print("[bold cyan]◆ Step 7: Cloud Provider API Keys (Optional)[/bold cyan]")
        self.console.print(
            "NexusAgent works fully offline with local GGUF models.\n"
            "You can optionally configure cloud providers for hybrid mode.\n"
        )

        add_keys = self._confirm("  Would you like to add any cloud API keys now?", default=False)
        provider_key = None
        if add_keys:
            self.console.print()
            for key, name, example, env_var in CLOUD_PROVIDERS:
                add = self._confirm(f"  Configure [cyan]{name}[/cyan] ({env_var})?", default=False)
                if add:
                    api_key = self._prompt(f"    Enter your {name} API key ({example})")
                    if api_key and api_key.strip():
                        self.config_updates.setdefault("providers", {})
                        self.config_updates["providers"].setdefault(key, {})
                        self.config_updates["providers"][key]["api_key"] = api_key.strip()
                        if provider_key is None:
                            provider_key = key

            if provider_key:
                make_active = self._confirm(
                    f"  Make [cyan]{provider_key}[/cyan] the active provider?", default=False
                )
                if make_active:
                    self.config_updates.setdefault("providers", {})
                    self.config_updates["providers"]["active"] = provider_key

        self.console.print()
        return provider_key

    def _show_summary(self) -> None:
        self.console.print("[bold cyan]◆ Setup Summary[/bold cyan]")
        self.console.print()

        runtime = self.config_updates.get("local_model", {}).get("runtime", "auto")
        items = [
            ("Runtime Backend", runtime),
            ("Permission Mode", self.config_updates.get("permissions", {}).get("mode", "ask")),
            ("Memory Mode", self.config_updates.get("memory", {}).get("mode", "full")),
            ("Guardrail Level", self.config_updates.get("local_model", {}).get("guardrails", "balanced")),
            ("GPU Offloading", "Enabled" if self.config_updates.get("local_model", {}).get("gpu_layers", 0) != 0 else "Disabled (CPU only)"),
        ]

        providers_configured = [k for k in CLOUD_PROVIDERS
                                if self.config_updates.get("providers", {}).get(k[0], {}).get("api_key")]
        if providers_configured:
            items.append(("Cloud Providers", ", ".join(c[1] for c in providers_configured)))
        else:
            items.append(("Cloud Providers", "None (offline mode)"))

        table = Table(box=box.ROUNDED, show_header=False)
        table.add_column("Setting", style="yellow", width=20)
        table.add_column("Value", style="green")
        for name, value in items:
            table.add_row(name, str(value))
        self.console.print(table)
        self.console.print()

    def _save(self, provider_key: str | None) -> None:
        self.console.print("[bold cyan]◆ Saving Configuration[/bold cyan]")
        try:
            save_user_config(self.config_updates)
            config_path = get_config_dir() / "config.yaml"
            self.console.print(f"  [green]Configuration saved to {config_path}[/green]")
            self.console.print()
            self.console.print("[bold green]Setup complete![/bold green] Run [cyan]nexus chat[/cyan] to start.")
        except OSError as e:
            logger.error(f"Failed to save config: {e}")
            self.console.print(f"  [red]Failed to save configuration: {e}[/red]")
            self.console.print("  You can manually edit the config file later.")
            self.console.print()
            self.console.print("[yellow]Setup incomplete. Run [cyan]nexus wizard[/cyan] to try again.[/yellow]")
