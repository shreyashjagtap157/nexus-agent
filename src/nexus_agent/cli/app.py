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
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Any

from rich.text import Text

from nexus_agent import __version__
from nexus_agent.cli.command_dispatcher import CommandDispatcherMixin
from nexus_agent.cli.event_handler import EventHandlerMixin
from nexus_agent.cli.input_handler import InputHandlerMixin
from nexus_agent.cli.renderer import (
    ContextBreakdown,
    NexusTerminalRenderer,
    TokenUsage,
    Verbosity,
)
from nexus_agent.cli.session_handler import SessionOrchestratorMixin
from nexus_agent.core.agent import AgentLoop, AgentMode

logger = logging.getLogger(__name__)


class NexusApp(
    CommandDispatcherMixin,
    InputHandlerMixin,
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
        new_session: bool = False,
        verbose: bool = False,
        quiet: bool = False,
    ):
        self.workspace = workspace or Path.cwd()
        self.config_path = config_path
        self.data_dir = data_dir
        self.initial_prompt = initial_prompt
        self._model_path = model_path
        self._model_path_passed = (model_path is not None)
        self._provider_name = provider
        self._gpu_layers = gpu_layers
        self._session_id = session_id
        self._new_session = new_session

        verbosity = Verbosity.VERBOSE if verbose else Verbosity.QUIET if quiet else Verbosity.NORMAL
        self.r = NexusTerminalRenderer(verbosity)
        self.console = self.r.console

        self._config: dict[str, Any] = {}
        self._agent: AgentLoop | None = None
        self._engine: Any = None
        self._memory: Any = None
        self._session_mgr: Any = None
        self._permissions: Any = None
        self._mcp_clients: list = []
        self._mcp_tools: list = []
        self._skill_registry: Any = None
        self._current_mode = AgentMode.AUTO
        self._tokens = TokenUsage()
        self.r.tokens = self._tokens
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

        self._is_running = threading.Event()
        self._is_running.set()
        self._processing = False
        self._model_status = "idle"  # idle | loading | loaded | unloading
        self._first_request_done = False
        self._abort_event = threading.Event()

        self._input_history: list[str] = []
        self._history_idx = -1
        self._prompt_line_count = 0

        self._sub_agents: list[dict] = []
        self._tool_timings: dict[str, float] = {}
        self._cmd_menu_lines = 0
        self._kill_buffer = ""
        self._last_term_h = shutil.get_terminal_size().lines
        self._key_queue: list[bytes] = []
        # Phase 8 — Footer & Drawer state
        self._footer_log = ""
        self._footer_log_time = 0.0
        self._notification = ""
        self._notification_time = 0.0
        self._drawer_active = False
        self._drawer_idx = 0

    def run(self):
        try:
            self._initialize()
            self._welcome_thread = threading.Thread(target=self._welcome_update_loop, daemon=True)
            self._welcome_thread.start()
            self._main_loop()
        except KeyboardInterrupt:
            self.console.print(Text("\n  Interrupted.", style="dim"))
        except (RuntimeError, ValueError, OSError, TypeError) as e:
            logger.exception("Fatal error")
            self.console.print(Text(f"\n  X Fatal: {e}", style="bold red"))
        finally:
            self._cleanup()

    def _welcome_update_loop(self):
        while self._is_running.is_set():
            time.sleep(1.0)
            if not self._processing:
                try:
                    self._rebuild_welcome()
                except Exception:
                    pass

    def _main_loop(self):
        # Clear screen to ensure no remnants of early prints are visible
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

        model_name = self._model_name()
        provider = self._provider_name or "local"
        if provider in self._PROVIDER_CONTEXT_SIZES:
            context_size = self._PROVIDER_CONTEXT_SIZES[provider]
        else:
            context_size = self._config.get("local_model", {}).get("context_size", 200000)
        self.r.welcome(
            model_name,
            str(self.workspace),
            __version__,
            provider,
            context_size,
            self._tokens,
            self._metrics,
            active_agents=len(self._sub_agents),
        )

        effort = self._config.get("agent", {}).get("effort_level", "medium")
        mode = self._current_mode.value
        self.r.system_message(f"Mode: {mode.upper()} | Effort: {effort.upper()}")

        # Print any startup error cleanly below the welcome panel
        startup_err = getattr(self, "_startup_error", None)
        if startup_err:
            self.r.error(startup_err)
            self._startup_error = None

        # Set terminal title
        self.r.set_terminal_title(self._status_line())

        if self.initial_prompt:
            time.sleep(0.3)
            self.r.user_message(self.initial_prompt)
            self._process_user_input(self.initial_prompt)
            self.initial_prompt = None

        while self._is_running.is_set():
            try:
                user_input = self._read_input()
                if user_input is None:
                    self._check_resize()
                    continue
                self._process_user_input(user_input)
                self._check_resize()
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
        self.r.close()
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()
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
        for client in getattr(self, '_mcp_clients', []):
            try:
                client.close()
            except (OSError, RuntimeError):
                pass
        logo = """
 _   _  _____  __  __ _   _  ____    _     ____ _____ _   _ _____ 
| \\ | || ____| \\ \\/ /| | | |/ ___|  / \\   / ___| ____| \\ | |_   _|
|  \\| ||  _|    \\  / | | | |\\___ \\ / _ \\ | |  _|  _| |  \\| | | |  
| |\\  || |___   /  \\ | |_| | ___) / ___ \\| |_| | |___| |\\  | | |  
|_| \\_||_____| /_/\\_\\ \\___/|____/_/   \\_\\\\____|_____|_| \\_| |_|  
"""
        self.r.console.print(logo, style="bold cyan")
        if self._session_id:
            self.r.console.print(f"  [bold green]Session saved.[/bold green] To resume this session, run:")
            self.r.console.print(f"  [bold]nexus session resume {self._session_id}[/bold]\n")
        else:
            self.r.console.print("  [dim]Goodbye.[/dim]\n")
        self.r.set_terminal_title("NexusAgent — closed")
