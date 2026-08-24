"""Config slash commands — /config, /theme, /color, /tui, /vim, /statusline, /permissions.

Extracted from the monolithic command_dispatcher.py.
"""

from __future__ import annotations

import sys

from nexus_agent.core.config import save_config


class ConfigCommandsMixin:
    """Mixin providing configuration-related slash command handlers."""

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
        """Set prompt bar color."""
        colors = ["purple", "blue", "green", "cyan", "yellow", "red", "white"]
        if args in colors:
            self._config.setdefault("tui", {})["prompt_color"] = args
            save_config(self._config, self.config_path)
            self.r.system_message(f"Prompt color set to {args}")
        else:
            self.r.system_message(f"Usage: /color <{'|'.join(colors)}>\nCurrent: {self._config.get('tui', {}).get('prompt_color', 'purple')}")

    def _cmd_vim(self, args: str):
        """Toggle vim-style keybindings."""
        current = self._config.get("cli", {}).get("vim_mode", False)
        if args == "on":
            new_val = True
        elif args == "off":
            new_val = False
        else:
            new_val = not current
        self._config.setdefault("cli", {})["vim_mode"] = new_val
        save_config(self._config, self.config_path)
        status = "enabled" if new_val else "disabled"
        self.r.system_message(f"Vim mode {status}")

    def _cmd_statusline(self, args: str):
        if not args:
            self.r.system_message("Usage: /statusline <comma_separated_items>")
            return
        self._config.setdefault("tui", {})["statusline_items"] = [i.strip() for i in args.split(",")]
        save_config(self._config, self.config_path)
        self.r.system_message(f"Statusline updated to: {args}")

    def _cmd_permissions(self, args: str):
        """Show or modify permission settings."""
        if not self._permissions:
            self.r.system_message("Permissions manager unavailable.")
            return
        if not args:
            mode = getattr(self._permissions, 'mode', 'ask')
            self.console.print(f"\n  [bold]Permission Mode:[/bold] {mode}")
            rules = getattr(self._permissions, 'rules', {})
            if rules:
                self.console.print("  [bold]Tool Rules:[/bold]")
                for tool_name, level in rules.items():
                    self.console.print(f"    {tool_name}: {level}")
            self.console.print("\n  [dim]Usage: /permissions <allow|ask|deny> [tool_name][/dim]")
            self.console.print()
            return
        parts = args.split(maxsplit=1)
        mode = parts[0].lower()
        if mode in ("allow", "ask", "deny") and len(parts) == 1:
            self._permissions.mode = mode
            self.r.system_message(f"Global permission mode set to {mode}")
        elif mode in ("allow", "ask", "deny") and len(parts) == 2:
            tool_name = parts[1]
            self._permissions.set_tool_permission(tool_name, mode)
            self.r.system_message(f"Permission for '{tool_name}' set to {mode}")
        else:
            self.r.system_message("Usage: /permissions <allow|ask|deny> [tool_name]")
