"""
Session Storage — SQLite-backed conversation persistence.

Stores full conversation history, session metadata, and file
change tracking for the session management system.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import textwrap
import time
import uuid
from typing import Any

from nexus_agent.core.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


class SessionStorage(SQLiteStore):
    """SQLite-backed storage for session data.

    Stores:
    - Session metadata (id, model, provider, workspace, timestamps)
    - Conversation messages (full message history as JSON)
    - File changes tracked during the session
    """

    SCHEMA_SQL = textwrap.dedent("""\
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT DEFAULT '',
            model TEXT DEFAULT '',
            provider TEXT DEFAULT '',
            workspace TEXT DEFAULT '',
            mode TEXT DEFAULT 'auto',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            message_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            metadata TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            type TEXT DEFAULT '',
            content TEXT,
            tool_calls TEXT,
            tool_call_id TEXT,
            name TEXT,
            created_at REAL NOT NULL,
            metadata TEXT DEFAULT '{}',
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS file_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            file_path TEXT NOT NULL,
            change_type TEXT NOT NULL,
            original_content TEXT,
            new_content TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        -- Session replay trace: records every action for replay/debug
        CREATE TABLE IF NOT EXISTS session_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_data TEXT NOT NULL DEFAULT '{}',
            parent_event_id INTEGER,
            created_at REAL NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_file_changes_session ON file_changes(session_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at);
        CREATE INDEX IF NOT EXISTS idx_session_events_session ON session_events(session_id);
    """)

    def _init_db(self) -> None:
        super()._init_db()
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute("ALTER TABLE sessions ADD COLUMN mode TEXT DEFAULT 'auto'")
                conn.commit()
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE messages ADD COLUMN type TEXT DEFAULT ''")
                conn.commit()
            except sqlite3.OperationalError:
                pass

    def create_session(
        self,
        session_id: str,
        model: str = "",
        provider: str = "",
        workspace: str = "",
        title: str = "",
        mode: str = "auto",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Create a new session."""
        with self._lock:
            now = time.time()
            conn = self._get_conn()
            conn.execute(
                "INSERT OR IGNORE INTO sessions (id, title, model, provider, workspace, mode, created_at, updated_at, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, title, model, provider, workspace, mode, now, now,
                 json.dumps(metadata or {})),
            )
            conn.commit()

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str | None = None,
        tool_calls: list[dict] | None = None,
        tool_call_id: str | None = None,
        name: str | None = None,
        type: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Save a message to a session.

        Args:
            session_id: The session ID.
            role: Message role (user, assistant, system, tool).
            content: Message content.
            tool_calls: List of tool call dicts.
            tool_call_id: Tool call ID for tool messages.
            name: Name for assistant messages.
            type: UI event type (user, assistant, tool_call, tool_result, system, divider).
            metadata: Additional metadata dict.

        Returns:
            The row ID of the inserted message.
        """
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "INSERT INTO messages (session_id, role, type, content, tool_calls, tool_call_id, name, created_at, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, role, type, content,
                 json.dumps(tool_calls) if tool_calls is not None else None,
                 tool_call_id, name, time.time(),
                 json.dumps(metadata or {})),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ?, message_count = message_count + 1 WHERE id = ?",
                (time.time(), session_id),
            )
            conn.commit()
            return cursor.lastrowid

    def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Get all messages for a session."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            )
            messages = []
            for row in cursor:
                msg = dict(row)
                if msg.get("tool_calls"):
                    try:
                        msg["tool_calls"] = json.loads(msg["tool_calls"])
                    except (json.JSONDecodeError, TypeError):
                        msg["tool_calls"] = None
                if msg.get("metadata"):
                    try:
                        msg["metadata"] = json.loads(msg["metadata"])
                    except (json.JSONDecodeError, TypeError):
                        msg["metadata"] = {}
                messages.append(msg)
            return messages

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session metadata."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            row = cursor.fetchone()
            if row:
                session = dict(row)
                session["metadata"] = json.loads(session.get("metadata", "{}"))
                return session
            return None

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        """List sessions ordered by most recent."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            )
            sessions = []
            for row in cursor:
                s = dict(row)
                s["metadata"] = json.loads(s.get("metadata", "{}"))
                s["created"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(s["created_at"]))
                sessions.append(s)
            return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages."""
        with self._lock:
            conn = self._get_conn()
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM file_changes WHERE session_id = ?", (session_id,))
            cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0

    def track_file_change(
        self,
        session_id: str,
        file_path: str,
        change_type: str,
        original_content: str | None = None,
        new_content: str | None = None,
    ) -> None:
        """Track a file modification made during a session."""
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO file_changes (session_id, file_path, change_type, "
                "original_content, new_content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, file_path, change_type, original_content, new_content, time.time()),
            )
            conn.commit()

    def get_file_changes(self, session_id: str) -> list[dict[str, Any]]:
        """Get all file changes for a session."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT * FROM file_changes WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            )
            return [dict(row) for row in cursor]

    def update_session_title(self, session_id: str, title: str) -> None:
        """Update session title."""
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (title, time.time(), session_id),
            )
            conn.commit()

    def touch_session(self, session_id: str) -> None:
        """Update the updated_at timestamp of a session."""
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (time.time(), session_id),
            )
            conn.commit()

    def count_sessions(self) -> int:
        """Count total sessions."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("SELECT COUNT(*) as count FROM sessions")
            row = cursor.fetchone()
            return row["count"] if row else 0

    def get_messages_count(self, session_id: str) -> int:
        """Count messages in a session."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM messages WHERE session_id = ?",
                (session_id,),
            )
            row = cursor.fetchone()
            return row["count"] if row else 0

    # ── Session Replay (Goose-inspired event recording) ───────────────

    def record_event(
        self,
        session_id: str,
        event_type: str,
        event_data: dict[str, Any],
        parent_event_id: int | None = None,
    ) -> int:
        """Record a session event for replay/trace.

        Args:
            session_id: Session this event belongs to.
            event_type: Event category (prompt, tool_call, tool_result, file_change, error, etc.).
            event_data: Structured payload for the event.
            parent_event_id: Optional parent event ID (for building call trees).

        Returns:
            The row ID of the inserted event.
        """
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "INSERT INTO session_events "
                "(session_id, event_type, event_data, parent_event_id, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, event_type, json.dumps(event_data), parent_event_id, time.time()),
            )
            conn.commit()
            return cursor.lastrowid

    def record_tool_call_event(
        self,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        result: str | None = None,
        success: bool = True,
    ) -> int:
        """Record a tool call event for replay.

        Args:
            session_id: Session ID.
            tool_name: Name of the tool called.
            arguments: Arguments passed to the tool.
            result: Tool execution result (optional — populated on completion).
            success: Whether the tool call succeeded.

        Returns:
            Event ID.
        """
        return self.record_event(
            session_id=session_id,
            event_type="tool_call",
            event_data={
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
                "success": success,
            },
        )

    def get_session_events(
        self,
        session_id: str,
        event_type: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Get all recorded events for a session in chronological order.

        Args:
            session_id: Session ID.
            event_type: Optional filter by event type.
            limit: Maximum events to return.

        Returns:
            List of event dicts.
        """
        with self._lock:
            conn = self._get_conn()
            if event_type:
                cursor = conn.execute(
                    "SELECT * FROM session_events WHERE session_id = ? AND event_type = ? "
                    "ORDER BY created_at ASC LIMIT ?",
                    (session_id, event_type, limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM session_events WHERE session_id = ? "
                    "ORDER BY created_at ASC LIMIT ?",
                    (session_id, limit),
                )
            results = []
            for row in cursor:
                ev = dict(row)
                try:
                    ev["event_data"] = json.loads(ev["event_data"])
                except (json.JSONDecodeError, TypeError):
                    ev["event_data"] = {}
                results.append(ev)
            return results

    def get_session_event_tree(self, session_id: str) -> list[dict[str, Any]]:
        """Get session events structured as a tree (parent → children).

        Useful for visualizing the call chain during replay.

        Args:
            session_id: Session ID.

n        Returns:
            List of root events, each with a 'children' list.
        """
        events = self.get_session_events(session_id)
        event_map: dict[int, dict[str, Any]] = {}
        roots: list[dict[str, Any]] = []

        for ev in events:
            ev["children"] = []
            event_map[ev["id"]] = ev

        for ev in events:
            parent_id = ev.get("parent_event_id")
            if parent_id and parent_id in event_map:
                event_map[parent_id]["children"].append(ev)
            else:
                roots.append(ev)

        return roots

    def delete_session_events(self, session_id: str) -> int:
        """Delete all events for a session.

        Returns:
            Number of deleted events.
        """
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "DELETE FROM session_events WHERE session_id = ?",
                (session_id,),
            )
            conn.commit()
            return cursor.rowcount


