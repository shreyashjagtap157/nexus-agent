"""Model slash commands — /model management, switch, list, unload, interactive picker.

Extracted from the monolithic command_dispatcher.py.
"""

from __future__ import annotations

import os


class ModelCommandsMixin:
    """Mixin providing model-management slash command handlers."""

    def _cmd_model(self, args: str):
        import shlex
        try:
            parts = shlex.split(args) if args else []
        except ValueError:
            parts = args.strip().split() if args else []
        subcmd = parts[0].lower() if parts else ""

        if subcmd == "list":
            self._cmd_model_list()
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
            self.r.system_message(f"Model saved: {name} \u2192 {path}")
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
            self.r.system_message(f"Switching to model: {name}\u2026")
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

        elif subcmd == "grouped":
            self._cmd_model_list(grouped=True)
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
            items.append(("\033[31m[\u2715] Unload model\033[0m", "__unload__"))
            items.append(("\u2500" * 20, None))
        items.append(("[+] Add new model", "__add__"))
        for name in sorted_n:
            p = (self._models_db.get_path(name) or "")[:60]
            items.append((f"{name}  \033[2m\u2192 {p}\033[0m", f"__switch__:{name}"))
        if items and not items[-1][1]:
            pass
        elif items:
            items.append(("\u2500" * 20, None))
        items.append(("[\u2197] Connect provider", "__connect__"))

        sel = self._interactive_menu(items, "Select a model (\u2191\u2193 Enter Esc):")
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

    def _cmd_model_list(self, grouped: bool = True):
        """List models grouped by provider (local vs cloud)."""
        models = self._models_db.list()
        if not models:
            self.r.system_message("No stored models. Use /model add <name> <path>")
            return

        from rich.table import Table
        local_models = []
        cloud_models = []
        for name, entry in sorted(models.items()):
            if isinstance(entry, dict):
                provider = entry.get("provider", "local")
                path_or_id = entry.get("path_or_id", "")
            else:
                provider = "local"
                path_or_id = str(entry)
            if provider == "local":
                local_models.append((name, path_or_id, entry))
            else:
                cloud_models.append((name, path_or_id, entry))

        is_active = (
            self._engine
            and getattr(self._engine, "is_loaded", False)
            and hasattr(self._engine, "model_name")
        )
        active_name = self._engine.model_name if is_active else None
        active_provider = self._provider_name or "local"

        def make_table(title: str, items: list, provider_label: str = "") -> Table:
            tbl = Table(title=title, show_header=True, header_style="bold")
            tbl.add_column("", width=2)
            tbl.add_column("Name", style="cyan", max_width=35)
            tbl.add_column("Path / ID", style="dim", max_width=45)
            tbl.add_column("Provider", style="green", width=12)
            tbl.add_column("Status", width=10)
            for name, path_or_id, entry in items:
                marker = "\u25b8" if (active_name and name in str(active_name)) else " "
                prov = entry.get("provider", provider_label) if isinstance(entry, dict) else provider_label
                status = "[green]\u25cf active[/green]" if (active_name and name in str(active_name)) else "[dim]\u25cb[/dim]"
                display_path = path_or_id[:45] if path_or_id else ""
                tbl.add_row(marker, name[:35], display_path, prov, status)
            return tbl

        if grouped:
            active_provider = self._provider_name or "local"
            if local_models:
                self.console.print(make_table("Local Models", local_models, "local"))
                self.console.print()
            if cloud_models:
                self.console.print(make_table("Cloud Models", cloud_models, "cloud"))
                self.console.print()
            if not local_models and not cloud_models:
                self.r.system_message("No stored models.")
            elif not cloud_models:
                self.console.print("  [dim]No cloud providers connected. Use /connect to add one.[/dim]")
        else:
            all_items = local_models + cloud_models
            self.console.print(make_table("All Models", all_items))

        total = len(local_models) + len(cloud_models)
        self.console.print(f"  [dim]{total} model(s) total ({len(local_models)} local, {len(cloud_models)} cloud)[/dim]")

    def _cmd_unload(self, args: str):
        self._cmd_model("unload")
