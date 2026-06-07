"""
Background sessions — parallel isolated agent runs.

A `BackgroundSession` is a self-contained subagent invocation that runs
in a daemon thread. It has its own session id, its own conversation log,
and is registered with the parent `SessionManager` so the foreground
session stays interactive while the background work proceeds.

Use cases:
- Long-running research ("/background research the latest X while I code")
- Parallel investigations (multiple /background commands at once)
- File processing that should not block the main conversation
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class BackgroundState(str, Enum):
    """Lifecycle states of a background session."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BackgroundResult:
    """The final result of a background session."""

    session_id: str
    prompt: str
    state: BackgroundState
    output: str = ""
    error: str | None = None
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    iterations: int = 0
    tokens_used: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "prompt": self.prompt,
            "state": self.state.value,
            "output": self.output,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "iterations": self.iterations,
            "tokens_used": self.tokens_used,
            "duration_s": (
                None if self.finished_at is None else (self.finished_at - self.started_at)
            ),
        }


class BackgroundSession:
    """A non-blocking, parallel subagent run.

    A `BackgroundSession` wraps a single `agent.run(prompt)` invocation in a
    daemon thread. The foreground session can continue to interact with the
    user; the background session reports progress through its `status()` /
    `get_output()` methods and via the registered `SessionManager`.

    The session is identified by a 12-character hex id. The full conversation
    is persisted in the parent SessionManager's storage (so it survives a
    restart) but does not pollute the foreground session's message history.
    """

    def __init__(
        self,
        prompt: str,
        run_callable: Callable[[str], str],
        *,
        session_id: str | None = None,
        max_iterations: int = 30,
        metadata: dict[str, Any] | None = None,
        on_complete: Callable[["BackgroundResult"], None] | None = None,
    ):
        self.session_id = session_id or uuid.uuid4().hex[:12]
        self.prompt = prompt
        self._run_callable = run_callable
        self.max_iterations = max_iterations
        self.metadata = metadata or {}
        self._on_complete = on_complete

        self._state = BackgroundState.PENDING
        self._output_lines: list[str] = []
        self._output_lock = threading.Lock()
        self._result: BackgroundResult | None = None
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()
        self._started_at: float = 0.0
        self._finished_at: float | None = None

    def start(self) -> str:
        """Start the background thread. Returns the session id."""
        if self._thread and self._thread.is_alive():
            return self.session_id
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name=f"BackgroundSession-{self.session_id}",
        )
        self._thread.start()
        return self.session_id

    def cancel(self) -> bool:
        """Request cancellation. Returns True if a cancel was signalled."""
        if self._state in (BackgroundState.COMPLETED, BackgroundState.FAILED, BackgroundState.CANCELLED):
            return False
        self._cancel.set()
        return True

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def status(self) -> dict[str, Any]:
        """Snapshot the current status as a dict (always safe to call)."""
        result = self._result
        if result is not None:
            return result.to_dict()
        return {
            "session_id": self.session_id,
            "prompt": self.prompt,
            "state": self._state.value,
            "output": self._read_output(),
            "error": None,
            "started_at": self._started_at,
            "finished_at": self._finished_at,
            "iterations": 0,
            "tokens_used": 0,
            "duration_s": (
                None
                if self._finished_at is None
                else (self._finished_at - self._started_at)
            ),
        }

    def get_output(self) -> str:
        """Read the full output so far."""
        return self._read_output()

    def wait(self, timeout: float | None = None) -> BackgroundResult | None:
        """Block until completion (or timeout). Returns the final result or None on timeout."""
        if self._thread:
            self._thread.join(timeout=timeout)
        return self._result

    def _append_output(self, line: str) -> None:
        with self._output_lock:
            self._output_lines.append(line)

    def _read_output(self) -> str:
        with self._output_lock:
            return "\n".join(self._output_lines)

    def _run(self) -> None:
        self._state = BackgroundState.RUNNING
        self._started_at = time.time()
        result = BackgroundResult(
            session_id=self.session_id,
            prompt=self.prompt,
            state=BackgroundState.RUNNING,
            started_at=self._started_at,
        )
        try:
            output = self._run_callable(self.prompt)
            if self._cancel.is_set():
                result.state = BackgroundState.CANCELLED
                result.output = output
            else:
                result.state = BackgroundState.COMPLETED
                result.output = output
        except (OSError, ValueError, RuntimeError, TypeError, ConnectionError) as e:
            result.state = BackgroundState.FAILED
            result.error = f"{type(e).__name__}: {e}"
            logger.error(f"Background session {self.session_id} failed: {e}")
        finally:
            self._finished_at = time.time()
            result.finished_at = self._finished_at
            self._state = result.state
            self._result = result
            if self._on_complete is not None:
                try:
                    self._on_complete(result)
                except (OSError, ValueError, TypeError, RuntimeError) as e:
                    logger.debug(f"on_complete callback failed: {e}")
