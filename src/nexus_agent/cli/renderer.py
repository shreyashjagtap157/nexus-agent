# TODO: Split into renderer/ subpackage
"""Claude Code-style terminal renderer for NexusAgent.

Replicates the exact rendering of Claude Code CLI:
- REPL-style inline rendering with input at bottom
- Animated spinner with rotating verbs (Warping, Discombobulating, etc.)
- Status bar with model, mode, tokens, context window %
- Slash command dropdown with autocomplete
- @-mention file autocomplete
- Collapsible tool call sections
- Permission dialogs
- Token streaming display
- Sub-agent status display
"""

from __future__ import annotations

import logging
import math
import os
import random
import re
import shutil
import sys
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from rich.console import Console
from rich.markdown import Markdown

from nexus_agent.cli.theme import DARK_THEME, LIGHT_THEME

logger = logging.getLogger(__name__)

try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

try:
    import ctypes
    HAS_CTYPES = True
except ImportError:
    HAS_CTYPES = False


def enable_vt_processing():
    """Enable ENABLE_VIRTUAL_TERMINAL_PROCESSING on Windows Console."""
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except (OSError, AttributeError, ValueError):
            pass
        try:
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except (OSError, AttributeError, ValueError):
            pass
    if sys.platform == "win32" and HAS_CTYPES:
        try:
            kernel32 = ctypes.windll.kernel32
            hStdout = kernel32.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(hStdout, ctypes.byref(mode)):
                mode.value |= 0x0004 | 0x0002  # VT processing | Enable output processing
                kernel32.SetConsoleMode(hStdout, mode)
        except (OSError, AttributeError, ValueError):
            pass


CSI = "\033["
OSC = "\033]"
BEL = "\x07"
ST = "\033\\"

_RICH_TAG = re.compile(r'\[/?\w+(?:=[^\]]*?)?\]')
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)')

def visual_len(text: str) -> int:
    no_markup = _RICH_TAG.sub("", text)
    plain = _ANSI_RE.sub('', no_markup)
    width = 0
    for ch in plain:
        if unicodedata.east_asian_width(ch) in ('W', 'F'):
            width += 2
        else:
            width += 1
    return width


def truncate_visual(text: str, max_width: int) -> str:
    if visual_len(text) <= max_width:
        return text
    # Binary search for correct truncation point to avoid O(n²)
    chars = list(text)
    lo, hi = 0, len(chars)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if visual_len("".join(chars[:mid])) <= max_width:
            lo = mid
        else:
            hi = mid - 1
    return "".join(chars[:lo])


def hex_to_ansi(hex_str: str) -> str:
    h = hex_str.lstrip("#")
    if len(h) != 6:
        return ""
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return ""
    return f"\033[38;2;{r};{g};{b}m"


def strip_markup(text: str) -> str:
    return _RICH_TAG.sub("", text)


def save_cursor() -> str:
    return CSI + "s"

def restore_cursor() -> str:
    return CSI + "u"

def hide_cursor() -> str:
    return CSI + "?25l"

def show_cursor() -> str:
    return CSI + "?25h"

def move_up(n: int = 1) -> str:
    return CSI + f"{n}A"

def move_down(n: int = 1) -> str:
    return CSI + f"{n}B"

def move_right(n: int = 1) -> str:
    return CSI + f"{n}C"

def move_left(n: int = 1) -> str:
    return CSI + f"{n}D"

def move_to(col: int = 0, row: int = 0) -> str:
    return CSI + f"{row};{col}H"

def clear_line() -> str:
    return CSI + "2K"

def clear_to_end() -> str:
    return CSI + "0J"

def clear_screen() -> str:
    return CSI + "2J"

def erase_line() -> str:
    return f"\r{clear_line()}"

def alternate_screen() -> str:
    return CSI + "?1049h"

def main_screen() -> str:
    return CSI + "?1049l"

def enable_synchronized() -> str:
    return CSI + "?2026h"

def disable_synchronized() -> str:
    return CSI + "?2026l"

def enable_mouse() -> str:
    """Enable X10 + any-event mouse tracking."""
    return CSI + "?1000h" + CSI + "?1003h" + CSI + "?1006h"

def disable_mouse() -> str:
    """Disable mouse tracking."""
    return CSI + "?1006l" + CSI + "?1003l" + CSI + "?1000l"

def enable_bracketed_paste() -> str:
    """Enable bracketed paste mode — wraps pasted text in escape sequences."""
    return CSI + "?2004h"

def disable_bracketed_paste() -> str:
    """Disable bracketed paste mode."""
    return CSI + "?2004l"

def set_title(title: str) -> str:
    sanitized = title.replace("\x07", "").replace("\x1b", "")
    return f"{OSC}0;{sanitized}{ST}"

def set_scroll_region(top: int, bottom: int) -> str:
    return CSI + f"{top};{bottom}r"


def detect_dark_mode() -> bool:
    colorfgbg = os.environ.get("COLORFGBG", "")
    if colorfgbg and ";" in colorfgbg:
        try:
            fg, bg = colorfgbg.split(";", 1)
            bg_val = int(bg)
            if bg_val in (7, 11, 14, 15):
                return False
        except ValueError:
            pass
    return True


class Verbosity(Enum):
    NORMAL = "normal"
    VERBOSE = "verbose"
    QUIET = "quiet"


@dataclass
class PerRequest:
    """Per-request token + timing tracking, like Claude Code."""
    def __init__(self):
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.elapsed: float = 0.0
        self._start: float = 0.0

    def begin(self) -> None:
        self._start = time.time()
        self.input_tokens = 0
        self.output_tokens = 0

    def end(self) -> None:
        if self._start:
            self.elapsed = time.time() - self._start

    def display(self) -> str:
        parts = []
        if self.input_tokens > 0:
            parts.append(f"\033[2mIn:\033[0m{self.input_tokens:,}")
        if self.output_tokens > 0:
            parts.append(f"\033[2mOut:\033[0m{self.output_tokens:,}")
        if self.elapsed > 0:
            if self.elapsed >= 60:
                m, s = divmod(int(self.elapsed), 60)
                parts.append(f"\033[2mTime:\033[0m{m}m{s:02d}s")
            else:
                parts.append(f"\033[2mTime:\033[0m{self.elapsed:.1f}s")
        return "  ".join(parts) if parts else ""


class TokenUsage:
    """Token usage tracking — matches Claude Code's display."""
    def __init__(self):
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.cache_creation: int = 0
        self.cache_read: int = 0
        self.total_input: int = 0
        self.total_output: int = 0
        self.context_window: int = 200000
        self.provider_name: str = "local"
        self.current_request = PerRequest()
        self.last_request = PerRequest()

    # Per-provider pricing: (input_per_1m, output_per_1m) in USD
    PRICING: dict[str, tuple[float, float]] = {
        "anthropic": (3.00, 15.00),
        "openai": (2.50, 10.00),
        "google": (1.25, 5.00),
        "groq": (0.59, 0.79),
        "deepseek": (0.14, 0.28),
        "openrouter": (3.00, 15.00),  # Varies by model
        "mistral": (2.00, 6.00),
        "fireworks": (0.90, 0.90),
        "together": (0.88, 0.88),
        "perplexity": (1.00, 1.00),
        "nvidia": (0.00, 0.00),  # Free tier
        "local": (0.00, 0.00),
        "ollama": (0.00, 0.00),
    }

    @property
    def total(self) -> int:
        return self.total_input + self.total_output

    @property
    def estimated_cost(self) -> float:
        """Calculate estimated cost based on provider pricing."""
        pricing = self.PRICING.get(self.provider_name, (0.0, 0.0))
        input_cost = self.total_input / 1_000_000 * pricing[0]
        output_cost = self.total_output / 1_000_000 * pricing[1]
        return input_cost + output_cost

    def display_short(self) -> str:
        inp = self.total_input or self.input_tokens
        out = self.total_output or self.output_tokens
        return f"\u2191{inp:,}|\u2193{out:,}" if inp or out else ""

    def display_request(self) -> str:
        """Display the last request's token usage and timing."""
        return self.last_request.display()

    def display_context(self) -> str:
        """Context bar format like Claude Code's visual bar."""
        ctx = self.context_window or 200000
        pct = min(100, int(self.total / ctx * 100)) if self.total > 0 else 0
        bar_len = 10
        filled = int(pct / 100 * bar_len)
        bar = "\u2501" * filled + "\u2500" * (bar_len - filled)
        color = "green" if pct < 50 else "yellow" if pct < 80 else "red"
        if self.last_request.elapsed > 0:
            time_str = self._fmt_time(self.last_request.elapsed)
            return f"[dim]{time_str}[/dim] Ctx: [{color}]{bar}[/{color}] {pct}%"
        return f"Ctx: [{color}]{bar}[/{color}] {pct}%"

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        if seconds >= 60:
            m, s = divmod(int(seconds), 60)
            return f"{m}m{s:02d}s"
        return f"{seconds:.1f}s"

    def detail_str(self) -> str:
        """Detailed breakdown for /context command."""
        ctx = self.context_window or 200000
        pct = min(100, int(self.total / ctx * 100))
        bar_len = 30
        filled = int(pct / 100 * bar_len)
        bar = "\u2588" * filled + "\u2591" * (bar_len - filled)
        cost = self.estimated_cost
        lines = [
            f"  Input tokens:     {self.total_input:,}",
            f"  Output tokens:    {self.total_output:,}",
            f"  Cache creation:   {self.cache_creation:,}",
            f"  Cache read:       {self.cache_read:,}",
            f"  Total:            {self.total:,} / {ctx:,} ({pct}%)",
        ]
        if self.last_request.elapsed > 0:
            lines.append(f"  Last request:     {self._fmt_time(self.last_request.elapsed)}")
        if self.last_request.input_tokens or self.last_request.output_tokens:
            lines.append(f"  Last I/O:         \u2191{self.last_request.input_tokens:,} \u2193{self.last_request.output_tokens:,}")
        lines.append(f"  Estimated cost:   ${cost:.4f}")
        lines.append(f"  [{bar}] {pct}%")
        return "\n".join(lines)

    def display_cost(self, kind: str = "all") -> str:
        pricing = self.PRICING.get(self.provider_name, (0.003, 0.015))
        if kind == "input":
            return f"${self.total_input / 1_000_000 * pricing[0]:.4f}"
        elif kind == "output":
            return f"${self.total_output / 1_000_000 * pricing[1]:.4f}"
        return f"${self.estimated_cost:.4f}"


class ContextBreakdown:
    """Context breakdown like Claude Code's /context command.

    Supports both hardcoded defaults (for when no agent is loaded) and
    dynamic updates from actual system prompt, tools, and provider data.
    """
    def __init__(self, max_context: int = 200000):
        self.system_prompt = 2600
        self.system_tools = 17600
        self.mcp_tools = 1200
        self.mcp_deferred = 5900
        self.tools_deferred = 7300
        self.memory_files = 3300
        self.skills = 333
        self.messages = 0
        self.auto_compact_buffer = 33000
        self.max_context = max_context

    def update_from_agent(self, agent: Any = None, engine: Any = None,
                          mcp_tools_count: int = 0, skills_count: int = 0):
        """Recalculate context breakdown from actual agent/engine data.

        Args:
            agent: The AgentLoop instance (for system prompt, tool definitions).
            engine: The LLM provider (for context window size, token counting).
            mcp_tools_count: Number of MCP tool definitions.
            skills_count: Number of loaded skills.
        """
        if engine:
            caps = getattr(engine, 'get_capabilities', lambda: None)()
            if caps and hasattr(caps, 'max_context_length'):
                self.max_context = caps.max_context_length
            # Try to get actual token count for system prompt
            if agent and hasattr(agent, '_build_system_prompt'):
                try:
                    sys_prompt = agent._build_system_prompt()
                    self.system_prompt = engine.count_tokens(sys_prompt)
                except (AttributeError, TypeError, ValueError):
                    pass
            # Calculate tools schema tokens
            if agent and hasattr(agent, '_tool_definitions'):
                try:
                    import json as _json
                    tools_text = _json.dumps([td.to_dict() for td in agent._tool_definitions])
                    self.system_tools = engine.count_tokens(tools_text)
                except (TypeError, AttributeError, ValueError):
                    pass
            # Calculate message tokens
            if agent and hasattr(agent, 'messages') and agent.messages:
                try:
                    self.messages = engine.count_message_tokens(agent.messages)
                except (AttributeError, TypeError, ValueError):
                    pass

        # MCP and skills
        self.mcp_tools = mcp_tools_count * 200  # ~200 tokens per tool schema
        self.skills = skills_count * 50  # ~50 tokens per skill reference

        # Auto-compact buffer scales with context window
        self.auto_compact_buffer = int(self.max_context * 0.15)

    @property
    def free_space(self) -> int:
        used = (self.system_prompt + self.system_tools + self.mcp_tools +
                self.mcp_deferred + self.tools_deferred + self.memory_files +
                self.skills + self.messages + self.auto_compact_buffer)
        return max(0, self.max_context - used)

    def render(self, token_usage: TokenUsage | None = None) -> str:
        if token_usage:
            self.messages = token_usage.total

        total_used = self.max_context - self.free_space
        pct = min(100, int(total_used / self.max_context * 100))

        def row(label: str, tokens: int, show_pct: bool = True) -> str:
            p = f" ({tokens / self.max_context * 100:.1f}%)" if show_pct else ""
            return f"  {label:<22} {tokens:>6,}{p}"

        bar_len = 25
        filled = int(pct / 100 * bar_len)
        bar = "▓" * filled + "░" * (bar_len - filled)
        color = "green" if pct < 50 else "yellow" if pct < 80 else "red"

        lines = [
            "Context Window Usage",
            "─" * 45,
            row("System prompt", self.system_prompt),
            row("System tools", self.system_tools),
            row("MCP tools", self.mcp_tools),
            row("MCP tools (deferred)", self.mcp_deferred),
            row("System tools (deferred)", self.tools_deferred),
            row("Memory files", self.memory_files),
            row("Skills", self.skills),
            row("Messages", self.messages),
            row("Free space", self.free_space, False),
            row("Autocompact buffer", self.auto_compact_buffer, False),
            "─" * 45,
            f"  [{color}]{bar}[/{color}] {pct}% used ({total_used:,} of {self.max_context:,})",
        ]
        return "\n".join(lines)


# ── Spinner Verbs ──
# Claude Code's exact spinner verb sets
SPINNER_VERBS_PRESENT = [
    "Warping", "Discombobulating", "Reticulating", "Bamboozling",
    "Thinking", "Processing", "Analyzing", "Reasoning",
    "Examining", "Computing", "Crunching", "Deciphering",
    "Deliberating", "Determining", "Elucidating", "Evaluating",
    "Formulating", "Generating", "Germinating", "Hatching",
    "Ideating", "Inferring", "Mulling", "Musing",
    "Noodling", "Percolating", "Perusing", "Pondering",
    "Ruminating", "Scheming", "Simmering", "Synthesizing",
    "Tinkering", "Unfurling", "Unravelling", "Whirring",
    "Wrangling", "Baking", "Brewing", "Cooking",
    "Crafting", "Creating", "Forging", "Shaping",
    "Weaving", "Assembling", "Compiling", "Concocting",
    "Conjuring", "Constructing", "Engineering", "Fabricating",
    "Building", "Implementing", "Coding", "Architecting",
    "Designing", "Hacking", "Cobbling", "Patching",
    "Fixing", "Resolving", "Investigating", "Exploring",
    "Probing", "Scanning", "Surveying", "Inspecting",
    "Reading", "Parsing", "Indexing", "Searching",
    "Hunting", "Tracking", "Digging", "Spelunking",
    "Tracing", "Aligning", "Calibrating", "Fine-tuning",
    "Polishing", "Refining", "Coordinating", "Harmonizing",
    "Integrating", "Merging", "Unifying", "Envisioning",
    "Imagining", "Conceiving", "Blueprinting", "Strategizing",
    "Validating", "Verifying", "Debugging", "Testing",
    "Reviewing", "Distilling", "Refracting", "Iterating",
]

SPINNER_VERBS_PAST = [
    "Warped", "Discombobulated", "Reticulated", "Bamboozled",
    "Thought", "Processed", "Analyzed", "Reasoned",
    "Examined", "Computed", "Crunched", "Deciphered",
    "Deliberated", "Determined", "Elucidated", "Evaluated",
    "Formulated", "Generated", "Germinated", "Hatched",
    "Ideated", "Inferred", "Mulled", "Mused",
    "Noodled", "Percolated", "Perused", "Pondered",
    "Ruminated", "Schemed", "Simmered", "Synthesized",
    "Tinkered", "Unfurled", "Unravelled", "Whirred",
    "Wrangled", "Baked", "Brewed", "Cooked",
    "Crafted", "Created", "Forged", "Shaped",
    "Wove", "Assembled", "Compiled", "Concocted",
    "Conjured", "Constructed", "Engineered", "Fabricated",
    "Built", "Implemented", "Coded", "Architected",
    "Designed", "Hacked", "Cobbled", "Patched",
    "Fixed", "Resolved", "Investigated", "Explored",
    "Probed", "Scanned", "Surveyed", "Inspected",
    "Read", "Parsed", "Indexed", "Searched",
    "Hunted", "Tracked", "Dug", "Spelunked",
    "Traced", "Aligned", "Calibrated", "Fine-tuned",
    "Polished", "Refined", "Coordinated", "Harmonized",
    "Integrated", "Merged", "Unified", "Envisioned",
    "Imagined", "Conceived", "Blueprinted", "Strategized",
    "Validated", "Verified", "Debugged", "Tested",
    "Reviewed", "Distilled", "Refracted", "Iterated",
]

# Rotating infinity symbol frames + gradient color stops
# Each frame is a step of clockwise rotation
# Using segments of ∞ at different rotation angles for smooth animation
INFINITY_FRAMES = ["∞", "∝", "≈", "∼", "∼", "≈", "∝", "∞", "∝", "≈", "∼", "∼", "≈", "∝"]
INFINITY_COLORS_PURPLE = [
    "\033[38;2;180;80;220m",  # deep purple
    "\033[38;2;160;100;230m",
    "\033[38;2;140;120;240m",
    "\033[38;2;120;140;250m",
    "\033[38;2;140;120;240m",
    "\033[38;2;160;100;230m",
    "\033[38;2;180;80;220m",
    "\033[38;2;200;60;210m",
    "\033[38;2;180;80;220m",
    "\033[38;2;160;100;230m",
    "\033[38;2;140;120;240m",
    "\033[38;2;120;140;250m",
    "\033[38;2;140;120;240m",
    "\033[38;2;160;100;230m",
]
INFINITY_COLORS_GOLD = [
    "\033[38;2;255;215;0m",    # gold
    "\033[38;2;255;200;50m",
    "\033[38;2;255;185;100m",
    "\033[38;2;255;170;150m",
    "\033[38;2;255;185;100m",
    "\033[38;2;255;200;50m",
    "\033[38;2;255;215;0m",
    "\033[38;2;255;230;0m",
    "\033[38;2;255;215;0m",
    "\033[38;2;255;200;50m",
    "\033[38;2;255;185;100m",
    "\033[38;2;255;170;150m",
    "\033[38;2;255;185;100m",
    "\033[38;2;255;200;50m",
]
INFINITY_COLORS_SILVER = [
    "\033[38;2;192;192;192m",  # silver
    "\033[38;2;200;200;210m",
    "\033[38;2;208;208;220m",
    "\033[38;2;216;216;230m",
    "\033[38;2;208;208;220m",
    "\033[38;2;200;200;210m",
    "\033[38;2;192;192;192m",
    "\033[38;2;184;184;184m",
    "\033[38;2;192;192;192m",
    "\033[38;2;200;200;210m",
    "\033[38;2;208;208;220m",
    "\033[38;2;216;216;230m",
    "\033[38;2;208;208;220m",
    "\033[38;2;200;200;210m",
]
_RESET = "\033[0m"

TOOL_VERBS_PRESENT = [
    "Reading", "Writing", "Searching", "Executing",
    "Fetching", "Parsing", "Scanning", "Grepping",
    "Editing", "Patching", "Applying", "Running",
]

TOOL_VERBS_PAST = [
    "Read", "Wrote", "Searched", "Executed",
    "Fetched", "Parsed", "Scanned", "Grep'd",
    "Edited", "Patched", "Applied", "Ran",
]


class SpinnerWidget:
    """Animated spinner with rotating ∞ symbol — matches Claude Code's spinner."""

    def __init__(self):
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._current_verb = ""
        self._start_time = 0.0
        self._frame_idx = 0
        self._shown = False
        self._progress = ""
        self._color = "bold"
        self._line_count = 1

    def start(self, verb: str | None = None):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._start_time = time.time()
            self._frame_idx = 0
            self._shown = False
            self._current_verb = verb or random.choice(SPINNER_VERBS_PRESENT)
            self._progress = ""
            self._color = "bold"
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self) -> tuple[str, float] | None:
        verb = None
        elapsed = 0.0
        with self._lock:
            if not self._running:
                return None
            self._running = False
            elapsed = time.time() - self._start_time
            verb = self._current_verb
        if self._thread:
            self._thread.join(timeout=0.5)
        self._clear()
        return verb, elapsed

    def update_verb(self, verb: str):
        with self._lock:
            self._current_verb = verb

    def set_progress(self, progress: str):
        with self._lock:
            self._progress = progress

    def set_color(self, color: str):
        with self._lock:
            self._color = color

    def _run(self):
        while True:
            with self._lock:
                if not self._running:
                    break
                frame = INFINITY_FRAMES[self._frame_idx % len(INFINITY_FRAMES)]
                elapsed = time.time() - self._start_time
                verb = self._current_verb
                progress = self._progress
                self._frame_idx += 1

                if elapsed < 60:
                    elapsed_str = f"{elapsed:.0f}s"
                else:
                    elapsed_str = f"{elapsed / 60:.0f}m {elapsed % 60:.0f}s"

                # Gradient color based on frame
                fi = (self._frame_idx - 1) % len(INFINITY_FRAMES)
                p_sub = INFINITY_COLORS_PURPLE[fi]
                g_sub = INFINITY_COLORS_GOLD[fi]
                s_sub = INFINITY_COLORS_SILVER[fi]

                # Blend purple/gold/silver for a radiating gradient effect
                symbol = f"{p_sub}{frame}{_RESET}"

                color_style = "bold"
                if elapsed >= 30:
                    color_style = "bold red"
                elif elapsed >= 10:
                    color_style = "bold yellow"

                parts = [symbol, f"\033[3m{verb}\033[0m", f"\033[2m· {elapsed_str}\033[0m"]
                if progress:
                    parts.append(f"\033[2m{progress}\033[0m")

                text = " ".join(parts)
            self._render(text)
            time.sleep(0.08)

    def _render(self, text: str):
        """Render spinner text in-place, preserving ANSI color codes for gradient."""
        with self._lock:
            if not self._shown:
                sys.stdout.write("\r" + text + "\n")
                sys.stdout.flush()
                self._shown = True
                self._line_count = 1
            else:
                sys.stdout.write(move_up(self._line_count))
                sys.stdout.write(clear_line())
                sys.stdout.write("\r" + text + "\n")
                sys.stdout.flush()
                self._line_count = 1

    def _clear(self):
        with self._lock:
            if self._shown:
                for _ in range(self._line_count):
                    sys.stdout.write(move_up(1))
                    sys.stdout.write(clear_line() + "\r")
                sys.stdout.flush()
                self._shown = False


class StatusBar:
    """Bottom status line — matches Claude Code's status bar.

    Shows: Model | Mode | Tokens (+/-) | Ctx: % | [agents] | [goal]
    """

    def __init__(self):
        self.items: list[str] = []
        self._lock = threading.Lock()
        self._cached_width = 80
        self._last_width_check = 0.0
        self._width_cache_ttl = 1.0  # seconds

    def set(self, *items: str):
        with self._lock:
            self.items = list(items)

    def get_lines(self, width: int | None = None) -> list[str]:
        with self._lock:
            items = list(self.items)
        if not items:
            return [""]

        w = width or self._get_width()
        sep = "  │  "

        all_parts = []
        for item in items:
            stripped = re.sub(r'\[/?\w+(?:=.*?)?\]', '', item)
            all_parts.append((item, stripped))

        lines: list[str] = []
        current_line = ""
        current_plain = ""

        for rich_text, plain_text in all_parts:
            sep_plain = sep.replace("│", "|")
            needed = len(sep_plain) + len(plain_text) if current_line else len(plain_text)
            if current_line and len(current_plain) + 3 + len(plain_text) > w:
                lines.append(current_line)
                current_line = ""
                current_plain = ""

            if current_line:
                separator_rich = "  │  "
                current_line += separator_rich
                current_plain += sep_plain

            current_line += rich_text
            current_plain += plain_text

        if current_line:
            lines.append(current_line)
        if not lines:
            lines.append("")

        return lines

    def render_to(self, console: Console, width: int | None = None):
        lines = self.get_lines(width)
        for line in lines:
            console.print(line, highlight=False)

    def _get_width(self) -> int:
        now = time.time()
        if now - self._last_width_check > self._width_cache_ttl:
            try:
                self._cached_width = shutil.get_terminal_size().columns
            except (OSError, ValueError):
                self._cached_width = 80
            self._last_width_check = now
        return self._cached_width


class CommandMenu:
    """Slash command dropdown menu — matches Claude Code's autocomplete."""

    def __init__(self):
        self.filtered: list[dict[str, str]] = []
        self.selected_index = 0
        self.visible = False
        self.filter = ""

    def show(self, prefix: str, commands: list[dict[str, str]]):
        self.filter = prefix
        self.filtered = [c for c in commands if c["name"].startswith(prefix)]
        self.selected_index = 0
        self.visible = len(self.filtered) > 0
        return self.visible

    def show_files(self, files: list[str]):
        self.filtered = [{"name": f, "description": ""} for f in files]
        self.selected_index = 0
        self.visible = len(self.filtered) > 0
        return self.visible

    def hide(self):
        self.visible = False
        self.filtered = []

    def select_next(self):
        if self.filtered:
            self.selected_index = (self.selected_index + 1) % len(self.filtered)

    def select_prev(self):
        if self.filtered:
            self.selected_index = (self.selected_index - 1) % len(self.filtered)

    def current(self) -> dict[str, str] | None:
        if self.filtered and 0 <= self.selected_index < len(self.filtered):
            return self.filtered[self.selected_index]
        return None

    def render_lines(self, width: int) -> list[str]:
        if not self.visible or not self.filtered:
            return []

        lines = []
        max_name = min(max(visual_len(c["name"]) for c in self.filtered), max(width - 15, 10))

        for i, cmd in enumerate(self.filtered[:min(10, len(self.filtered))]):
            marker = "▸" if i == self.selected_index else " "
            name = cmd["name"]
            if visual_len(name) > max_name:
                name = truncate_visual(name, max_name - 1) + "…"
            desc = cmd.get("description") or ""
            avail = max(width - max_name - 10, 5)
            if visual_len(desc) > avail:
                desc = truncate_visual(desc, max(avail - 3, 1)) + "…"
            style_prefix = "  " if i != self.selected_index else ""
            padding = max_name - visual_len(name)
            name_padded = name + (" " * padding)
            lines.append(f"  {marker} {name_padded}  {desc}")

        return lines


class PermissionDialog:
    """Inline permission dialog — matches Claude Code's tool permission prompt."""

    @staticmethod
    def render(console: Console, tool_name: str, args: dict[str, Any]) -> bool:
        # Show the dialog
        args_preview = "\n".join(f"    {k} = {v}" for k, v in args.items())
        console.print("\n  [bold yellow]⚠ Tool execution requires approval[/bold yellow]")
        console.print(f"  [bold cyan]{tool_name}[/bold cyan]")
        if args_preview:
            console.print(f"  [dim]{args_preview}[/dim]")
        console.print("  [bold]Allow?[/bold] [green](Y)es[/green] / [red](N)o[/red] / [yellow](A)lways allow[/yellow] ", end="")

        # Wait for keypress
        if HAS_MSVCRT:
            while True:
                ch = msvcrt.getch().lower()
                if ch == b"y":
                    console.print("[green]Approved ✓[/green]")
                    return True
                elif ch == b"n":
                    console.print("[red]Denied ✗[/red]")
                    return False
                elif ch == b"a":
                    console.print("[yellow]Always allowed ✓[/yellow]")
                    return True
                elif ch == b"\x03":
                    return False
        else:
            try:
                resp = input().strip().lower()
                if resp in ("y", "yes"):
                    console.print("[green]Approved ✓[/green]")
                    return True
                else:
                    console.print("[red]Denied ✗[/red]")
                    return False
            except (EOFError, KeyboardInterrupt):
                return False
        return False


# ── Virtual Transcript Architecture ─────────────────────────────────────

@dataclass
class TranscriptBlock:
    """A single message block in the virtual transcript."""
    block_id: int
    block_type: str  # user | assistant | tool_call | tool_result | system | divider
    content: str = ""
    name: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    elapsed: float = 0.0
    collapsed: bool = True
    is_streaming: bool = False
    streaming_content: str = ""
    timestamp: float = field(default_factory=time.time)


class VirtualTranscript:
    """Structured transcript of all conversation blocks."""

    def __init__(self):
        self.blocks: list[TranscriptBlock] = []
        self._next_id = 0
        self._lock = threading.Lock()

    def add_block(self, block_type: str, **kwargs) -> int:
        with self._lock:
            block_id = self._next_id
            self._next_id += 1
            block = TranscriptBlock(
                block_id=block_id,
                block_type=block_type,
                collapsed=(block_type == "tool_result"),
                **kwargs,
            )
            self.blocks.append(block)
            return block_id

    def get_block(self, block_id: int) -> TranscriptBlock | None:
        with self._lock:
            for b in self.blocks:
                if b.block_id == block_id:
                    return b
            return None

    def update_block(self, block_id: int, **kwargs):
        with self._lock:
            for b in self.blocks:
                if b.block_id == block_id:
                    for k, v in kwargs.items():
                        setattr(b, k, v)
                    break

    def toggle_collapsed(self, block_id: int):
        with self._lock:
            for b in self.blocks:
                if b.block_id == block_id:
                    b.collapsed = not b.collapsed
                    break

    def clear(self):
        with self._lock:
            self.blocks.clear()
            self._next_id = 0

    def get_last_block(self) -> TranscriptBlock | None:
        with self._lock:
            if self.blocks:
                return self.blocks[-1]
            return None

    def count_lines(self, width: int) -> int:
        total = 0
        with self._lock:
            for block in self.blocks:
                total += self._block_line_count(block, width)
        return total

    def _block_line_count(self, block: TranscriptBlock, width: int) -> int:
        if block.block_type == "user":
            count = 0
            for line in block.content.split("\n"):
                count += max(1, math.ceil(visual_len(line) / max(width, 1)))
            return count
        elif block.block_type == "assistant":
            if not block.content.strip():
                return 0
            count = 0
            for line in block.content.split("\n"):
                count += max(1, math.ceil(visual_len(line) / max(width, 1)))
            return count
        elif block.block_type == "tool_call":
            return 1
        elif block.block_type == "tool_result":
            count = 1
            if not block.collapsed and block.content:
                content_lines = block.content.split("\n")
                visible = min(len(content_lines), 8)
                count += visible
                if len(content_lines) > 8:
                    count += 1
            elif block.collapsed and block.content:
                content_lines = block.content.split("\n")
                if len(content_lines) > 3:
                    count += 3  # 2 lines + summary
            return count
        elif block.block_type == "system":
            return 1 if block.content else 0
        elif block.block_type == "divider":
            return 1
        return 1

    def render_lines(self, width: int, scroll_offset: int = 0, view_height: int = 0) -> list[str]:
        all_lines: list[tuple[int, str]] = []
        with self._lock:
            for block in self.blocks:
                rendered = self._render_block(block, width)
                for line in rendered:
                    all_lines.append((block.block_id, line))
        total = len(all_lines)
        if view_height <= 0:
            start, end = 0, total
        else:
            max_offset = max(0, total - view_height)
            offset = min(scroll_offset, max_offset)
            start = offset
            end = min(offset + view_height, total)
        return [line for _, line in all_lines[start:end]]

    def _render_block(self, block: TranscriptBlock, width: int) -> list[str]:
        lines: list[str] = []
        if block.block_type == "user":
            lines.append(f"[bold]> {block.content}[/bold]")
        elif block.block_type == "system":
            if block.content:
                lines.append(f"[dim italic]{block.content}[/dim italic]")
        elif block.block_type == "divider":
            lines.append("[dim]" + "─" * min(width - 2, 60) + "[/dim]")
        elif block.block_type == "tool_call":
            args_preview = ""
            if block.args:
                items = list(block.args.items())[:3]
                args_preview = ", ".join(
                    f"{k}='{v}'" if isinstance(v, str) else f"{k}={v}" for k, v in items
                )
                if len(block.args) > 3:
                    args_preview += f" … +{len(block.args) - 3} more"
            status = "⠿" if block.is_streaming else "▶"
            line = f"[bold cyan]{status} {block.name}[/bold cyan]"
            if args_preview:
                line += f"  [dim]{args_preview}[/dim]"
            lines.append(line)
        elif block.block_type == "tool_result":
            status_text = "OK" if block.success else "FAIL"
            status_style = "bold green" if block.success else "bold red"
            elapsed_str = f" [{block.elapsed:.1f}s]" if block.elapsed else ""
            lines.append(f"[{status_style}]{status_text}[/{status_style}]{elapsed_str} [dim]{block.name}[/dim]")
            if block.content and not block.collapsed:
                content_lines = block.content.split("\n")
                for line in content_lines[:8]:
                    lines.append(f"[dim]  {line[:width - 4]}[/dim]")
                if len(content_lines) > 8:
                    lines.append(f"[dim]  … ({len(content_lines) - 8} more lines)[/dim]")
            elif block.content and block.collapsed:
                content_lines = block.content.split("\n")
                if len(content_lines) > 3:
                    for line in content_lines[:2]:
                        lines.append(f"[dim]  {line[:width - 4]}[/dim]")
                    lines.append(f"[dim]  … ({len(content_lines)} lines)[/dim]")
        elif block.block_type == "assistant":
            if block.content.strip():
                for line in block.content.split("\n"):
                    lines.append(line)
        return lines


class Viewport:
    """Manages scroll offset for transcript viewport."""

    def __init__(self, height: int = 0):
        self.scroll_offset = 0
        self.total_lines = 0
        self.auto_follow = True
        self._height = height

    @property
    def height(self) -> int:
        return self._height

    @height.setter
    def height(self, value: int):
        self._height = value

    @property
    def max_offset(self) -> int:
        return max(0, self.total_lines - self._height)

    def set_total(self, total_lines: int):
        was_at_bottom = self.scroll_offset >= self.max_offset or self.auto_follow
        self.total_lines = total_lines
        if was_at_bottom:
            self.scroll_to_bottom()

    def scroll_up(self, n: int = 1):
        self.auto_follow = False
        self.scroll_offset = max(0, self.scroll_offset - n)

    def scroll_down(self, n: int = 1):
        self.scroll_offset = min(self.max_offset, self.scroll_offset + n)
        if self.scroll_offset >= self.max_offset:
            self.auto_follow = True

    def page_up(self):
        self.scroll_up(max(1, self._height // 2))

    def page_down(self):
        self.scroll_down(max(1, self._height // 2))

    def scroll_to_bottom(self):
        self.auto_follow = True
        self.scroll_offset = self.max_offset

    def reset(self):
        self.scroll_to_bottom()


class FrameDiffEngine:
    """Computes minimal ANSI patches between consecutive frames."""

    def __init__(self):
        self.last_frame: list[str] = []

    def compute_patch(self, new_frame: list[str]) -> str:
        if not self.last_frame:
            self.last_frame = list(new_frame)
            return self._full_redraw(new_frame)
        patch_parts: list[str] = []
        max_lines = max(len(self.last_frame), len(new_frame))
        for i in range(max_lines):
            old_line = self.last_frame[i] if i < len(self.last_frame) else ""
            new_line = new_frame[i] if i < len(new_frame) else ""
            if old_line != new_line:
                row = i + 1
                patch_parts.append(f"{CSI}{row};1H{CSI}2K{new_line}")
        if len(new_frame) < len(self.last_frame):
            for i in range(len(new_frame), len(self.last_frame)):
                row = i + 1
                patch_parts.append(f"{CSI}{row};1H{CSI}2K")
        self.last_frame = list(new_frame)
        return "".join(patch_parts)

    def _full_redraw(self, frame: list[str]) -> str:
        parts = []
        for i, line in enumerate(frame):
            parts.append(f"{CSI}{i + 1};1H{CSI}2K{line}")
        return "".join(parts)

    def reset(self):
        self.last_frame = []


class NexusTerminalRenderer:
    """Main terminal renderer — replicates Claude Code's rendering exactly.

    Supports two rendering modes:
    - Scrollback (default): uses console.print to append to terminal
    - Fullscreen: uses viewport + frame diffing for flicker-free updates
    """

    def __init__(self, verbosity: Verbosity = Verbosity.NORMAL):
        self.console = Console(highlight=False, emoji=True, color_system="auto")
        self.verbosity = verbosity
        self._update_size()
        self.spinner = SpinnerWidget()
        self.status_bar = StatusBar()
        self.cmd_menu = CommandMenu()
        self._is_fullscreen = False
        self._input_line_count = 0
        self._last_status_height = 0
        self._previous_input_lines: list[str] = []

        # New architecture
        self.transcript = VirtualTranscript()
        self.viewport = Viewport()
        self.frame_diff = FrameDiffEngine()
        self._auto_collapse = True
        self._view_mode = "default"
        self._block_id_map: dict[int, int] = {}
        self._last_tool_call_id: int = 0
        self._welcome_height = 0
        self._scroll_region_set = False

        # Theme setting
        self.theme = DARK_THEME

        # Stored welcome params for rebuild on resize/clear
        self._welcome_params: dict = {}

    def set_theme(self, theme_name: str):
        if theme_name == "light":
            self.theme = LIGHT_THEME
        else:
            self.theme = DARK_THEME

    def _update_size(self):
        try:
            sz = shutil.get_terminal_size()
            self.width = sz.columns
            self.height = sz.lines
        except (OSError, ValueError):
            self.width = 80
            self.height = 24
        self._scroll_region_set = False

    def enter_fullscreen(self):
        if not self._is_fullscreen:
            sys.stdout.write(alternate_screen() + hide_cursor() + enable_mouse() + enable_bracketed_paste())
            sys.stdout.flush()
            self._is_fullscreen = True
            self._update_size()
            self.viewport.height = self.height - 3
            self.frame_diff.reset()
            self._previous_input_lines = []
            self._render_fullscreen()

    def exit_fullscreen(self):
        if self._is_fullscreen:
            sys.stdout.write(disable_bracketed_paste() + disable_mouse() + show_cursor() + main_screen())
            sys.stdout.flush()
            self._is_fullscreen = False
            self.frame_diff.reset()

    def toggle_fullscreen(self):
        if self._is_fullscreen:
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def _render_fullscreen(self, force: bool = False):
        """Render the fullscreen viewport with frame diffing."""
        if not self._is_fullscreen:
            return
        self._update_size()
        viewport_height = self.height - 3
        self.viewport.height = viewport_height
        total_lines = self.transcript.count_lines(self.width)
        self.viewport.set_total(total_lines)
        frame = self.transcript.render_lines(self.width, self.viewport.scroll_offset, viewport_height)
        patch = self.frame_diff.compute_patch(frame)
        sys.stdout.write(patch)
        sys.stdout.flush()

    def scroll_up(self, n: int = 1):
        if self._is_fullscreen:
            self.viewport.scroll_up(n)
            self._render_fullscreen()

    def scroll_down(self, n: int = 1):
        if self._is_fullscreen:
            self.viewport.scroll_down(n)
            self._render_fullscreen()

    def page_up(self):
        if self._is_fullscreen:
            self.viewport.page_up()
            self._render_fullscreen()

    def page_down(self):
        if self._is_fullscreen:
            self.viewport.page_down()
            self._render_fullscreen()

    def set_view_mode(self, mode: str):
        if mode in ("default", "focus", "verbose"):
            self._view_mode = mode
            if self._is_fullscreen:
                self._render_fullscreen()

    def _setup_scroll_region(self, height: int):
        # Reset any existing scroll region first
        self._reset_scroll_region()
        try:
            term_h = shutil.get_terminal_size().lines
        except (OSError, ValueError):
            term_h = 24
        if height >= term_h - 1:
            height = term_h - 2
        start = height + 1
        sys.stdout.write(f"\033[{start};{term_h}r")
        sys.stdout.write(f"\033[{start};1H")
        sys.stdout.flush()
        self._scroll_region_set = True
        self._welcome_height = height

    def _reset_scroll_region(self):
        if self._scroll_region_set:
            try:
                term_h = shutil.get_terminal_size().lines
            except (OSError, ValueError):
                term_h = 24
            sys.stdout.write(f"\033[1;{term_h}r")
            # Move cursor to the very bottom line of the terminal screen, and add a newline to scroll up once
            sys.stdout.write(f"\033[{term_h};1H\n")
            sys.stdout.flush()
            self._scroll_region_set = False

    def _clear_welcome_area(self):
        if self._welcome_height > 0:
            batch = []
            for i in range(self._welcome_height):
                batch.append(f"\033[{i + 1};1H\033[2K")
            sys.stdout.write("".join(batch))
            sys.stdout.flush()

    def welcome(self, model_name: str, workspace: str, version: str,
                provider: str = "local", context_size: int = 200000,
                tokens: object = None, metrics: dict = None,
                model_status: str = "idle", resource_info: str = "",
                active_agents: int = 0):
        try:
            W = shutil.get_terminal_size().columns
        except (OSError, ValueError):
            W = 80

        # Narrow terminal fallback
        if W < 40:
            model_d = truncate_visual(model_name, 20)
            ws = truncate_visual(workspace, 20)
            lines = [
                "╭─ NexusAgent ────────╮",
                "│ Welcome to Nexus!   │",
                f"│ Model: {model_d:<20} │",
                f"│ Workspace: {ws:<20} │",
                "╰─────────────────────╯"
            ]
            panel_h = len(lines)
            batch = []
            for i in range(panel_h):
                batch.append(f"\033[{i + 1};1H\033[2K")
            for i, line in enumerate(lines):
                batch.append(f"\033[{i + 1};1H{line}")
            batch.append(f"\033[{panel_h + 1};1H")
            sys.stdout.write("".join(batch))
            sys.stdout.flush()
            self._welcome_height = panel_h
            self._setup_scroll_region(self._welcome_height)
            self._welcome_params = dict(
                model_name=model_name,
                workspace=workspace,
                version=version,
                provider=provider,
                context_size=context_size,
                model_status=model_status,
                resource_info=resource_info,
                tokens=tokens,
                metrics=metrics,
                active_agents=active_agents,
            )
            return

        import subprocess
        import psutil

        # 1. Fetch system statistics
        cpu_percent = psutil.cpu_percent(interval=None) or 0.0
        if cpu_percent == 0.0:
            cpu_percent = 5.0
            
        cpu_threads = os.cpu_count() or 8
        if metrics and "threads" in metrics:
            cpu_threads = metrics["threads"]

        try:
            virtual_mem = psutil.virtual_memory()
            used_gb = virtual_mem.used / (1024**3)
            total_gb = virtual_mem.total / (1024**3)
            mem_str = f"{used_gb:.1f}G/{total_gb:.0f}G"
        except Exception:
            mem_str = "—"

        gpu_percent = 0
        try:
            gpu_res = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=1
            )
            if gpu_res.returncode == 0 and gpu_res.stdout.strip().isdigit():
                gpu_percent = int(gpu_res.stdout.strip())
        except Exception:
            pass

        # 2. Fetch git delta lines
        added = 0
        deleted = 0
        try:
            res = subprocess.run(
                ["git", "diff", "--numstat"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=2
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 3:
                        a, d = parts[0], parts[1]
                        if a.isdigit() and d.isdigit():
                            added += int(a)
                            deleted += int(d)
        except Exception:
            pass
        delta_lines = f"+{added}/-{deleted}"

        # 3. Setup tokens
        tokens_in = tokens.total_input if tokens and hasattr(tokens, 'total_input') else 0
        tokens_out = tokens.total_output if tokens and hasattr(tokens, 'total_output') else 0
        context_used = tokens.total if tokens and hasattr(tokens, 'total') else 0
        context_limit = context_size

        # 4. Formatter layout
        if W < 75:
            box_width = 55
            left_col_w = 33
            right_col_w = 18
        else:
            box_width = 70
            left_col_w = 45
            right_col_w = 21

        def format_dashboard_line(left: str, right: str = "") -> str:
            left_plain = strip_markup(_ANSI_RE.sub('', left))
            right_plain = strip_markup(_ANSI_RE.sub('', right))
            
            if not right:
                pad = box_width - visual_len(left_plain)
                return f"│{left}{' ' * pad}│"
            else:
                left_pad = left_col_w - visual_len(left_plain)
                right_pad = right_col_w - visual_len(right_plain)
                return f"│{left}{' ' * left_pad} ║ {right}{' ' * right_pad}│"

        # 5. Build dashboard details
        model_d = truncate_visual(model_name, 20)
        
        # Colors
        B = "\033[1m"
        D = "\033[2m"
        C = hex_to_ansi(self.theme.accent_primary)
        R = "\033[0m"
        Y = hex_to_ansi(self.theme.accent_warning)
        M_color = "\033[38;2;180;80;220m"

        left_1 = f" 🦄 NexusAgent      Model: {M_color}{model_d}{R}"
        right_1 = f"Mem: {mem_str}"

        left_2 = f"  CPU: {cpu_threads} threads    GPU: {gpu_percent}%"
        right_2 = f"Context: {context_used}/{context_limit}"

        left_3 = f"  Tokens In: {tokens_in:<6} Out: {tokens_out}"
        right_3 = f"ΔLines: {delta_lines}"

        left_4 = f"  Processes (agents): {active_agents}"
        right_4 = ""

        # Draw box
        lines = [
            "┌" + "─" * box_width + "┐",
            format_dashboard_line(left_1, right_1),
            format_dashboard_line(left_2, right_2),
            format_dashboard_line(left_3, right_3),
            format_dashboard_line(left_4, right_4),
            "└" + "─" * box_width + "┘"
        ]

        panel_h = len(lines)
        batch = []
        if self._scroll_region_set:
            batch.append("\033[s")  # Save cursor position if scroll region is active

        for i in range(panel_h):
            batch.append(f"\033[{i + 1};1H\033[2K")
        for i, line in enumerate(lines):
            batch.append(f"\033[{i + 1};1H{line}")

        if self._scroll_region_set:
            batch.append("\033[u")  # Restore cursor position
        else:
            batch.append(f"\033[{panel_h + 1};1H")  # Move cursor to top of scroll region

        sys.stdout.write("".join(batch))
        sys.stdout.flush()

        self._welcome_height = panel_h
        if not self._scroll_region_set:
            self._setup_scroll_region(self._welcome_height)

        self.transcript.add_block("system", content=f"NexusAgent v{version}")
        self.transcript.add_block("system", content=f"Model: {model_name}")
        self.transcript.add_block("system", content=f"Working directory: {workspace}")

        # Store params for rebuild on resize/clear
        self._welcome_params = dict(
            model_name=model_name,
            workspace=workspace,
            version=version,
            provider=provider,
            context_size=context_size,
            model_status=model_status,
            resource_info=resource_info,
            tokens=tokens,
            metrics=metrics,
            active_agents=active_agents,
        )

    def update_size(self):
        self._update_size()

    def rebuild_welcome(self, tokens: object = None, metrics: dict = None,
                      model_status: str | None = None, resource_info: str = "",
                      active_agents: int | None = None, model_name: str | None = None):
        """Rebuild the welcome panel after terminal resize or clear screen."""
        p = self._welcome_params
        if not p:
            return
        if model_name is not None:
            p["model_name"] = model_name
        actual_status = model_status if model_status is not None else p.get("model_status", "idle")
        actual_resource = resource_info if resource_info else p.get("resource_info", "")
        actual_tokens = tokens if tokens is not None else p.get("tokens")
        actual_metrics = metrics if metrics is not None else p.get("metrics")
        actual_active = active_agents if active_agents is not None else p.get("active_agents", 0)
        self.welcome(
            p["model_name"], p["workspace"], p["version"],
            p.get("provider", "local"), p.get("context_size", 200000),
            actual_tokens, actual_metrics, actual_status, actual_resource,
            active_agents=actual_active,
        )

    def system_message(self, text: str):
        self.console.print(f"  [dim]⎿ {text}[/dim]")
        self.transcript.add_block("system", content=text)

    def user_message(self, text: str):
        self.console.print(f"[bold]❯ {text}[/bold]")
        self.transcript.add_block("user", content=text)

    def _get_token_string(self) -> str:
        if hasattr(self, 'tokens') and self.tokens:
            req = self.tokens.current_request
            if req.input_tokens == 0 and req.output_tokens == 0:
                req = self.tokens.last_request
            
            if req.input_tokens > 0 or req.output_tokens > 0:
                parts = []
                if req.input_tokens > 0:
                    parts.append(f"In: {req.input_tokens:,}")
                if req.output_tokens > 0:
                    parts.append(f"Out: {req.output_tokens:,}")
                if parts:
                    return f"  [dim]({' | '.join(parts)})[/dim]"
        return ""

    def assistant_message(self, content: str):
        if not content.strip():
            return
        self.transcript.add_block("assistant", content=content)
        token_str = self._get_token_string()
        try:
            self.console.print(f"[bold]●[/bold]{token_str}")
            md = Markdown(content, code_theme="monokai", inline_code_theme="monokai")
            self.console.print(md)
        except (ValueError, TypeError):
            for line in content.split("\n"):
                self.console.print(f"{line}")

    def tool_call(self, name: str, args: dict[str, Any], is_start: bool = True):
        block_id = self.transcript.add_block("tool_call", name=name, args=args, is_streaming=is_start)
        self._block_id_map[len(self._block_id_map)] = block_id
        self.console.print(f"\n[bold cyan]▶ {name}[/bold cyan]")
        if args:
            items = list(args.items())[:3]
            args_preview = ", ".join(
                f"{k}='{v}'" if isinstance(v, str) else f"{k}={v}" for k, v in items
            )
            if len(args) > 3:
                args_preview += f" … +{len(args) - 3} more"
            self.console.print(f"[dim]  {args_preview}[/dim]")
        self._last_tool_call_id = block_id

    def tool_result(self, name: str, output: str, success: bool, elapsed: float = 0):
        status_text = "[bold green]OK[/bold green]" if success else "[bold red]FAIL[/bold red]"
        elapsed_str = f" [dim][{elapsed:.1f}s][/dim]" if elapsed else ""
        if hasattr(self, '_last_tool_call_id'):
            self.transcript.update_block(
                self._last_tool_call_id,
                is_streaming=False,
                success=success,
                elapsed=elapsed,
                content=output,
            )
        if not output:
            self.console.print(f"  {status_text}{elapsed_str} [dim]{name}[/dim]")
        else:
            self.console.print(f"  {status_text}{elapsed_str} [dim]{name}[/dim]")
            lines = output.split("\n")
            max_preview = 20 if self._view_mode == "verbose" else 3
            if self._view_mode != "verbose":
                for line in lines[:max_preview]:
                    self.console.print(f"[dim]  {line[:self.width - 4]}[/dim]")
                if len(lines) > max_preview:
                    self.console.print(f"[dim]  … ({len(lines) - max_preview} more lines)[/dim]")

    def error(self, msg: str):
        term_width = min(shutil.get_terminal_size().columns, 100)
        self.console.print("\033[2m" + "─" * term_width + "\033[0m")
        self.console.print(f"[bold red]Error: {msg}[/bold red]")
        self.console.print("\033[2m" + "─" * term_width + "\033[0m")
        self.transcript.add_block("system", content=f"Error: {msg}")

    def divider(self):
        term_width = min(shutil.get_terminal_size().columns, 100)
        self.console.print("\033[2m" + "─" * term_width + "\033[0m")
        self.transcript.add_block("divider")

    def show_spinner(self, verb: str | None = None):
        self.spinner.start(verb)

    def hide_spinner(self):
        return self.spinner.stop()

    def update_spinner(self, verb: str):
        self.spinner.update_verb(verb)

    def update_status(self, *items: str):
        self.status_bar.set(*items)

    def show_cmd_menu(self, prefix: str, commands: list[dict[str, str]]) -> bool:
        return self.cmd_menu.show(prefix, commands)

    def show_file_menu(self, files: list[str]) -> bool:
        return self.cmd_menu.show_files(files)

    def hide_cmd_menu(self):
        self.cmd_menu.hide()

    def clear(self):
        self.transcript.clear()
        self._block_id_map.clear()
        sys.stdout.write(clear_screen())
        sys.stdout.flush()
        self.frame_diff.reset()
        if self._is_fullscreen:
            self._render_fullscreen()
        else:
            self.rebuild_welcome()

    def close(self):
        self._reset_scroll_region()
        self.spinner.stop()
        self.exit_fullscreen()

    def print(self, text: str):
        self.console.print(text)

    def set_terminal_title(self, title: str):
        sys.stdout.write(set_title(title))
        sys.stdout.flush()

    def expand_tool_output(self, block_id: int | None = None):
        if block_id is not None:
            self.transcript.update_block(block_id, collapsed=False)
        elif hasattr(self, '_last_tool_call_id'):
            self.transcript.update_block(self._last_tool_call_id, collapsed=False)
        if self._is_fullscreen:
            self._render_fullscreen()

    def collapse_tool_output(self, block_id: int | None = None):
        if block_id is not None:
            self.transcript.update_block(block_id, collapsed=True)
        elif hasattr(self, '_last_tool_call_id'):
            self.transcript.update_block(self._last_tool_call_id, collapsed=True)
        if self._is_fullscreen:
            self._render_fullscreen()

    def toggle_tool_output(self, block_id: int | None = None):
        if block_id is not None:
            self.transcript.toggle_collapsed(block_id)
        elif hasattr(self, '_last_tool_call_id'):
            self.transcript.toggle_collapsed(self._last_tool_call_id)
        if self._is_fullscreen:
            self._render_fullscreen()

    def flush(self):
        """Flush the renderer — called after agent execution."""
        if self._is_fullscreen:
            self._render_fullscreen(force=True)
        sys.stdout.flush()

    def render_transcript(self) -> list[str]:
        """Render the full transcript (for /context, /log, etc.)."""
        return self.transcript.render_lines(self.width)

    # ── Streaming Display ──────────────────────────────────────────────

    def stream_text(self, text: str):
        """Progressively display a text chunk (alias for stream_chunk)."""
        self.stream_chunk(text)

    def stream_chunk(self, chunk: str):
        """Append a streamed chunk and render it progressively.

        Uses raw stdout writes for real-time display. Each chunk is
        appended to the streaming buffer and the current line is
        redrawn so text appears word-by-word like Claude Code.

        Includes:
        - Render throttling at ~30fps (33ms min between redraws)
        - DEC mode 2026 synchronized output to eliminate flicker
        """
        if not hasattr(self, '_streaming_buffer'):
            self._streaming_buffer = ""
            self._streaming_line_count = 0
            self._streaming_block_id = self.transcript.add_block(
                "assistant", content="", is_streaming=True,
            )
            self._streaming_last_render = 0.0
            self._streaming_active = True
            # Print the ● marker once at start with incoming tokens if available
            token_str = ""
            if hasattr(self, 'tokens') and self.tokens:
                req = self.tokens.current_request
                if req.input_tokens > 0:
                    token_str = f"  [dim](In: {req.input_tokens:,})[/dim]"
            self.console.print(f"[bold]●[/bold]{token_str}", end="")
            sys.stdout.write("\n")
            sys.stdout.flush()
            self._streaming_line_count = 1

        self._streaming_buffer += chunk

        # Render throttle: skip redraws if less than 33ms since last render
        now = time.time()
        if now - self._streaming_last_render < 0.033:
            return
        self._streaming_last_render = now

        # Split into lines and render current state
        lines = self._streaming_buffer.split("\n")
        new_line_count = len(lines)

        # Use synchronized output to batch all writes (DEC mode 2026)
        batch = enable_synchronized()

        # Move up to overwrite previous streaming output
        if self._streaming_line_count > 0:
            for _ in range(self._streaming_line_count):
                batch += move_up(1) + clear_line() + "\r"

        # Write all lines with proper visual width truncation
        w = max(self.width - 2, 10)
        for line in lines:
            if visual_len(line) > w:
                line = truncate_visual(line, w)
            batch += line + "\n"

        batch += disable_synchronized()
        sys.stdout.write(batch)
        sys.stdout.flush()
        self._streaming_line_count = new_line_count

        # Update transcript block
        self.transcript.update_block(
            self._streaming_block_id,
            content=self._streaming_buffer,
        )

    def finalize_stream(self) -> str:
        """Finalize streaming display: clear raw output, render final markdown.

        Returns the full accumulated response text.
        """
        if not hasattr(self, '_streaming_buffer'):
            return ""

        full_response = self._streaming_buffer
        self._streaming_active = False

        # Clear the raw streaming output
        if self._streaming_line_count > 0:
            for _ in range(self._streaming_line_count):
                sys.stdout.write(move_up(1) + clear_line() + "\r")
            sys.stdout.flush()

        # Render final markdown
        if full_response.strip():
            self.transcript.update_block(
                self._streaming_block_id,
                content=full_response,
                is_streaming=False,
            )
            token_str = self._get_token_string()
            try:
                self.console.print(f"[bold]●[/bold]{token_str}")
                md = Markdown(full_response, code_theme="monokai", inline_code_theme="monokai")
                self.console.print(md)
            except (ValueError, TypeError):
                for line in full_response.split("\n"):
                    self.console.print(line)

        # Clean up streaming state safely (guard against double-call)
        result = full_response
        for attr in ('_streaming_buffer', '_streaming_line_count', '_streaming_block_id', '_streaming_last_render'):
            if hasattr(self, attr):
                delattr(self, attr)
        return result
