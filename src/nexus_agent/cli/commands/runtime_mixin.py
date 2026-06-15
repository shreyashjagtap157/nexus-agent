"""Runtime slash commands — /runtime management and helpers.

Extracted from the monolithic command_dispatcher.py to reduce file size.
"""

from __future__ import annotations

import os

from nexus_agent.core.config import save_config


class RuntimeCommandsMixin:
    """Mixin providing runtime management slash command and helpers."""

    def _cmd_runtime(self, args: str):
        from nexus_agent.cli.runtimes import format_runtime_list, scan_runtimes
        from nexus_agent.llm.runtime_manager import RuntimeManager

        parts = args.strip().split(maxsplit=1) if args else []
        subcmd = parts[0].lower() if parts else ""

        if subcmd == "scan":
            self.console.print("  [dim]Scanning for available runtimes\u2026[/dim]")
            self._runtime_list = self._get_custom_runtimes() + scan_runtimes()
            self.console.print(format_runtime_list(self._runtime_list))
            self.console.print(
                f"\n  [dim]{len(self._runtime_list)} runtime(s) detected[/dim]"
            )

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
            self.r.system_message(
                f"Custom runtime registered: {name} \u2192 {abs_path}"
            )
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
                    status = (
                        "[green]\u2713 installed[/green]"
                        if RuntimeManager.is_runtime_installed(key)
                        else "[dim]not installed[/dim]"
                    )
                    rec_str = (
                        " [yellow](Recommended for your system)[/yellow]"
                        if rt.get("recommended")
                        else ""
                    )
                    self.console.print(
                        f"  {key:12s} {rt['name']:40s} {status}{rec_str}"
                    )
                    self.console.print(
                        f"  {'':12s} [dim]{rt['description']}[/dim]"
                    )
                self.console.print(
                    "\n  Usage: [bold]/runtime install <backend>[/bold]"
                )
                self.console.print(f"  Backends: {', '.join(installable.keys())}")
                return

            if RuntimeManager.is_runtime_installed(backend):
                self.r.system_message(
                    f"{backend} runtime is already installed. Use /runtime reinstall {backend} to reinstall."
                )
                return

            self.console.print(
                f"  [dim]Installing {backend} runtime...[/dim]"
            )
            success = RuntimeManager.install_runtime(
                backend, progress_callback=self._runtime_progress
            )
            if success:
                self._runtime_list = self._get_custom_runtimes() + scan_runtimes()
                self.r.system_message(
                    f"\u2713 {backend} runtime installed successfully"
                )
            else:
                self.r.error(
                    f"Failed to install {backend} runtime. See logs for details."
                )

        elif subcmd == "reinstall":
            backend = parts[1].strip().lower() if len(parts) >= 2 else ""
            if not backend:
                self.r.error("Usage: /runtime reinstall <backend>")
                return
            self.console.print(
                f"  [dim]Reinstalling {backend} runtime...[/dim]"
            )
            success = RuntimeManager.install_runtime(
                backend,
                force_reinstall=True,
                progress_callback=self._runtime_progress,
            )
            if success:
                self._runtime_list = self._get_custom_runtimes() + scan_runtimes()
                self.r.system_message(
                    f"\u2713 {backend} runtime reinstalled successfully"
                )
            else:
                self.r.error(
                    f"Failed to reinstall {backend} runtime. See logs for details."
                )

        elif subcmd == "uninstall":
            backend = parts[1].strip().lower() if len(parts) >= 2 else ""
            if not backend:
                self.r.error("Usage: /runtime uninstall <backend>")
                return
            self.console.print(
                f"  [dim]Uninstalling {backend} runtime...[/dim]"
            )
            success = RuntimeManager.uninstall_runtime(backend)
            if success:
                self._runtime_list = self._get_custom_runtimes() + scan_runtimes()
                self.r.system_message(
                    f"\u2713 {backend} runtime uninstalled"
                )
            else:
                self.r.error(f"Failed to uninstall {backend} runtime.")

        elif subcmd == "list" or (not args):
            if not self._runtime_list:
                self._runtime_list = self._get_custom_runtimes() + scan_runtimes()
            runtime_items: list[tuple[str, str | None]] = []
            for rt in self._runtime_list:
                status = "\u2713" if rt.available else "\u2717"
                runtime_items.append(
                    (f"{status} {rt.name} ({rt.description})", rt.name)
                )
            runtime_items.append(("Cancel", "exit"))
            sel = self._interactive_menu(
                runtime_items, "Select a runtime (\u2191\u2193 Enter Esc):"
            )
            if sel and sel != "exit":
                self._cmd_runtime(f"select {sel}")
            return

        elif subcmd == "select" and len(parts) >= 2:
            name = parts[1].strip()
            installable = RuntimeManager.get_installable_runtimes()
            if name.lower() in installable:
                backend = name.lower()
                if not RuntimeManager.is_runtime_installed(backend):
                    self.r.error(
                        f"Runtime '{backend}' is not installed. Run /runtime install {backend} first."
                    )
                    return
                self._config.setdefault("runtime", {})["active"] = backend
                cfg_runtime = self._config.get("runtime", {})
                if "path" in cfg_runtime:
                    del self._config["runtime"]["path"]
                if "name" in cfg_runtime:
                    del self._config["runtime"]["name"]
                save_config(self._config, self.config_path)
                RuntimeManager.activate_runtime(backend)
                self.r.system_message(
                    f"Active runtime switched to isolated backend: {backend}"
                )
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

                path_dir = (
                    os.path.dirname(path) if os.path.isfile(path) else path
                )
                os.environ["PATH"] = (
                    path_dir
                    + os.pathsep
                    + os.environ.get("PATH", "")
                )

                self.r.system_message(
                    f"Selected custom runtime: {name} (\u2713 active path prepended)"
                )
                self._runtime_list = self._get_custom_runtimes() + scan_runtimes()
                self._init_engine()
                self._init_agent()
                return

            if not self._runtime_list:
                self._runtime_list = self._get_custom_runtimes() + scan_runtimes()
            found = [
                r
                for r in self._runtime_list
                if name.lower() in r.name.lower()
            ]
            if found:
                rt = found[0]
                self._config.setdefault("runtime", {})["active"] = rt.provider
                cfg_runtime = self._config.get("runtime", {})
                if "path" in cfg_runtime:
                    del self._config["runtime"]["path"]
                if "name" in cfg_runtime:
                    del self._config["runtime"]["name"]
                save_config(self._config, self.config_path)
                self.r.system_message(
                    f"Active runtime: {rt.name} [{rt.provider}]"
                )
                self._runtime_list = self._get_custom_runtimes() + scan_runtimes()
                self._init_engine()
                self._init_agent()
            else:
                self.r.error(
                    f"No runtime matches: {name}. Run /runtime list"
                )

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
                self.r.error(
                    "Failed to switch runtime. Valid: auto, llama-cpp, onnx"
                )

        elif subcmd in ("help", "--help", "-h") or (not args and subcmd not in ("list",)):
            self.console.print(
                """\n  [bold]Runtime Management:[/bold]
  [cyan]/runtime list[/cyan]       \u2014 Show detected runtimes
  [cyan]/runtime scan[/cyan]       \u2014 Re-scan for runtimes
  [cyan]/runtime select <n>[/cyan] \u2014 Select active runtime by name
  [cyan]/runtime install <b>[/cyan]  \u2014 Install a runtime backend (cpu|cuda|vulkan|metal|rocm|onnx)
  [cyan]/runtime reinstall <b>[/cyan]\u2014 Force reinstall a runtime backend
  [cyan]/runtime uninstall <b>[/cyan]\u2014 Uninstall a runtime backend
  [cyan]/runtime switch <b>[/cyan]  \u2014 Switch runtime type (auto|llama-cpp|onnx)
  [cyan]/runtime add <n> <p>[/cyan] \u2014 Register a custom runtime path
  [cyan]/runtime remove <n>[/cyan]  \u2014 Remove a custom runtime\n"""
            )

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
            is_active = active_name == name
            status_str = " (active)" if is_active else ""
            customs.append(
                RuntimeInfo(
                    name=f"Custom: {name}{status_str}",
                    provider="custom",
                    available=True,
                    path=path,
                    description=f"User-provided custom runtime at {path}",
                    priority=100 if is_active else 90,
                )
            )
        return customs
