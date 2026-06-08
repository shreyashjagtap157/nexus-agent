"""
Session Manager — Orchestrates session lifecycle.

Handles creating, resuming, saving, and listing sessions.
Integrates with SessionStorage for persistence and
CheckpointManager for rollback capability.
"""

from __future__ import annotations

import atexit
import json
import logging
import signal
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from nexus_agent.session.checkpoint import CheckpointManager
from nexus_agent.session.storage import SessionStorage

logger = logging.getLogger(__name__)


SCHEMA_VERSION = 1


def sid_safe(s: str) -> str:
    """Return the first 12 chars of an id, or '?' if empty."""
    return (s or "?")[:12]


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
        self._autosave_thread: threading.Thread | None = None
        self._autosave_stop = threading.Event()
        self._background_sessions: dict[str, "BackgroundSession"] = {}
        self._background_lock = threading.Lock()

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

        if self.auto_save and self.auto_save_interval > 0:
            self._start_autosave()

    @classmethod
    def _atexit_save_all(cls) -> None:
        for inst in cls._instances:
            try:
                inst.save_session()
            except (OSError, ValueError, sqlite3.Error, RuntimeError):
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
        type: str = "",
    ) -> None:
        """Save a message to the active session.

        Args:
            role: Message role (user, assistant, system, tool).
            content: Message content.
            tool_calls: List of tool call dicts.
            tool_call_id: Tool call ID for tool messages.
            name: Name for assistant messages.
            type: UI event type (user, assistant, tool_call, tool_result, system, divider).
        """
        if not self._active_session_id:
            return

        self.storage.save_message(
            session_id=self._active_session_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            name=name,
            type=type,
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

    def rename(self, new_name: str) -> bool:
        """Alias for :meth:`rename_session` (matches the `/rename` slash command)."""
        return self.rename_session(new_name)

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

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def close(self) -> None:
        """Clean up resources."""
        self._stop_autosave()
        self.save_session()
        self.storage.close()

    def _start_autosave(self) -> None:
        """Start the background autosave timer thread."""
        if self._autosave_thread and self._autosave_thread.is_alive():
            return
        self._autosave_stop.clear()
        self._autosave_thread = threading.Thread(
            target=self._autosave_loop,
            daemon=True,
            name=f"SessionManager-autosave-{id(self)}",
        )
        self._autosave_thread.start()
        logger.debug(f"Autosave started (interval={self.auto_save_interval}s)")

    def _stop_autosave(self) -> None:
        """Stop the background autosave timer thread."""
        self._autosave_stop.set()
        if self._autosave_thread and self._autosave_thread.is_alive():
            self._autosave_thread.join(timeout=2.0)
        self._autosave_thread = None

    def _autosave_loop(self) -> None:
        """Background loop that periodically saves the active session."""
        while not self._autosave_stop.wait(self.auto_save_interval):
            try:
                self.save_session()
            except (OSError, ValueError, TypeError, RuntimeError) as e:
                logger.debug(f"Autosave error: {e}")

    def get_messages(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Get messages for the active session.

        Args:
            limit: Optional max number of most-recent messages to return.

        Returns:
            List of message dicts in chronological order.
        """
        if not self._active_session_id:
            return []
        msgs = self.storage.get_messages(self._active_session_id)
        if limit is not None and limit > 0:
            return msgs[-limit:]
        return msgs

    def get_session_info(self) -> dict[str, Any]:
        """Get a human-readable info dict for the active session."""
        info: dict[str, Any] = {
            "active_session_id": self._active_session_id or "(none)",
            "total_sessions": self.count_sessions(),
        }
        if self._active_session_id:
            session = self.storage.get_session(self._active_session_id)
            if session:
                info.update(
                    {
                        "title": session.get("title", ""),
                        "model": session.get("model", ""),
                        "provider": session.get("provider", ""),
                        "mode": session.get("mode", "auto"),
                        "status": session.get("status", "active"),
                        "message_count": session.get("message_count", 0),
                        "created": session.get("created", ""),
                        "updated": session.get("updated", ""),
                    }
                )
            info["active_message_count"] = self.get_messages_count()
        return info

    def export_session(self, session_id: str | None = None) -> dict[str, Any]:
        """Export a session (default: active) to a portable JSON-serializable dict.

        Format:
            {
                "schema_version": 1,
                "exported_at": <unix-ts>,
                "session": { ...full session row... },
                "messages": [ ...message dicts... ],
                "file_changes": [ ...file change dicts... ],
            }
        """
        sid = session_id or self._active_session_id
        if not sid:
            raise ValueError("No session to export (no active session and no id given)")
        session = self.storage.get_session(sid)
        if not session:
            raise ValueError(f"Session not found: {sid}")
        messages = self.storage.get_messages(sid)
        file_changes = self.storage.get_file_changes(sid)
        return {
            "schema_version": SCHEMA_VERSION,
            "exported_at": time.time(),
            "session": session,
            "messages": messages,
            "file_changes": file_changes,
        }

    def import_session(self, src: str | Path) -> str | None:
        """Import a session from a JSON file produced by `export_session`.

        Returns the new session id, or None on failure.
        """
        path = Path(src)
        if not path.exists():
            raise FileNotFoundError(f"Import file not found: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"Invalid session file: {e}") from e
        if not isinstance(payload, dict):
            raise ValueError("Invalid session file: top-level must be an object")
        if "session" not in payload:
            raise ValueError("Invalid session file: missing 'session' field")
        schema_version = int(payload.get("schema_version", 0))
        if schema_version > SCHEMA_VERSION:
            raise ValueError(
                f"Session file is from a newer version (schema={schema_version}); "
                f"this build supports up to schema={SCHEMA_VERSION}"
            )
        src_session = payload.get("session", {})
        new_id = self.create_session(
            model=src_session.get("model", ""),
            provider=src_session.get("provider", ""),
            workspace=src_session.get("workspace", ""),
            title=(src_session.get("title", "Imported session") + " (imported)"),
            mode=src_session.get("mode", "auto"),
            metadata=src_session.get("metadata", {}),
        )
        for msg in payload.get("messages", []):
            try:
                self.storage.save_message(
                    session_id=new_id,
                    role=msg.get("role", "user"),
                    content=msg.get("content"),
                    tool_calls=msg.get("tool_calls"),
                    tool_call_id=msg.get("tool_call_id"),
                    name=msg.get("name"),
                    type=msg.get("type", ""),
                )
            except (OSError, ValueError, TypeError) as e:
                logger.warning(f"Skipping message during import: {e}")
        for fc in payload.get("file_changes", []):
            try:
                self.storage.track_file_change(
                    session_id=new_id,
                    file_path=fc.get("file_path", ""),
                    change_type=fc.get("change_type", "edit"),
                    original_content=fc.get("original_content"),
                    new_content=fc.get("new_content"),
                )
            except (OSError, ValueError, TypeError) as e:
                logger.warning(f"Skipping file change during import: {e}")
        logger.info(f"Imported session {sid_safe(src_session.get('id', '?'))} → {new_id}")
        return new_id

    # ── Session Replay (Goose-inspired) ──────────────────────────────

    def record_event(
        self,
        event_type: str,
        event_data: dict[str, Any],
        parent_event_id: int | None = None,
    ) -> int | None:
        """Record a session event for replay.

        Args:
            event_type: Event category (prompt, tool_call, tool_result, etc.).
            event_data: Structured payload.
            parent_event_id: Optional parent event ID.

        Returns:
            Event row ID, or None if no active session.
        """
        if not self._active_session_id:
            return None
        return self.storage.record_event(
            session_id=self._active_session_id,
            event_type=event_type,
            event_data=event_data,
            parent_event_id=parent_event_id,
        )

    def record_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: str | None = None,
        success: bool = True,
    ) -> int | None:
        """Record a tool call for replay."""
        if not self._active_session_id:
            return None
        return self.storage.record_tool_call_event(
            session_id=self._active_session_id,
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            success=success,
        )

    def get_session_trace(
        self,
        session_id: str | None = None,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get a replayable trace of session events.

        Args:
            session_id: Session ID (defaults to active session).
            event_type: Optional filter by event type.

        Returns:
            Chronological list of events with deserialized payloads.
        """
        sid = session_id or self._active_session_id
        if not sid:
            return []
        return self.storage.get_session_events(
            session_id=sid,
            event_type=event_type,
        )

    def get_session_event_tree(self, session_id: str | None = None) -> list[dict[str, Any]]:
        """Get session events as a parent-child tree for visualization."""
        sid = session_id or self._active_session_id
        if not sid:
            return []
        return self.storage.get_session_event_tree(session_id=sid)

    def replay_session(
        self,
        session_id: str,
        target_role: str = "user",
    ) -> list[dict[str, Any]]:
        """Replay a session by extracting its prompt/response pairs.

        Returns a list of sequential actions that can be fed back to the
        agent to reproduce the session's behavior. This is a "trace" replay:
        it extracts the prompts and results, not the actual LLM calls.

        Args:
            session_id: The session to replay.
            target_role: Which role's events to extract ("user" = prompts,
                "assistant" = responses, "tool" = tool results).

        Returns:
            List of replay events in chronological order.
        """
        messages = self.storage.get_messages(session_id)
        events = self.storage.get_session_events(session_id)

        replay: list[dict[str, Any]] = []

        # First add message replay
        for msg in messages:
            if target_role and msg.get("role") != target_role:
                continue
            replay.append({
                "type": "message",
                "role": msg.get("role"),
                "content": msg.get("content"),
                "timestamp": msg.get("created_at"),
            })

        # Then add tool call replay
        for ev in events:
            if target_role == "tool" and ev.get("event_type") != "tool_call":
                continue
            replay.append({
                "type": "event",
                "event_type": ev.get("event_type"),
                "data": ev.get("event_data", {}),
                "timestamp": ev.get("created_at"),
            })

        replay.sort(key=lambda x: x.get("timestamp", 0))
        return replay

    def export_replay(
        self,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Export a full replay package: messages + events + file changes.

        The output is suitable for debugging, testing, or sharing.

        Args:
            session_id: Session ID (defaults to active session).

        Returns:
            Dict with 'messages', 'events', 'file_changes', 'session_metadata'.
        """
        sid = session_id or self._active_session_id
        if not sid:
            return {"error": "No active session"}

        session = self.storage.get_session(sid) or {}
        messages = self.storage.get_messages(sid)
        events = self.storage.get_session_events(sid)
        file_changes = self.storage.get_file_changes(sid)

        return {
            "session_id": sid,
            "session_metadata": {
                "title": session.get("title"),
                "model": session.get("model"),
                "provider": session.get("provider"),
                "workspace": session.get("workspace"),
                "created_at": session.get("created_at"),
                "message_count": session.get("message_count"),
            },
            "messages": messages,
            "events": events,
            "file_changes": file_changes,
        }

    # ── Background Sessions ───────────────────────────────────────────

    def list_background_sessions(self) -> list[dict[str, Any]]:
        """List all running background sessions."""
        with self._background_lock:
            return [bg.status() for bg in self._background_sessions.values()]

    def get_background_session(self, session_id: str) -> "BackgroundSession | None":
        """Get a background session by id (supports prefix match)."""
        with self._background_lock:
            for sid, bg in self._background_sessions.items():
                if sid == session_id or sid.startswith(session_id):
                    return bg
        return None

    def register_background(self, bg: "BackgroundSession") -> None:
        with self._background_lock:
            self._background_sessions[bg.session_id] = bg

    def unregister_background(self, session_id: str) -> None:
        with self._background_lock:
            self._background_sessions.pop(session_id, None)
