"""Input handler — keypress parsing, prompt rendering, and input state management."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

from nexus_agent.cli.renderer import (
    hide_cursor,
    move_left,
    move_right,
    move_up,
    show_cursor,
    visual_len,
)

try:
    import msvcrt
except ImportError:
    msvcrt = None

try:
    import select
    import termios
    import tty
except ImportError:
    termios = None
    tty = None
    select = None


class InputHandlerMixin:
    """Mixin that provides keypress reading, prompt rendering, and input management."""

    def _kbhit(self) -> bool:
        if self._key_queue:
            return True
        if msvcrt is not None:
            try:
                return msvcrt.kbhit()
            except (OSError, ValueError):
                pass
        if select is not None:
            try:
                r, _, _ = select.select([sys.stdin], [], [], 0.0)
                return bool(r)
            except (OSError, ValueError, TypeError):
                pass
        return False

    def _read_byte(self) -> bytes:
        if self._key_queue:
            return self._key_queue.pop(0)

        if msvcrt is not None:
            try:
                return msvcrt.getch()
            except (OSError, ValueError):
                pass

        old_settings = None
        if termios is not None and tty is not None:
            try:
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
            except (OSError, ValueError):
                old_settings = None
        if old_settings is None:
            try:
                ch = sys.stdin.read(1)
                return ch.encode("utf-8") if ch else b""
            except (OSError, ValueError, UnicodeDecodeError):
                return b""

        try:
            tty.setraw(fd)
            r, _, _ = select.select([fd], [], [], 0.1)
            if not r:
                return b""
            ch = sys.stdin.read(1)
            if not ch:
                return b""
            if ch == "\x1b":
                r, _, _ = select.select([sys.stdin], [], [], 0.05)
                if r:
                    ext1 = sys.stdin.read(1)
                    if ext1 == "[":
                        r2, _, _ = select.select([sys.stdin], [], [], 0.05)
                        if r2:
                            ext2 = sys.stdin.read(1)
                            if ext2 == "A":
                                self._key_queue.extend([b"H"])
                                return b"\xe0"
                            elif ext2 == "B":
                                self._key_queue.extend([b"P"])
                                return b"\xe0"
                            elif ext2 == "C":
                                self._key_queue.extend([b"M"])
                                return b"\xe0"
                            elif ext2 == "D":
                                self._key_queue.extend([b"K"])
                                return b"\xe0"
                            elif ext2 == "H":
                                self._key_queue.extend([b"G"])
                                return b"\xe0"
                            elif ext2 == "F":
                                self._key_queue.extend([b"O"])
                                return b"\xe0"
                            elif ext2 in ("5", "6"):
                                select.select([sys.stdin], [], [], 0.02)
                                sys.stdin.read(1)
                                if ext2 == "5":
                                    self._key_queue.extend([b"I"])
                                else:
                                    self._key_queue.extend([b"Q"])
                                return b"\xe0"
                            elif ext2 == "2":
                                r3, _, _ = select.select([sys.stdin], [], [], 0.05)
                                if r3:
                                    ext3 = sys.stdin.read(1)
                                    if ext3 == "~":
                                        self._key_queue.extend([b"R"])
                                        return b"\xe0"
                                    elif ext3 == "0":
                                        sys.stdin.read(2)
                                        self._key_queue.extend([b"[", b"2", b"0", b"0", b"~"])
                                        return b"\x1b"
                            elif ext2 == "3":
                                select.select([sys.stdin], [], [], 0.02)
                                sys.stdin.read(1)
                                self._key_queue.extend([b"S"])
                                return b"\xe0"
                            elif ext2 == "1":
                                select.select([sys.stdin], [], [], 0.05)
                                extra = sys.stdin.read(4)
                                if extra == ";5D":
                                    self._key_queue.extend([b"s"])
                                    return b"\xe0"
                                elif extra == ";5C":
                                    self._key_queue.extend([b"t"])
                                    return b"\xe0"
                        return b"\x1b"
                    elif ext1 == "O":
                        r2, _, _ = select.select([sys.stdin], [], [], 0.05)
                        if r2:
                            ext2 = sys.stdin.read(1)
                            if ext2 == "A":
                                self._key_queue.extend([b"H"])
                                return b"\xe0"
                            elif ext2 == "B":
                                self._key_queue.extend([b"P"])
                                return b"\xe0"
                            elif ext2 == "C":
                                self._key_queue.extend([b"M"])
                                return b"\xe0"
                            elif ext2 == "D":
                                self._key_queue.extend([b"K"])
                                return b"\xe0"
                        return b"\x1b"
                    else:
                        self._key_queue.extend([ext1.encode("utf-8")])
                        return b"\x1b"
                return b"\x1b"
            return ch.encode("utf-8")
        except (OSError, ValueError, TypeError, UnicodeDecodeError):
            return b""
        finally:
            if old_settings is not None and termios is not None:
                try:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                except (OSError, ValueError):
                    pass

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

                multi_line = (ch == b"\x00" and self._kbhit() and self._read_byte() == b"\x0a")
                if multi_line:
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
                            sys.stdout.write(f"\r❯ {sel_name} \n")
                            sys.stdout.flush()
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
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                    self._prompt_line_count = 0
                    if value.strip():
                        self._input_history.append(value.strip())
                        self._history_idx = -1
                    return value.strip() if value.strip() else None

                elif ch == b"\x03":
                    raise KeyboardInterrupt

                elif ch == b"\x04":
                    if not value:
                        self._clear_cmd_menu(cmd_menu_visible)
                        raise EOFError
                    if pos < len(value):
                        value = value[:pos] + value[pos + 1:]
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
                    sys.stdout.write("\033[2J")
                    self.r.rebuild_welcome(self._tokens, self._metrics, model_status=None, resource_info="")
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
                        value = value[:pos - 1] + value[pos:]
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
                            paste = paste.replace('\r\n', '\n').replace('\r', '\n')
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
                                self._render_footer()
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
                                self._drawer_idx = min(len(self._sub_agents) - 1, self._drawer_idx + 1)
                                self._render_footer()
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
                            sys.stdout.write(move_left(1))
                            sys.stdout.flush()
                    elif ext == b"M":
                        if pos < len(value):
                            pos += 1
                            sys.stdout.write(move_right(1))
                            sys.stdout.flush()
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
                                        extra = self._read_byte() + self._read_byte() + self._read_byte()
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
                                                                    p_ext2 = self._read_byte() + self._read_byte() + self._read_byte() + self._read_byte()
                                                                    if p_ext2 == b"201~":
                                                                        break
                                                                    else:
                                                                        paste_buffer += b"\x1b[" + p_ext2
                                                            else:
                                                                paste_buffer += b"\x1b" + p_ext1
                                                    else:
                                                        paste_buffer += p_ch
                                                else:
                                                    time.sleep(0.01)
                                            try:
                                                paste = paste_buffer.decode("utf-8")
                                            except UnicodeDecodeError:
                                                paste = paste_buffer.decode("latin-1", errors="replace")
                                            paste = paste.replace('\r\n', '\n').replace('\r', '\n')
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
        while i > 0 and not text[i - 1].isalnum() and text[i - 1] != '_':
            i -= 1
        while i > 0 and (text[i - 1].isalnum() or text[i - 1] == '_'):
            i -= 1
        return i

    @staticmethod
    def _word_boundary_right(text: str, pos: int) -> int:
        n = len(text)
        if pos >= n:
            return n
        i = pos
        while i < n and (text[i].isalnum() or text[i] == '_'):
            i += 1
        while i < n and not text[i].isalnum() and text[i] != '_':
            i += 1
        return i

    def _render_prompt(self, value: str, pos: int):
        if self._prompt_line_count > 1:
            for _ in range(self._prompt_line_count - 1):
                sys.stdout.write(move_up(1))
        sys.stdout.write("\r\033[J")

        prompt = f"\033[1;36m❯\033[0m {value} "
        self._prompt_line_count = prompt.count("\n") + 1
        sys.stdout.write(prompt)

        if pos < len(value):
            visual_pos = visual_len(value[:pos])
            sys.stdout.write(move_left(visual_pos))
        sys.stdout.flush()
        self._render_footer()

    def _clear_cmd_menu(self, visible: bool):
        if visible and self._cmd_menu_lines > 0:
            sys.stdout.write("\033[s")
            for _ in range(self._cmd_menu_lines + 1):
                sys.stdout.write("\033[1B\r\033[2K")
            sys.stdout.write("\033[u")
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
        EFFORT_COLORS = {"low": "32", "medium": "36", "high": "33", "xhigh": "35", "max": "31"}
        ec = EFFORT_COLORS.get(effort, "0")

        parts = [f"Mode: \033[1m{mode_str}\033[0m"]
        parts.append(f"Effort: \033[1;{ec}m{effort.upper()}\033[0m")
        if self._sub_agents:
            parts.append(f"\033[36m⊞ {len(self._sub_agents)}‖")
        notif = getattr(self, '_notification', '')
        if notif and (time.time() - getattr(self, '_notification_time', 0)) < 5:
            parts.append(f"\033[2m{notif}\033[0m")

        footer = "  │  ".join(parts)
        if len(footer) > W:
            footer = footer[:W]

        sys.stdout.write("\033[s")

        drawer_h = 0
        if getattr(self, '_drawer_active', False):
            d_items = self._sub_agents
            max_visible = min(8, H - 5)
            d_count = min(len(d_items), max_visible) if d_items else 0
            drawer_h = d_count + 3
            d_start = H - drawer_h - 1

            sys.stdout.write(f"\033[{d_start};1H\033[2K\033[2m{'─' * min(W, 60)}\033[0m")
            sys.stdout.write(f"\033[{d_start + 1};1H\033[2K  \033[1mSub-Agents\033[0m")
            if d_items:
                visible_items = d_items[:max_visible]
                for i, agent in enumerate(visible_items):
                    name = agent.get("name", "?")
                    desc = agent.get("description", "")
                    prefix = "▸" if i == self._drawer_idx else " "
                    line = f"  {prefix} \033[1m{name}\033[0m"
                    if desc:
                        d_max = W - 22 - len(name)
                        if d_max > 5:
                            line += f"  \033[2m{desc[:d_max]}\033[0m"
                    if i == self._drawer_idx:
                        line = f"\033[7m{line}\033[0m"
                    sys.stdout.write(f"\033[{d_start + 2 + i};1H\033[2K{line[:W]}")
                nav_row = d_start + 2 + d_count
                sys.stdout.write(f"\033[{nav_row};1H\033[2K  \033[2m↑↓ navigate · Enter use · Esc close\033[0m")
            else:
                sys.stdout.write(f"\033[{d_start + 2};1H\033[2K  \033[2mNo sub-agents configured.\033[0m")

        sys.stdout.write(f"\033[{H - drawer_h};1H\033[2K{footer}")
        sys.stdout.write("\033[u")
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
            elif self._cmd_menu_lines > 0:
                self._clear_cmd_menu(True)
                return (False, [], 0)

        elif "@" in value:
            at_idx = value.rfind("@")
            if at_idx >= 0 and (at_idx == 0 or value[at_idx - 1] in (" ", "\t", "")):
                file_q = value[at_idx + 1:]
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

        if total_items <= MAX_VISIBLE:
            start_idx = 0
            end_idx = total_items
            display_cmds = commands
            show_indicators = False
        else:
            start_idx = idx - MAX_VISIBLE // 2
            start_idx = max(0, min(start_idx, total_items - MAX_VISIBLE))
            end_idx = start_idx + MAX_VISIBLE
            display_cmds = commands[start_idx:end_idx]
            show_indicators = True

        lines = []
        if not commands:
            lines.append("  No commands match")
        else:
            if show_indicators:
                if start_idx > 0:
                    lines.append(f"  \033[2m▲ +{start_idx} more above\033[0m")
                else:
                    lines.append("  \033[2m▲ (start of list)\033[0m")

            for i, cmd in enumerate(display_cmds):
                name = cmd["name"]
                desc = cmd.get("description", "")
                desc_max = term_width - max_name - 15
                padded_name = name.ljust(max_name)
                if desc_max > 5 and len(desc) > desc_max:
                    desc = desc[:desc_max] + "…"

                if start_idx + i == idx:
                    base = f"      \033[7m{padded_name}\033[0m  {desc}"
                else:
                    base = f"    {padded_name}  {desc}"
                lines.append(base[:term_width])

            if show_indicators:
                remaining = total_items - end_idx
                if remaining > 0:
                    lines.append(f"  \033[2m▼ +{remaining} more below\033[0m")
                else:
                    lines.append("  \033[2m▼ (end of list)\033[0m")

        nh = len(lines)
        self._cmd_menu_lines = nh

        sys.stdout.write("\033[s")
        try:
            sys.stdout.write("\033[1B\r\033[J")
            sys.stdout.write("\n".join(lines))
        finally:
            sys.stdout.write("\033[u")
            sys.stdout.flush()
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
        sys.stdout.write(f"\r\x1b[K(reverse-i-search)`{query}': ")
        sys.stdout.flush()
        while True:
            while not self._kbhit():
                time.sleep(0.01)
            ch = self._read_byte()
            if not ch:
                continue
            if ch == b"\r":
                sys.stdout.write("\n")
                sys.stdout.flush()
                if self._input_history:
                    return self._input_history[idx]
                return None
            elif ch in (b"\x1b", b"\x03"):
                sys.stdout.write("\n")
                sys.stdout.flush()
                return None
            elif ch in (b"\x7f", b"\x08"):
                if query:
                    query = query[:-1]
                    idx = 0
            elif ch == b"\x12":
                matches = [h for h in self._input_history
                           if query.lower() in h.lower()]
                if matches and idx < len(matches) - 1:
                    idx += 1
            elif ch == b"\x08":
                matches = [h for h in self._input_history
                           if query.lower() in h.lower()]
                if matches and idx > 0:
                    idx -= 1
            else:
                try:
                    char = ch.decode("utf-8")
                except UnicodeDecodeError:
                    char = ch.decode("latin-1", errors="replace")
                if char.isprintable():
                    query += char
                    idx = 0
            matches = [h for h in self._input_history
                       if query.lower() in h.lower()]
            display = matches[idx] if matches and idx < len(matches) else ""
            sys.stdout.write(f"\r\x1b[K(reverse-i-search)`{query}': {display}")
            sys.stdout.flush()

    def _external_editor(self, current: str) -> str | None:
        import shlex
        import tempfile
        fd, tmp = tempfile.mkstemp(suffix=".md", prefix="nexus_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(current)
            editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "notepad.exe"))
            try:
                cmd = shlex.split(editor, posix=(os.name != "nt")) + [tmp]
            except ValueError:
                cmd = [editor, tmp]
            sys.stdout.write(show_cursor())
            subprocess.run(cmd)
            sys.stdout.write(hide_cursor())
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
