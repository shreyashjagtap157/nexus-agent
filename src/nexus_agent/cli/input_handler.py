"""Input handler — keypress parsing via blessed, prompt rendering via Rich."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import warnings

from blessed import Terminal
from rich.text import Text

from nexus_agent.cli.renderer import visual_len
from nexus_agent.cli.ui_state import compute_menu_window, prompt_cursor_back_columns


_term = Terminal()

_BLESSED_EXT = {
    _term.KEY_UP: b"H",
    _term.KEY_DOWN: b"P",
    _term.KEY_LEFT: b"K",
    _term.KEY_RIGHT: b"M",
    _term.KEY_HOME: b"G",
    _term.KEY_END: b"O",
    _term.KEY_DELETE: b"S",
    _term.KEY_PGUP: b"I",
    _term.KEY_PGDOWN: b"Q",
    _term.KEY_INSERT: b"R",
}

_BLESSED_SIMPLE = {
    _term.KEY_ESCAPE: b"\x1b",
    _term.KEY_ENTER: b"\r",
    _term.KEY_BACKSPACE: b"\x7f",
    _term.KEY_TAB: b"\t",
}

_CONTROL_TO_BYTE = {
    1: b"\x01",
    2: b"\x02",
    3: b"\x03",
    4: b"\x04",
    5: b"\x05",
    6: b"\x06",
    7: b"\x07",
    8: b"\x08",
    11: b"\x0b",
    12: b"\x0c",
    14: b"\x0e",
    15: b"\x0f",
    16: b"\x10",
    18: b"\x12",
    19: b"\x13",
    20: b"\x14",
    21: b"\x15",
    22: b"\x16",
    23: b"\x17",
    24: b"\x18",
    25: b"\x19",
    26: b"\x1a",
}

_CONTROL_TO_BYTE = {
    1: b"\x01",  # Ctrl+A
    2: b"\x02",  # Ctrl+B
    3: b"\x03",  # Ctrl+C
    4: b"\x04",  # Ctrl+D
    5: b"\x05",  # Ctrl+E
    6: b"\x06",  # Ctrl+F
    7: b"\x07",  # Ctrl+G
    8: b"\x08",  # Ctrl+H / Backspace
    11: b"\x0b",  # Ctrl+K
    12: b"\x0c",  # Ctrl+L
    14: b"\x0e",  # Ctrl+N
    15: b"\x0f",  # Ctrl+O
    16: b"\x10",  # Ctrl+P
    18: b"\x12",  # Ctrl+R
    19: b"\x13",  # Ctrl+S
    20: b"\x14",  # Ctrl+T
    21: b"\x15",  # Ctrl+U
    22: b"\x16",  # Ctrl+V
    23: b"\x17",  # Ctrl+W
    24: b"\x18",  # Ctrl+X
    25: b"\x19",  # Ctrl+Y
    26: b"\x1a",  # Ctrl+Z
}


def _key_to_bytes(key, queue):
    """Convert a blessed Keypress to legacy byte sequences, queuing extension bytes."""
    if key.is_sequence:
        ext = _BLESSED_EXT.get(key.code)
        if ext:
            queue.append(ext)
            return b"\xe0"
        bs = _BLESSED_SIMPLE.get(key.code)
        if bs:
            return bs
        name = key.name or ""
        if name.startswith("KEY_F"):
            return b""
        if name == "KEY_SLEFT":
            return b"\xe0s"
        if name == "KEY_SRIGHT":
            return b"\xe0t"
        return b""
    s = str(key)
    if s:
        return s.encode("utf-8")
    if key.code:
        return _CONTROL_TO_BYTE.get(key.code, bytes([key.code]))
    return b""


class InputHandlerMixin:
    """Mixin that provides keypress reading, prompt rendering, and input management."""

    def _kbhit(self) -> bool:
        if self._key_queue:
            return True
        key = _term.inkey(timeout=0)
        if key:
            self._key_queue.append(key)
            return True
        return False

    def _read_byte(self) -> bytes:
        if not self._key_queue:
            key = _term.inkey(timeout=0.05)
            if not key:
                return b""
            self._key_queue.append(key)

        raw = self._key_queue.pop(0)
        if isinstance(raw, bytes):
            return raw
        return _key_to_bytes(raw, self._key_queue)

    def _read_input(self) -> str | None:
        value = ""
        pos = 0
        lines = 1
        cmd_menu_visible = False
        cmd_menu_filtered: list[dict] = []
        cmd_menu_idx = 0

        self._render_prompt(value, pos)

        try:
            while True:
                if not self._kbhit():
                    if self._check_resize_in_loop():
                        self._render_prompt(value, pos)
                    time.sleep(0.01)
                    continue
                ch = self._read_byte()
                if not ch:
                    continue

                # Multi-line: Alt+Enter (ESC then Enter) or Ctrl+Enter (NUL then LF)
                alt_enter = ch == b"\x1b" and self._kbhit() and self._read_byte() == b"\r"
                ctrl_enter = ch == b"\x00" and self._kbhit() and self._read_byte() == b"\x0a"
                if alt_enter or ctrl_enter:
                    value = value[:pos] + "\n" + value[pos:]
                    pos += 1
                    lines += 1
                    self._render_prompt(value, pos)
                    cmd_menu_visible, cmd_menu_filtered, cmd_menu_idx = self._update_menu(
                        value, cmd_menu_filtered, cmd_menu_idx
                    )
                    continue

                if ch == b"\r":
                    if self._drawer_active:
                        if self._sub_agents:
                            sel = self._sub_agents[self._drawer_idx]
                            self._clear_cmd_menu(cmd_menu_visible)
                            cmd_menu_visible = False
                            self._drawer_active = False
                            value = f"/skill load {sel['name']} "
                            pos = len(value)
                            self._render_prompt(value, pos)
                            continue
                    elif cmd_menu_visible and 0 <= cmd_menu_idx < len(cmd_menu_filtered):
                        sel = cmd_menu_filtered[cmd_menu_idx]
                        sel_name = sel["name"]
                        self._clear_cmd_menu(cmd_menu_visible)
                        cmd_menu_visible = False
                        if sel_name.startswith("/"):
                            self.r.system_message(f"> {sel_name}")
                            self._input_history.append(sel_name)
                            self._history_idx = -1
                            return sel_name
                        if value.rfind("@") >= 0:
                            at_idx = value.rfind("@")
                            value = value[:at_idx] + "@" + sel_name + " "
                        else:
                            value = sel_name + " "
                        pos = len(value)
                        self._render_prompt(value, pos)
                        continue
                    self._clear_cmd_menu(cmd_menu_visible)
                    self.r.console.print()
                    self._prompt_line_count = 0
                    if value.strip():
                        # Add to global input history with cap at 500
                        self._input_history.append(value.strip())
                        if len(self._input_history) > 500:
                            self._input_history = self._input_history[-500:]
                        # Add to per-session history with cap at 100
                        if hasattr(self, '_session_history'):
                            self._session_history.append(value.strip())
                            if len(self._session_history) > 100:
                                self._session_history = self._session_history[-100:]
                        self._history_idx = -1
                    return value.strip() if value.strip() else None

                elif ch == b"\x03":
                    raise KeyboardInterrupt

                elif ch == b"\x04":
                    if not value:
                        self._clear_cmd_menu(cmd_menu_visible)
                        raise EOFError
                    if pos < len(value):
                        value = value[:pos] + value[pos + 1 :]
                        self._render_prompt(value, pos)
                    continue

                elif ch == b"\x01":
                    if pos > 0:
                        pos = 0
                        self._render_prompt(value, pos)
                    continue

                elif ch == b"\x05":
                    if pos < len(value):
                        pos = len(value)
                        self._render_prompt(value, pos)
                    continue

                elif ch == b"\x0b":
                    if pos < len(value):
                        self._kill_buffer = value[pos:]
                        value = value[:pos]
                        self._render_prompt(value, pos)
                    continue

                elif ch == b"\x15":
                    if pos > 0:
                        self._kill_buffer = value[:pos]
                        value = value[pos:]
                        pos = 0
                        self._render_prompt(value, pos)
                    continue

                elif ch == b"\x19":
                    if self._kill_buffer:
                        value = value[:pos] + self._kill_buffer + value[pos:]
                        pos += len(self._kill_buffer)
                        self._render_prompt(value, pos)
                    continue

                elif ch == b"\x0c":
                    self.r.console.clear()
                    self._rebuild_welcome()
                    self._render_prompt(value, pos)
                    continue

                elif ch == b"\x12":
                    result = self._history_search()
                    if result is not None:
                        value = result
                        pos = len(value)
                        self._render_prompt(value, pos)
                    continue

                elif ch == b"\x07":
                    edited = self._external_editor(value)
                    if edited is not None:
                        value = edited
                        pos = len(value)
                        self._render_prompt(value, pos)
                    continue

                elif ch == b"\x0f":
                    self._clear_cmd_menu(cmd_menu_visible)
                    self._cmd_model_interactive()
                    self._render_prompt(value, pos)
                    continue

                elif ch == b"\x13":
                    self._clear_cmd_menu(cmd_menu_visible)
                    self._drawer_active = not self._drawer_active
                    if self._drawer_active:
                        self._drawer_idx = 0
                    self._render_prompt(value, pos)
                    continue

                elif ch == b"\t":
                    if cmd_menu_visible and 0 <= cmd_menu_idx < len(cmd_menu_filtered):
                        sel = cmd_menu_filtered[cmd_menu_idx]
                        sel_name = sel["name"]
                        if value.rfind("@") >= 0 and not sel_name.startswith("/"):
                            at_idx = value.rfind("@")
                            value = value[:at_idx] + "@" + sel_name + " "
                            pos = len(value)
                        else:
                            value = sel_name + " "
                            pos = len(value)
                        self._clear_cmd_menu(cmd_menu_visible)
                        cmd_menu_visible = False
                        self._render_prompt(value, pos)
                    continue

                elif ch in (b"\x7f", b"\x08"):
                    if pos > 0:
                        if value[pos - 1] == "\n":
                            lines -= 1
                        value = value[: pos - 1] + value[pos:]
                        pos -= 1
                        self._render_prompt(value, pos)
                        cmd_menu_visible, cmd_menu_filtered, cmd_menu_idx = self._update_menu(
                            value, cmd_menu_filtered, cmd_menu_idx
                        )
                    continue

                elif ch == b"\x16":
                    try:
                        import pyperclip

                        paste = pyperclip.paste()
                        if paste:
                            paste = paste.replace("\r\n", "\n").replace("\r", "\n")
                            if len(paste) > 10000:
                                paste = f"[Pasted text ({len(paste)} chars)]"
                            added_lines = paste.count("\n")
                            value = value[:pos] + paste + value[pos:]
                            pos += len(paste)
                            lines += added_lines
                            self._render_prompt(value, pos)
                    except (OSError, ValueError, TypeError):
                        pass
                    continue

                elif ch == b"\xe0":
                    ext = self._read_byte()
                    if ext == b"H":
                        if self._drawer_active:
                            if self._sub_agents:
                                self._drawer_idx = max(0, self._drawer_idx - 1)
                                self._render_prompt(value, pos)
                        elif cmd_menu_visible and cmd_menu_filtered:
                            cmd_menu_idx = max(0, cmd_menu_idx - 1)
                            self._render_cmd_menu(cmd_menu_filtered, cmd_menu_idx, value)
                        else:
                            hv = self._history_up()
                            if hv is not None:
                                value = hv
                                pos = len(value)
                                self._render_prompt(value, pos)
                    elif ext == b"P":
                        if self._drawer_active:
                            if self._sub_agents:
                                self._drawer_idx = min(
                                    len(self._sub_agents) - 1, self._drawer_idx + 1
                                )
                                self._render_prompt(value, pos)
                        elif cmd_menu_visible and cmd_menu_filtered:
                            cmd_menu_idx = min(len(cmd_menu_filtered) - 1, cmd_menu_idx + 1)
                            self._render_cmd_menu(cmd_menu_filtered, cmd_menu_idx, value)
                        else:
                            hv = self._history_down()
                            if hv is not None:
                                value = hv
                                pos = len(value)
                                self._render_prompt(value, pos)
                    elif ext == b"K":
                        if pos > 0:
                            pos -= 1
                            self._render_prompt(value, pos)
                    elif ext == b"M":
                        if pos < len(value):
                            pos += 1
                            self._render_prompt(value, pos)
                    elif ext == b"G":
                        if pos > 0:
                            pos = 0
                            self._render_prompt(value, pos)
                    elif ext == b"O":
                        if pos < len(value):
                            pos = len(value)
                            self._render_prompt(value, pos)
                    elif ext == b"I":
                        self.r.page_up()
                    elif ext == b"Q":
                        self.r.page_down()
                    elif ext == b"s":
                        pos = self._word_boundary_left(value, pos)
                        self._render_prompt(value, pos)
                    elif ext == b"t":
                        pos = self._word_boundary_right(value, pos)
                        self._render_prompt(value, pos)
                    elif ext == b"\x93":
                        new_pos = self._word_boundary_right(value, pos)
                        value = value[:pos] + value[new_pos:]
                        self._render_prompt(value, pos)
                    elif ext == b"\x7f":
                        new_pos = self._word_boundary_left(value, pos)
                        value = value[:new_pos] + value[pos:]
                        pos = new_pos
                        self._render_prompt(value, pos)
                    continue

                elif ch == b"\x1b":
                    if self._drawer_active:
                        self._drawer_active = False
                        self._render_prompt(value, pos)
                        continue
                    if self._cmd_menu_lines > 0 and value.startswith("/"):
                        self._clear_cmd_menu(True)
                        value = ""
                        pos = 0
                        self._render_prompt(value, pos)
                        continue
                    if self._kbhit():
                        ext = self._read_byte()
                        if ext == b"[":
                            if self._kbhit():
                                ext2 = self._read_byte()
                                if ext2 == b"2":
                                    if self._kbhit():
                                        extra = (
                                            self._read_byte()
                                            + self._read_byte()
                                            + self._read_byte()
                                        )
                                        if extra == b"00~":
                                            paste_buffer = b""
                                            while True:
                                                if self._kbhit():
                                                    p_ch = self._read_byte()
                                                    if p_ch == b"\x1b":
                                                        if self._kbhit():
                                                            p_ext1 = self._read_byte()
                                                            if p_ext1 == b"[":
                                                                if self._kbhit():
                                                                    p_ext2 = (
                                                                        self._read_byte()
                                                                        + self._read_byte()
                                                                        + self._read_byte()
                                                                        + self._read_byte()
                                                                    )
                                                                    if p_ext2 == b"201~":
                                                                        break
                                                                    else:
                                                                        paste_buffer += (
                                                                            b"\x1b[" + p_ext2
                                                                        )
                                                            else:
                                                                paste_buffer += (
                                                                    b"\x1b" + p_ext1
                                                                )
                                                    else:
                                                        paste_buffer += p_ch
                                                else:
                                                    time.sleep(0.01)
                                            try:
                                                paste = paste_buffer.decode("utf-8")
                                            except UnicodeDecodeError:
                                                paste = paste_buffer.decode(
                                                    "latin-1", errors="replace"
                                                )
                                            paste = paste.replace("\r\n", "\n").replace("\r", "\n")
                                            value = value[:pos] + paste + value[pos:]
                                            pos += len(paste)
                                            self._render_prompt(value, pos)
                                            continue
                    continue

                else:
                    byte_val = ch[0] if isinstance(ch, bytes) and len(ch) == 1 else 0
                    raw_bytes = ch
                    if byte_val >= 0xC0:
                        if byte_val < 0xE0:
                            num_extra = 1
                        elif byte_val < 0xF0:
                            num_extra = 2
                        else:
                            num_extra = 3
                        for _ in range(num_extra):
                            if self._kbhit():
                                raw_bytes += self._read_byte()
                    try:
                        char = raw_bytes.decode("utf-8")
                    except UnicodeDecodeError:
                        char = raw_bytes.decode("latin-1", errors="replace")
                    if char.isprintable() or ord(char[0]) > 127:
                        value = value[:pos] + char + value[pos:]
                        pos += len(char)
                        self._render_prompt(value, pos)
                        cmd_menu_visible, cmd_menu_filtered, cmd_menu_idx = self._update_menu(
                            value, cmd_menu_filtered, cmd_menu_idx
                        )
        finally:
            if cmd_menu_visible:
                try:
                    self._clear_cmd_menu(True)
                except (OSError, ValueError):
                    pass

    @staticmethod
    def _word_boundary_left(text: str, pos: int) -> int:
        if pos <= 0:
            return 0
        i = pos - 1
        while i > 0 and not text[i - 1].isalnum() and text[i - 1] != "_":
            i -= 1
        while i > 0 and (text[i - 1].isalnum() or text[i - 1] == "_"):
            i -= 1
        return i

    @staticmethod
    def _word_boundary_right(text: str, pos: int) -> int:
        n = len(text)
        if pos >= n:
            return n
        i = pos
        while i < n and (text[i].isalnum() or text[i] == "_"):
            i += 1
        while i < n and not text[i].isalnum() and text[i] != "_":
            i += 1
        return i

    def _render_prompt(self, value: str, pos: int):
        self._current_input_value = value
        self._current_input_pos = pos
        # 1. Move to the prompt line
        if self.state.prompt_line_y > 0:
            sys.stdout.write(_term.move_y(self.state.prompt_line_y))
        
        # 2. Clear the previous prompt area if it was multi-line
        if self.state.prompt_line_count > 1:
            for _ in range(self.state.prompt_line_count - 1):
                sys.stdout.write(_term.move_up + _term.clear_eol)
            sys.stdout.write(_term.move_up) # Move back to the first line of the prompt
        
        # 3. Render the new prompt
        prompt = Text.assemble(("> ", "bold cyan"), (value, ""))
        self.r.console.print(prompt, end="")
        
        # 4. Update the prompt line Y and count
        self.state.prompt_line_count = prompt.plain.count("\n") + 1
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=".*unknown terminal capability: 'cursor_position'.*")
                cur_y, _ = _term.cursor_position
            self.state.prompt_line_y = cur_y - (self.state.prompt_line_count - 1)
        except (ValueError, TypeError):
            pass
        
        # 5. Move cursor to the correct position within the prompt
        if pos < len(value):
            back = prompt_cursor_back_columns(value, pos, visual_len)
            sys.stdout.write(_term.move_left * back)
        
        sys.stdout.flush()
        self._render_footer()


    def _clear_cmd_menu(self, visible: bool):
        if visible and self._cmd_menu_lines > 0:
            # Clear menu lines
            sys.stdout.write(_term.move_down)
            for _ in range(self._cmd_menu_lines):
                sys.stdout.write("\r" + _term.clear_eol + _term.move_down)
            
            # Return to prompt line
            sys.stdout.write(_term.move_up * (self._cmd_menu_lines + 1))
            col = visual_len("> " + self._current_input_value[:self._current_input_pos])
            sys.stdout.write(_term.move_x(col))
            
            sys.stdout.flush()
            self._cmd_menu_lines = 0
        self._render_footer()

    def _render_footer(self, menu_height: int = 0):
        try:
            W = shutil.get_terminal_size().columns
            H = shutil.get_terminal_size().lines
        except (OSError, ValueError):
            W, H = 80, 24

        mode_str = self._current_mode.value.upper()
        effort = self._config.get("agent", {}).get("effort_level", "medium").lower()
        EFFORT_COLORS = {"low": "green", "medium": "cyan", "high": "yellow", "xhigh": "magenta", "max": "red"}
        ec = EFFORT_COLORS.get(effort, "")

        parts = []
        parts.append(Text.assemble(("Mode: ", ""), (mode_str, "bold")))
        effort_text = Text.assemble(("Effort: ", ""), (effort.upper(), f"bold {ec}")) if ec else Text.assemble(("Effort: ", ""), (effort.upper(), "bold"))
        parts.append(effort_text)
        if self._sub_agents:
            parts.append(Text(f"[{len(self._sub_agents)}]", style="cyan"))
        notif = getattr(self, "_notification", "")
        if notif and (time.time() - getattr(self, "_notification_time", 0)) < 5:
            parts.append(Text(notif, style="dim"))

        footer_text = Text("  |  ").join(parts)
        if len(footer_text.plain) > W:
            footer_text = footer_text[:W]

        drawer_h = 0
        if getattr(self, "_drawer_active", False):
            d_items = self._sub_agents
            max_visible = min(8, H - 5)
            d_count = min(len(d_items), max_visible) if d_items else 0
            drawer_h = d_count + 3
            d_start = H - drawer_h - 1

            sys.stdout.write(_term.move_y(d_start) + _term.move_x(0) + _term.clear_eol)
            self.r.console.print(Text("\u2500" * min(W, 60), style="dim"))
            sys.stdout.write(_term.move_y(d_start + 1) + _term.move_x(0) + _term.clear_eol)
            self.r.console.print(Text("  Sub-Agents", style="bold"))
            if d_items:
                visible_items = d_items[:max_visible]
                for i, agent in enumerate(visible_items):
                    name = agent.get("name", "?")
                    desc = agent.get("description", "")
                    prefix = "\u25b8" if i == self._drawer_idx else " "
                    line = Text.assemble(("  " + prefix + " ", ""), (name, "bold"))
                    if desc:
                        d_max = W - 22 - len(name)
                        if d_max > 5:
                            line.append("  " + desc[:d_max], style="dim")
                    if i == self._drawer_idx:
                        line.stylize("reverse")
                    sys.stdout.write(_term.move_y(d_start + 2 + i) + _term.move_x(0) + _term.clear_eol)
                    self.r.console.print(line[:W])
                nav_row = d_start + 2 + d_count
                sys.stdout.write(_term.move_y(nav_row) + _term.move_x(0) + _term.clear_eol)
                self.r.console.print(Text("  \u2191\u2193 navigate \u00b7 Enter use \u00b7 Esc close", style="dim"))
            else:
                sys.stdout.write(_term.move_y(d_start + 2) + _term.move_x(0) + _term.clear_eol)
                self.r.console.print(Text("  No sub-agents configured.", style="dim"))

        sys.stdout.write(_term.move_y(H - drawer_h) + _term.move_x(0) + _term.clear_eol)
        self.r.console.print(footer_text)
        
        # Move back to prompt line
        sys.stdout.write(_term.move_y(self.state.prompt_line_y))
        col = visual_len("> " + self._current_input_value[:self._current_input_pos])
        sys.stdout.write(_term.move_x(col))
        
        sys.stdout.flush()

    def _update_menu(self, value: str, filtered: list, idx: int) -> tuple:
        visible = False
        new_filtered = filtered

        if value.startswith("/"):
            prefix = value
            matches = [c for c in self.SLASH_COMMANDS if c["name"].startswith(prefix)]
            if matches:
                new_filtered = matches
                idx = 0
                visible = True
                self._render_cmd_menu(new_filtered, idx, prefix)
            else:
                new_filtered = []
                idx = 0
                visible = True
                self._render_cmd_menu([], idx, prefix)

        elif "@" in value:
            at_idx = value.rfind("@")
            if at_idx >= 0 and (at_idx == 0 or value[at_idx - 1] in (" ", "\t", "")):
                file_q = value[at_idx + 1 :]
                files = self._find_files(file_q)
                if files:
                    new_filtered = [{"name": f, "description": "", "usage": ""} for f in files]
                    idx = 0
                    visible = True
                    self._render_cmd_menu(new_filtered, idx, file_q)
                elif self._cmd_menu_lines > 0:
                    self._clear_cmd_menu(True)
                    return (False, [], 0)

        elif self._cmd_menu_lines > 0:
            self._clear_cmd_menu(True)

        return (visible, new_filtered, idx)

    def _render_cmd_menu(self, commands: list[dict], idx: int, query: str = ""):
        term_width = shutil.get_terminal_size().columns
        term_lines = shutil.get_terminal_size().lines

        max_name = min(max(len(c["name"]) for c in commands), term_width - 25) if commands else 20
        query_lower = query.lower()

        MAX_VISIBLE = min(10, max(3, term_lines - 6))
        total_items = len(commands)

        window = compute_menu_window(total_items, idx, MAX_VISIBLE)
        display_cmds = commands[window.start : window.end]
        show_indicators = total_items > MAX_VISIBLE

        lines = []
        if not commands:
            lines.append(Text("  No commands match"))
        else:
            if show_indicators:
                if window.show_above:
                    lines.append(Text(f"  \u25b2 +{window.start} more above", style="dim"))
                else:
                    lines.append(Text("  \u25b2 (start of list)", style="dim"))

            for i, cmd in enumerate(display_cmds):
                name = cmd["name"]
                desc = cmd.get("description", "")
                desc_max = term_width - max_name - 15
                padded_name = name.ljust(max_name)

                if query and padded_name.startswith(query):
                    t = Text.assemble(
                        ("  " + padded_name[:len(query)], "bold blue"),
                        (padded_name[len(query):], ""),
                    )
                else:
                    t = Text("  " + padded_name)

                if desc_max > 5 and len(desc) > desc_max:
                    desc = desc[:desc_max] + "\u2026"

                if window.start + i == idx:
                    base = Text.assemble(("      ", ""), t, ("  " + desc, "reverse"))
                else:
                    base = Text.assemble(("    ", ""), t, ("  " + desc, ""))
                lines.append(base[:term_width])

            if show_indicators:
                remaining = total_items - window.end
                if window.show_below:
                    lines.append(Text(f"  \u25bc +{remaining} more below", style="dim"))
                else:
                    lines.append(Text("  \u25bc (end of list)", style="dim"))

        nh = len(lines)
        self._cmd_menu_lines = nh

        # Move to prompt area below, clear, print, then return to prompt
        sys.stdout.write(_term.move_down + "\r" + _term.clear_eos)
        for line in lines:
            self.r.console.print(line)
        
        # Move cursor back
        sys.stdout.write(_term.move_up * (nh + 1))
        col = visual_len("> " + self._current_input_value[:self._current_input_pos])
        sys.stdout.write(_term.move_x(col))
        
        sys.stdout.flush()
        self._render_footer()

    def _clear_cmd_menu(self, visible: bool):
        if visible and self._cmd_menu_lines > 0:
            # Clear menu lines
            sys.stdout.write(_term.move_down)
            for _ in range(self._cmd_menu_lines):
                sys.stdout.write("\r" + _term.clear_eol + _term.move_down)
            
            # Return to prompt line
            sys.stdout.write(_term.move_up * (self._cmd_menu_lines + 1))
            col = visual_len("> " + self._current_input_value[:self._current_input_pos])
            sys.stdout.write(_term.move_x(col))
            
            sys.stdout.flush()
            self._cmd_menu_lines = 0
        self._render_footer()


    def _history_up(self) -> str | None:
        if not self._input_history:
            return None
        if self._history_idx < len(self._input_history) - 1:
            self._history_idx += 1
        return self._input_history[-(self._history_idx + 1)]

    def _history_down(self) -> str | None:
        if self._history_idx <= 0:
            self._history_idx = -1
            return None
        self._history_idx -= 1
        return self._input_history[-(self._history_idx + 1)]

    def _history_search(self) -> str | None:
        if not self._input_history:
            return None
        query = ""
        idx = 0
        t = Text.assemble(("(reverse-i-search)`", "bold"), (query, ""), ("': ", "bold"))
        self.r.console.print(t, end="")
        while True:
            key = _term.inkey(timeout=0.1)
            if not key:
                continue
            if key.is_sequence and key.code == _term.KEY_ENTER:
                self.r.console.print()
                if self._input_history:
                    return self._input_history[idx]
                return None
            if key.is_sequence and key.code in (_term.KEY_ESCAPE,):
                self.r.console.print()
                return None
            s = str(key)
            if s == "\x03":
                self.r.console.print()
                return None
            if s in ("\x7f", "\x08"):
                if query:
                    query = query[:-1]
                    idx = 0
            elif key.is_sequence and key.name == "KEY_UP":
                matches = [h for h in self._input_history if query.lower() in h.lower()]
                if matches and idx < len(matches) - 1:
                    idx += 1
            elif key.is_sequence and key.name == "KEY_DOWN":
                matches = [h for h in self._input_history if query.lower() in h.lower()]
                if matches and idx > 0:
                    idx -= 1
            elif s.isprintable():
                query += s
                idx = 0
            matches = [h for h in self._input_history if query.lower() in h.lower()]
            display = matches[idx] if matches and idx < len(matches) else ""
            t = Text.assemble(("(reverse-i-search)`", "bold"), (query, ""), ("': ", "bold"), (display, "dim"))
            self.r.console.print("\r" + _term.clear_eol, t, end="")

    def _external_editor(self, current: str) -> str | None:
        import shlex

        fd, tmp = tempfile.mkstemp(suffix=".md", prefix="nexus_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(current)
            editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "notepad.exe"))
            try:
                cmd = shlex.split(editor, posix=(os.name != "nt")) + [tmp]
            except ValueError:
                cmd = [editor, tmp]
            sys.stdout.write(_term.normal_cursor)
            subprocess.run(cmd)
            sys.stdout.write(_term.hidden_cursor)
            with open(tmp, encoding="utf-8") as f:
                edited = f.read()
            if edited != current:
                return edited
            return None
        except (OSError, ValueError, subprocess.CalledProcessError):
            return None
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
