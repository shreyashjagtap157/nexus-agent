"""Model slash commands — /model, /runtime, /display-settings."""

from __future__ import annotations

import os
import sys

from nexus_agent.cli.commands._base import BaseCommands
from nexus_agent.core.config import save_config


class ModelCommands(BaseCommands):
    """Mixin providing model-related slash command handlers."""


    def _cmd_model(self, args: str):
        parts = args.strip().split(maxsplit=2) if args else []
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
            name = parts[1]
            raw_path = parts[2]
            stripped = raw_path.strip("\"'")
            path = os.path.abspath(stripped)
            if not os.path.isfile(path):
                self.r.error(f"File not found: {path}")
                return
            self._models_db.add(name, path)
            self.r.system_message(f"Model saved: {name} → {path}")
            return

        elif subcmd == "remove" and len(parts) >= 2:
            name = parts[1]
            if self._models_db.remove(name):
                self.r.system_message(f"Model removed: {name}")
            else:
                self.r.error(f"Model not found: {name}")
            return

        elif subcmd == "switch" and len(parts) >= 2:
            name = parts[1]
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
            self._init_engine(skip_interactive=False)
            self._init_agent()
            if self._engine and getattr(self._engine, "is_loaded", True):
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
        sel = self._interactive_menu(
            [(label, val) for label, val in items],
            "Display Settings (↑↓ Enter Esc):",
        )
        if sel is None:
            self._display_settings_idx = 0
            return
        self._display_settings_idx = 0
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
                    self.console.print(f"  {key:12s} {rt['name']:40s} {status}")
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
            self.console.print(format_runtime_list(self._runtime_list) or "  [dim]No runtimes detected. Run /runtime scan[/dim]")

        elif subcmd == "select" and len(parts) >= 2:
            name = parts[1].strip()
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
                self.r.error("Failed to switch runtime. Valid: auto, llama-cpp, onnx")

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
