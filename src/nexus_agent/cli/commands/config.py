"""Config slash commands — /config, /theme, /color, /permissions, etc."""

from __future__ import annotations

from nexus_agent.cli.commands._base import BaseCommands
from nexus_agent.core.config import save_config


class ConfigCommands(BaseCommands):
    """Mixin providing configuration slash command handlers."""


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


    def _cmd_tui(self, args: str):
        if args == "fullscreen":
            self.r.enter_fullscreen()
        elif args == "inline":
            self.r.exit_fullscreen()
        else:
            self.r.toggle_fullscreen()
        mode = "fullscreen" if getattr(self.r, '_is_fullscreen', False) else "inline"
        self.r.system_message(f"TUI: {mode}")


    def _cmd_theme(self, args: str):
        if args in ("dark", "light"):
            self.r.set_theme(args)
            self._config["theme"] = args
            save_config(self._config, self.config_path)
            self.r.system_message(f"Theme set to {args}")
        else:
            self.r.system_message("Usage: /theme [dark|light]")


    def _cmd_color(self, args: str):
        if not args:
            self.r.system_message("Usage: /color <hex_color>")
            return
        self._config.setdefault("tui", {})["prompt_color"] = args
        save_config(self._config, self.config_path)
        if hasattr(self.r, 'update_prompt_color'):
            self.r.update_prompt_color(args)
        self.r.system_message(f"Prompt bar color set to {args}")


    def _cmd_vim(self, args: str):
        current = self._config.get("tui", {}).get("vim_mode", False)
        new_mode = not current
        self._config.setdefault("tui", {})["vim_mode"] = new_mode
        save_config(self._config, self.config_path)
        if hasattr(self.r, 'update_vim_mode'):
            self.r.update_vim_mode(new_mode)
        self.r.system_message(f"Vim mode {'enabled' if new_mode else 'disabled'}")


    def _cmd_statusline(self, args: str):
        if not args:
            self.r.system_message("Usage: /statusline <comma_separated_items>")
            return
        self._config.setdefault("tui", {})["statusline_items"] = [i.strip() for i in args.split(",")]
        save_config(self._config, self.config_path)
        self.r.system_message(f"Statusline updated to: {args}")



    def _cmd_permissions(self, args: str):
        if not self._permissions:
            self.r.system_message("Permissions manager unavailable.")
            return
        self.r.system_message("Permissions management: Not yet implemented.")
