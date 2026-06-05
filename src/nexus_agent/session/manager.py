"""
Session Manager — Orchestrates session lifecycle.

Handles creating, resuming, saving, and listing sessions.
Integrates with SessionStorage for persistence and
CheckpointManager for rollback capability.
"""

from __future__ import annotations

import atexit
import logging
import signal
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from nexus_agent.session.checkpoint import CheckpointManager
from nexus_agent.session.storage import SessionStorage

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages the lifecycle of agent sessions.

    A session represents a single conversation with the agent,
    including all messages, tool calls, file changes, and checkpoints.

    Inspired by opencode's persistent session management.
    """

    _instances: list[SessionManager] = []

    def __init__(
        self,
        data_dir: str | Path | None = None,
        auto_save: bool = True,
        auto_save_interval: int = 30,
    ):
        self.data_dir = Path(data_dir or "~/.nexus-agent/sessions").expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.storage = SessionStorage(self.data_dir / "sessions.db")
        self.checkpoints = CheckpointManager(self.data_dir / "checkpoints")

        self.auto_save = auto_save
        self.auto_save_interval = auto_save_interval

        self._active_session_id: str | None = None
        self._last_save_time: float = 0

        SessionManager._instances.append(self)
        if len(SessionManager._instances) == 1:
            atexit.register(SessionManager._atexit_save_all)
            if threading.current_thread() is threading.main_thread():
                try:
                    signal.signal(signal.SIGINT, SessionManager._signal_handler)
                    sigterm = getattr(signal, 'SIGTERM', None)
                    if sigterm is not None:
                        signal.signal(sigterm, SessionManager._signal_handler)
                except (ValueError, RuntimeError, OSError):
                    pass

    @classmethod
    def _atexit_save_all(cls) -> None:
        for inst in cls._instances:
            try:
                inst.save_session()
            except (OSError, ValueError):
                pass

    @classmethod
    def _signal_handler(cls, signum: int, frame) -> None:
        logger.info("Received signal %s, saving sessions...", signum)
        cls._atexit_save_all()

    @property
    def active_session_id(self) -> str | None:
        """Get the currently active session ID."""
        return self._active_session_id

    def create_session(
        self,
        model: str = "",
        provider: str = "",
        workspace: str = "",
        title: str = "",
        mode: str = "auto",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create a new session.

        Args:
            model: Model name/path.
            provider: Provider name.
            workspace: Working directory.
            title: Session title.
            mode: Session operating mode.
            metadata: Additional metadata.

        Returns:
            New session ID.
        """
        session_id = uuid.uuid4().hex[:12]

        self.storage.create_session(
            session_id=session_id,
            model=model,
            provider=provider,
            workspace=workspace,
            title=title or f"Session {time.strftime('%Y-%m-%d %H:%M')}",
            mode=mode,
            metadata=metadata,
        )

        self._active_session_id = session_id
        self._last_save_time = time.time()

        logger.info(f"Created session: {session_id}")
        return session_id

    def resume_session(self, session_id: str) -> dict[str, Any] | None:
        """Resume an existing session.

        Args:
            session_id: Session ID (or prefix) to resume.

        Returns:
            Session data including messages, or None if not found.
        """
        if not session_id or not session_id.strip():
            return None
        # Support partial ID matching
        sessions = self.storage.list_sessions()
        match = None
        for s in sessions:
            if s["id"].startswith(session_id):
                match = s
                break

        if not match:
            logger.warning(f"Session not found: {session_id}")
            return None

        full_id = match["id"]
        self._active_session_id = full_id

        # Load messages
        messages = self.storage.get_messages(full_id)
        match["messages"] = messages

        logger.info(f"Resumed session: {full_id} ({len(messages)} messages)")
        return match

    def save_message(
        self,
        role: str,
        content: str | None = None,
        tool_calls: list[dict] | None = None,
        tool_call_id: str | None = None,
        name: str | None = None,
    ) -> None:
        """Save a message to the active session."""
        if not self._active_session_id:
            return

        self.storage.save_message(
            session_id=self._active_session_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            name=name,
        )

    def create_checkpoint(
        self,
        files: list[str],
        description: str = "",
    ) -> str:
        """Create a checkpoint for file rollback.

        Args:
            files: File paths to snapshot.
            description: Checkpoint description.

        Returns:
            Checkpoint ID.
        """
        cp = self.checkpoints.create(
            files_to_snapshot=files,
            description=description,
            metadata={"session_id": self._active_session_id},
        )
        return cp.id

    def rollback(self, checkpoint_id: str | None = None) -> dict[str, str]:
        """Roll back to a checkpoint.

        Args:
            checkpoint_id: Specific checkpoint ID, or None for latest.

        Returns:
            Dict of file_path → action taken.
        """
        if checkpoint_id is None:
            latest = self.checkpoints.get_latest()
            if not latest:
                raise ValueError("No checkpoints available")
            checkpoint_id = latest.id

        return self.checkpoints.rollback(checkpoint_id)

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        """List all sessions."""
        return self.storage.list_sessions(limit=limit)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        return self.storage.delete_session(session_id)

    def get_active_session(self) -> dict[str, Any] | None:
        """Get metadata of the active session."""
        if self._active_session_id:
            return self.storage.get_session(self._active_session_id)
        return None

    def track_file_change(
        self,
        file_path: str,
        change_type: str,
        original_content: str | None = None,
        new_content: str | None = None,
    ) -> None:
        """Track a file change in the active session."""
        if self._active_session_id:
            self.storage.track_file_change(
                session_id=self._active_session_id,
                file_path=file_path,
                change_type=change_type,
                original_content=original_content,
                new_content=new_content,
            )

    def auto_title(self, first_user_message: str) -> None:
        """Auto-generate session title from first user message."""
        if self._active_session_id:
            title = first_user_message[:80].strip()
            if len(first_user_message) > 80:
                title += "..."
            self.storage.update_session_title(self._active_session_id, title)

    def save_session(self) -> None:
        """Save the active session state to storage."""
        if not self._active_session_id:
            return
        try:
            self.storage.touch_session(self._active_session_id)
            self._last_save_time = time.time()
            logger.info(f"Saved session: {self._active_session_id}")
        except (OSError, ValueError, TypeError) as e:
            logger.error(f"Failed to save session {self._active_session_id}: {e}")

    def count_sessions(self) -> int:
        """Count total sessions in storage."""
        return self.storage.count_sessions()

    def get_messages_count(self, session_id: str | None = None) -> int:
        """Get message count for a session (defaults to active session)."""
        sid = session_id or self._active_session_id
        if not sid:
            return 0
        return self.storage.get_messages_count(sid)

    def fork_session(self, new_title: str | None = None) -> str | None:
        """Fork the active session as a new session with the same messages."""
        if not self._active_session_id:
            logger.warning("No active session to fork")
            return None
        src = self.storage.get_session(self._active_session_id)
        if not src:
            return None
        messages = self.storage.get_messages(self._active_session_id)
        new_id = self.create_session(
            model=src.get("model", ""),
            provider=src.get("provider", ""),
            workspace=src.get("workspace", ""),
            title=new_title or f"Fork of {src.get('title', self._active_session_id)}",
            mode=src.get("mode", "auto"),
        )
        for msg in messages:
            self.storage.save_message(
                session_id=new_id,
                role=msg.get("role", "user"),
                content=msg.get("content"),
                tool_calls=msg.get("tool_calls"),
                tool_call_id=msg.get("tool_call_id"),
                name=msg.get("name"),
            )
        logger.info(f"Forked session {self._active_session_id} → {new_id}")
        return new_id

    def rename_session(self, new_name: str) -> bool:
        """Rename the active session."""
        if self._active_session_id:
            self.storage.update_session_title(self._active_session_id, new_name)
            logger.info(f"Renamed session {self._active_session_id} to: {new_name}")
            return True
        return False

    def get_last_session_for_workspace(self, workspace: str) -> str | None:
        """Get the ID of the most recently updated session for a given workspace."""
        try:
            target_workspace = str(Path(workspace).resolve())
        except Exception:
            target_workspace = str(workspace)
        sessions = self.storage.list_sessions(limit=100)
        for s in sessions:
            ws = s.get("workspace")
            if ws:
                try:
                    ws_resolve = str(Path(ws).resolve())
                except Exception:
                    ws_resolve = str(ws)
                if ws_resolve == target_workspace:
                    return s["id"]
        return None

    def close(self) -> None:
        """Clean up resources."""
        self.save_session()
        self.storage.close()
