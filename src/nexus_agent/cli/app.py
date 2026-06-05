"""NexusAgent CLI — Full-Spectrum Agentic Coding Terminal.

Complete REPL application matching Claude Code's terminal UI while providing
the full feature map of modern AI coding agents:
- Autonomous goal execution with Planner/Executor/Orchestrator
- Multi-step agent loops with reflection and self-healing
- Repository mapping with RAG, AST indexing, and code search
- Shell execution, browser automation, and MCP tool integration
- Git intelligence with commit generation, PR review, branching
- DevOps verification pipeline (linters, secrets, tests)
- Multi-agent debate and consensus review
- Persistent memory (working, long-term, episodic, user profile)
- Skill system for modular sub-agent spawning
- Sandboxed execution with permission gating
- Streaming reasoning, interactive patches, and session management
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.text import Text

from nexus_agent.cli.commands import CommandDispatcherMixin
from nexus_agent.cli.event_handler import EventHandlerMixin
from nexus_agent.cli.input_handler_simple import MinimalInputHandlerMixin
from nexus_agent.cli.event_bus import EventBus, Event
from nexus_agent.cli.renderer import (
    ContextBreakdown,
    NexusTerminalRenderer,
    TokenUsage,
    Verbosity,
)
from nexus_agent.cli.session_handler import SessionOrchestratorMixin
from nexus_agent.core.agent import AgentLoop, AgentMode

logger = logging.getLogger(__name__)


@dataclass
class CLIState:
    """Encapsulates all mutable TUI/CLI interface states cleanly.

    Isolates UI variables from sessions and configuration logic.
    """

    is_running: threading.Event = field(default_factory=threading.Event)
    processing: bool = False
    model_status: str = "idle"  # idle | loading | loaded | unloading
    first_request_done: bool = False
    abort_event: threading.Event = field(default_factory=threading.Event)
    input_history: list[str] = field(default_factory=list)
    history_idx: int = -1
    prompt_line_count: int = 0
    prompt_line_y: int = 0
    drawer_active: bool = False
    drawer_idx: int = 0
    current_mode: AgentMode = AgentMode.ACT
    verbosity: Verbosity = Verbosity.NORMAL

    def __post_init__(self):
        self.is_running.set()


class EventLogHandler:
    """Subscribes to EventBus and writes structured events to a log file."""

    def __init__(self, log_file_path: str):
        try:
            self.log_file = open(log_file_path, "a", encoding="utf-8", buffering=1)
        except (OSError, ValueError) as e:
            logger.warning("Event log file open failed: %s", e)
            self.log_file = None

    def __call__(self, event: Event):
        if self.log_file:
            try:
                self.log_file.write(f"[{event.timestamp}] {event.type}: {event}\n")
            except (OSError, ValueError) as e:
                logger.debug("Event log write failed: %s", e)

    def close(self):
        if self.log_file:
            self.log_file.close()


class TUIDebugLogger:
    """Stream interceptor that duplicates stdout/stderr to a log file."""

    def __init__(self, stream, log_path: str):
        self.stream = stream
        self.log_path = log_path
        self.log_file = None
        try:
            self.log_file = open(log_path, "a", encoding="utf-8", buffering=1)
        except (OSError, ValueError) as e:
            logger.warning("TUIDebugLogger failed to open log file: %s", e)

    def write(self, data: str):
        self.stream.write(data)
        if self.log_file:
            self.log_file.write(data)

    def flush(self):
        self.stream.flush()
        if self.log_file:
            self.log_file.flush()

    def isatty(self) -> bool:
        return self.stream.isatty()

    def close(self):
        if self.log_file:
            self.log_file.close()


class NexusApp(
    CommandDispatcherMixin,
    MinimalInputHandlerMixin,
    SessionOrchestratorMixin,
    EventHandlerMixin,
):
    """Main REPL application — matches Claude Code's interaction model."""

    def __init__(
        self,
        model_path: str | None = None,
        provider: str | None = None,
        workspace: Path | None = None,
        gpu_layers: int | None = None,
        config_path: str | None = None,
        data_dir: str | None = None,
        initial_prompt: str | None = None,
        session_id: str | None = None,
        verbose: bool = False,
        quiet: bool = False,
    ):
        self.workspace = workspace or Path.cwd()
        self.config_path = config_path
        self.data_dir = data_dir
        self.initial_prompt = initial_prompt
        self._model_path = model_path
        self._provider_name = provider
        self._gpu_layers = gpu_layers
        self._session_id = session_id

        verbosity = Verbosity.VERBOSE if verbose else Verbosity.QUIET if quiet else Verbosity.NORMAL
        self.r = NexusTerminalRenderer(verbosity)
        self.console = self.r.console

        self.state = CLIState(verbosity=verbosity)

        self._config: dict[str, Any] = {}
        self._agent: AgentLoop | None = None
        self._engine: Any = None
        self._memory: Any = None
        self._session_mgr: Any = None
        self._permissions: Any = None
        self._tokens = TokenUsage()
        self._context = ContextBreakdown()
        self._metrics = {
            "read_tokens": 0,
            "write_tokens": 0,
            "edit_tokens": 0,
            "reasoning_tokens": 0,
            "inference_tokens": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "tool_calls": 0,
        }

        self._sub_agents: list[dict] = []
        self._tool_timings: dict[str, float] = {}
        self._cmd_menu_lines = 0
        self._copied_text: str = ""
        self._session_history: list[str] = []
        self._resize_debounce: float = 0.0
        self._resize_debounce_delay: float = 0.1
        self._kill_buffer = ""
        self._last_term_h = shutil.get_terminal_size().lines
        self._key_queue: list[bytes] = []
        # Phase 8 — Footer & Drawer state
        self._footer_log = ""
        self._footer_log_time = 0.0
        self._notification = ""
        self._notification_time = 0.0

        self.event_bus = EventBus()
        log_path = os.path.join(str(self.workspace), "nexus-tui-screen.log")
        self._event_logger = EventLogHandler(log_path)
        self.event_bus.subscribe(Event, self._event_logger)

    # -- Property delegates to preserve backwards compatibility for mixins --

    # -- Property delegates to preserve backwards compatibility for mixins --

    def _ensure_state(self):
        if not hasattr(self, "state") or self.state is None:
            self.state = CLIState()

    def get_config_dir(self) -> Path:
        return Path.home() / ".nexus"

    @property
    def _is_running(self) -> threading.Event:
        self._ensure_state()
        return self.state.is_running

    @_is_running.setter
    def _is_running(self, val: threading.Event):
        self._ensure_state()
        self.state.is_running = val

    @property
    def _processing(self) -> bool:
        self._ensure_state()
        return self.state.processing

    @_processing.setter
    def _processing(self, val: bool):
        self._ensure_state()
        self.state.processing = val

    @property
    def _model_status(self) -> str:
        self._ensure_state()
        return self.state.model_status

    @_model_status.setter
    def _model_status(self, val: str):
        self._ensure_state()
        self.state.model_status = val

    @property
    def _first_request_done(self) -> bool:
        self._ensure_state()
        return self.state.first_request_done

    @_first_request_done.setter
    def _first_request_done(self, val: bool):
        self._ensure_state()
        self.state.first_request_done = val

    @property
    def _abort_event(self) -> threading.Event:
        self._ensure_state()
        return self.state.abort_event

    @_abort_event.setter
    def _abort_event(self, val: threading.Event):
        self._ensure_state()
        self.state.abort_event = val

    @property
    def _input_history(self) -> list[str]:
        self._ensure_state()
        return self.state.input_history

    @_input_history.setter
    def _input_history(self, val: list[str]):
        self._ensure_state()
        self.state.input_history = val

    @property
    def _history_idx(self) -> int:
        self._ensure_state()
        return self.state.history_idx

    @_history_idx.setter
    def _history_idx(self, val: int):
        self._ensure_state()
        self.state.history_idx = val

    @property
    def _prompt_line_count(self) -> int:
        self._ensure_state()
        return self.state.prompt_line_count

    @_prompt_line_count.setter
    def _prompt_line_count(self, val: int):
        self._ensure_state()
        self.state.prompt_line_count = val

    @property
    def _drawer_active(self) -> bool:
        self._ensure_state()
        return self.state.drawer_active

    @_drawer_active.setter
    def _drawer_active(self, val: bool):
        self._ensure_state()
        self.state.drawer_active = val

    @property
    def _drawer_idx(self) -> int:
        self._ensure_state()
        return self.state.drawer_idx

    @_drawer_idx.setter
    def _drawer_idx(self, val: int):
        self._ensure_state()
        self.state.drawer_idx = val

    @property
    def _current_mode(self) -> AgentMode:
        self._ensure_state()
        return self.state.current_mode

    @_current_mode.setter
    def _current_mode(self, val: AgentMode):
        self._ensure_state()
        self.state.current_mode = val

    def run(self):
        import os
        import sys
        
        # Ensure UTF-8 for stdout/stderr to prevent UnicodeEncodeError on Windows
        if sys.platform == "win32":
            try:
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
                sys.stderr.reconfigure(encoding='utf-8', errors='replace')
            except (OSError, AttributeError):
                pass

        log_path = os.path.join(str(self.workspace), "nexus-tui-screen.log")
        self._stdout_logger = None
        self._stderr_logger = None
        try:
            self._stdout_logger = TUIDebugLogger(sys.stdout, log_path)
            self._stderr_logger = TUIDebugLogger(sys.stderr, log_path)
            self._original_stdout = sys.stdout
            self._original_stderr = sys.stderr
            sys.stdout = self._stdout_logger
            sys.stderr = self._stderr_logger
        except (OSError, ValueError) as e:
            logger.warning("TUIDebugLogger setup failed: %s", e)

        try:
            self._initialize()
            # self._rebuild_welcome()  <-- Removed redundant call
            self._main_loop()
        except KeyboardInterrupt:

            self.console.print(Text("\n  Interrupted.", style="dim"))
        except (RuntimeError, ValueError, OSError, TypeError) as e:
            logger.exception("Fatal error")
            self.console.print(Text(f"\n  X Fatal: {e}", style="bold red"))
        finally:
            self._cleanup()
            if getattr(self, "_original_stdout", None):
                sys.stdout = self._original_stdout
            if getattr(self, "_original_stderr", None):
                sys.stderr = self._original_stderr
            if getattr(self, "_stdout_logger", None) and self._stdout_logger.log_file:
                try:
                    self._stdout_logger.log_file.close()
                except (OSError, ValueError) as e:
                    logger.debug("stdout logger close: %s", e)
            if getattr(self, "_stderr_logger", None) and self._stderr_logger.log_file:
                try:
                    self._stderr_logger.log_file.close()
                except (OSError, ValueError) as e:
                    logger.debug("stderr logger close: %s", e)

    def _main_loop(self):
        self._rebuild_welcome()

        try:
            from blessed import Terminal as _Bt
            _mouse_term = _Bt()
            with _mouse_term.cbreak(), _mouse_term.keypad(), _mouse_term.bracketed_paste():
                self._run_main_loop_logic()
        except (ImportError, OSError, AttributeError) as e:
            logger.debug("Mouse tracking setup skipped: %s", e)

    def _run_main_loop_logic(self):
        effort = self._config.get("agent", {}).get("effort_level", "medium")
        mode = self._current_mode.value
        self.r.system_message(f"Mode: {mode.upper()} | Effort: {effort.upper()}")

        # Set terminal title
        self.r.set_terminal_title(self._status_line())

        if self.initial_prompt:
            time.sleep(0.3)
            self.r.user_message(self.initial_prompt)
            self._process_user_input(self.initial_prompt)
            self.initial_prompt = None

        if not sys.stdin.isatty():
            # Non-interactive pipelining fallback (CI/CD / redirected input)
            logger.info(
                "Non-interactive terminal detected. Falling back to line-by-line streaming."
            )
            for line in sys.stdin:
                user_input = line.strip()
                if user_input:
                    self.r.user_message(user_input)
                    self._process_user_input(user_input)
            return

        self._last_auto_save: float = time.time()

        while self._is_running.is_set():
            try:
                user_input = self._read_input()
                if user_input is None:
                    self._check_resize()
                    continue
                self._process_user_input(user_input)
                self._check_resize()

                now = time.time()
                if now - self._last_auto_save > 30.0:
                    if self._session_mgr:
                        try:
                            self._session_mgr.save_session()
                        except (OSError, ValueError):
                            pass
                    self._last_auto_save = now
            except KeyboardInterrupt:
                if self._processing:
                    self._abort_event.set()
                    self.r.system_message("Interrupting…")
                else:
                    self._clear_cmd_menu(self._cmd_menu_lines > 0)
                    break
            except EOFError:
                self._clear_cmd_menu(self._cmd_menu_lines > 0)
                break

    def _cleanup(self):
        try:
            self.r.console.clear()
        except Exception:
            pass

        self.r.close()
        if self._session_mgr:
            try:
                self._session_mgr.save_session()
            except (OSError, ValueError):
                pass
        if self._engine:
            try:
                self._engine.close()
            except (OSError, RuntimeError):
                pass
        if self._agent:
            try:
                self._agent.nla_telemetry.generate_session_summary()
            except (OSError, ValueError, RuntimeError):
                pass
        # Close MCP clients
        for client in getattr(self, "_mcp_clients", []):
            try:
                client.close()
            except (OSError, RuntimeError):
                pass
        self.r.console.print("\n[dim]Goodbye.[/dim]")
        self.r.set_terminal_title("NexusAgent — closed")
