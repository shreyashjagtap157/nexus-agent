"""
TodoWrite Tool — Multi-step task tracking for the agent.

Maintains a list of todos with status (pending/in_progress/completed/
cancelled) and priority (low/medium/high/critical). The agent calls
this tool to:

- show the user a structured plan before starting work
- update the status of individual todos as it works
- cancel todos that turn out to be unnecessary

State is kept in-memory and (optionally) persisted to
`.nexus/todos.json` in the workspace so the user can `cat` the file
and watch progress in real time.

This tool is read-write but does not modify the user's code; it only
manages its own JSON state file.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from nexus_agent.tools.base import Tool

logger = logging.getLogger(__name__)


class TodoStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TodoPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_STATUS_ALIASES: dict[str, TodoStatus] = {
    "pending": TodoStatus.PENDING,
    "todo": TodoStatus.PENDING,
    "open": TodoStatus.PENDING,
    "in_progress": TodoStatus.IN_PROGRESS,
    "in-progress": TodoStatus.IN_PROGRESS,
    "inprogress": TodoStatus.IN_PROGRESS,
    "doing": TodoStatus.IN_PROGRESS,
    "active": TodoStatus.IN_PROGRESS,
    "wip": TodoStatus.IN_PROGRESS,
    "completed": TodoStatus.COMPLETED,
    "done": TodoStatus.COMPLETED,
    "finished": TodoStatus.COMPLETED,
    "cancelled": TodoStatus.CANCELLED,
    "canceled": TodoStatus.CANCELLED,
    "skipped": TodoStatus.CANCELLED,
    "dropped": TodoStatus.CANCELLED,
}

_PRIORITY_ALIASES: dict[str, TodoPriority] = {
    "low": TodoPriority.LOW,
    "l": TodoPriority.LOW,
    "medium": TodoPriority.MEDIUM,
    "med": TodoPriority.MEDIUM,
    "m": TodoPriority.MEDIUM,
    "normal": TodoPriority.MEDIUM,
    "high": TodoPriority.HIGH,
    "h": TodoPriority.HIGH,
    "important": TodoPriority.HIGH,
    "critical": TodoPriority.CRITICAL,
    "crit": TodoPriority.CRITICAL,
    "urgent": TodoPriority.CRITICAL,
    "blocker": TodoPriority.CRITICAL,
}


def _coerce_status(value: Any) -> TodoStatus:
    if isinstance(value, TodoStatus):
        return value
    if not isinstance(value, str):
        return TodoStatus.PENDING
    key = value.strip().lower().replace(" ", "_")
    return _STATUS_ALIASES.get(key, TodoStatus.PENDING)


def _coerce_priority(value: Any) -> TodoPriority:
    if isinstance(value, TodoPriority):
        return value
    if not isinstance(value, str):
        return TodoPriority.MEDIUM
    key = value.strip().lower()
    return _PRIORITY_ALIASES.get(key, TodoPriority.MEDIUM)


@dataclass
class Todo:
    id: str
    content: str
    status: TodoStatus = TodoStatus.PENDING
    priority: TodoPriority = TodoPriority.MEDIUM
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["priority"] = self.priority.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Todo:
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:8]),
            content=str(data.get("content", "")).strip(),
            status=_coerce_status(data.get("status", "pending")),
            priority=_coerce_priority(data.get("priority", "medium")),
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
            notes=str(data.get("notes", "")),
        )


def _slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^A-Za-z0-9_.-]+", "-", text.strip().lower())
    s = re.sub(r"-+", "-", s).strip("-")
    if not s:
        s = "todo"
    return s[:max_len]


class TodoStore:
    """In-memory todo list with optional JSON persistence."""

    def __init__(self, persist_path: Path | None = None) -> None:
        self._todos: dict[str, Todo] = {}
        self._persist_path = persist_path
        if persist_path and persist_path.exists():
            try:
                self._load_from_disk()
            except (OSError, ValueError, json.JSONDecodeError) as e:
                logger.warning(f"TodoStore: failed to load {persist_path}: {e}")

    def _load_from_disk(self) -> None:
        if not self._persist_path:
            return
        with self._persist_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data.get("todos", []):
            if isinstance(entry, dict):
                todo = Todo.from_dict(entry)
                self._todos[todo.id] = todo

    def _save_to_disk(self) -> None:
        if not self._persist_path:
            return
        payload = {
            "version": 1,
            "saved_at": time.time(),
            "todos": [t.to_dict() for t in self._todos.values()],
        }
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._persist_path.with_suffix(self._persist_path.suffix + ".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, sort_keys=True)
            tmp.replace(self._persist_path)
        except OSError as e:
            logger.warning(f"TodoStore: failed to save {self._persist_path}: {e}")

    def add(
        self,
        content: str,
        *,
        priority: TodoPriority | str = TodoPriority.MEDIUM,
        status: TodoStatus | str = TodoStatus.PENDING,
        todo_id: str | None = None,
        notes: str = "",
    ) -> Todo:
        tid = todo_id or f"{_slugify(content)}-{uuid.uuid4().hex[:4]}"
        if tid in self._todos:
            # Disambiguate on collision
            tid = f"{tid}-{uuid.uuid4().hex[:4]}"
        todo = Todo(
            id=tid,
            content=content.strip(),
            status=_coerce_status(status),
            priority=_coerce_priority(priority),
            notes=notes,
        )
        self._todos[tid] = todo
        self._save_to_disk()
        return todo

    def update(
        self,
        todo_id: str,
        *,
        status: TodoStatus | str | None = None,
        priority: TodoPriority | str | None = None,
        content: str | None = None,
        notes: str | None = None,
    ) -> Todo | None:
        todo = self._todos.get(todo_id)
        if todo is None:
            return None
        if status is not None:
            todo.status = _coerce_status(status)
        if priority is not None:
            todo.priority = _coerce_priority(priority)
        if content is not None and content.strip():
            todo.content = content.strip()
        if notes is not None:
            todo.notes = notes
        todo.updated_at = time.time()
        self._save_to_disk()
        return todo

    def remove(self, todo_id: str) -> bool:
        existed = self._todos.pop(todo_id, None) is not None
        if existed:
            self._save_to_disk()
        return existed

    def get(self, todo_id: str) -> Todo | None:
        return self._todos.get(todo_id)

    def list(
        self,
        *,
        status: TodoStatus | str | None = None,
        priority: TodoPriority | str | None = None,
    ) -> list[Todo]:
        items = list(self._todos.values())
        if status is not None:
            s = _coerce_status(status)
            items = [t for t in items if t.status == s]
        if priority is not None:
            p = _coerce_priority(priority)
            items = [t for t in items if t.priority == p]
        # Sort: critical > high > medium > low, then by created_at asc
        order = {
            TodoPriority.CRITICAL: 0,
            TodoPriority.HIGH: 1,
            TodoPriority.MEDIUM: 2,
            TodoPriority.LOW: 3,
        }
        items.sort(key=lambda t: (order.get(t.priority, 9), t.created_at))
        return items

    def clear_completed(self) -> int:
        """Remove all completed/cancelled todos. Returns count removed."""
        to_remove = [
            tid for tid, t in self._todos.items()
            if t.status in (TodoStatus.COMPLETED, TodoStatus.CANCELLED)
        ]
        for tid in to_remove:
            del self._todos[tid]
        if to_remove:
            self._save_to_disk()
        return len(to_remove)

    def clear_all(self) -> int:
        n = len(self._todos)
        self._todos.clear()
        if n:
            self._save_to_disk()
        return n

    def counts(self) -> dict[str, int]:
        c = {s.value: 0 for s in TodoStatus}
        for t in self._todos.values():
            c[t.status.value] += 1
        c["total"] = len(self._todos)
        return c


_STATUS_ICONS: dict[TodoStatus, str] = {
    TodoStatus.PENDING: "[ ]",
    TodoStatus.IN_PROGRESS: "[>]",
    TodoStatus.COMPLETED: "[x]",
    TodoStatus.CANCELLED: "[-]",
}

_PRIORITY_TAGS: dict[TodoPriority, str] = {
    TodoPriority.CRITICAL: "CRIT",
    TodoPriority.HIGH: "HIGH",
    TodoPriority.MEDIUM: "MED",
    TodoPriority.LOW: "LOW",
}


def format_todo_list(todos: list[Todo]) -> str:
    """Return a human-readable rendering of the todo list."""
    if not todos:
        return "(no todos)"
    lines: list[str] = []
    for t in todos:
        icon = _STATUS_ICONS.get(t.status, "[ ]")
        tag = _PRIORITY_TAGS.get(t.priority, "MED")
        line = f"{icon} {tag:4s}  [{t.id}]  {t.content}"
        if t.notes:
            for nl in t.notes.splitlines():
                line += f"\n         | {nl}"
        lines.append(line)
    return "\n".join(lines)


class TodoWriteTool(Tool):
    """Track multi-step tasks with priorities and statuses."""

    def __init__(self, persist_path: Path | None = None, store: TodoStore | None = None) -> None:
        self._store = store or TodoStore(persist_path=persist_path)

    @property
    def name(self) -> str:
        return "todowrite"

    @property
    def description(self) -> str:
        return (
            "Track multi-step work as a list of todos. Each todo has an id, "
            "content, status (pending/in_progress/completed/cancelled), and "
            "priority (low/medium/high/critical). Use the 'action' parameter to "
            "add/update/remove/list/clear_completed/clear_all. Useful for "
            "showing the user a structured plan and tracking progress."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "action": {
                "type": "string",
                "description": (
                    "What to do. One of: add, update, remove, list, "
                    "clear_completed, clear_all, get."
                ),
            },
            "content": {"type": "string", "description": "Todo content (for add/update).", "required": False},
            "todo_id": {"type": "string", "description": "Existing todo id (for update/remove/get).", "required": False},
            "status": {"type": "string", "description": "pending|in_progress|completed|cancelled", "required": False},
            "priority": {"type": "string", "description": "low|medium|high|critical", "required": False},
            "notes": {"type": "string", "description": "Optional free-form notes (add/update).", "required": False},
        }

    @property
    def required_params(self) -> list[str]:
        return ["action"]

    @property
    def permission_level(self) -> str:
        return "read-write"

    @property
    def timeout(self) -> int:
        return 5

    @property
    def store(self) -> TodoStore:
        return self._store

    def execute(
        self,
        action: str,
        content: str | None = None,
        todo_id: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        notes: str | None = None,
        **kwargs: Any,
    ) -> str:
        action = (action or "").strip().lower().replace("-", "_")
        if not action:
            return "Error: 'action' is required."

        if action == "add":
            if not content or not content.strip():
                return "Error: 'content' is required for action=add."
            todo = self._store.add(
                content,
                priority=priority or TodoPriority.MEDIUM,
                status=status or TodoStatus.PENDING,
                todo_id=todo_id,
                notes=notes or "",
            )
            return f"Added todo [{todo.id}]: {todo.content}"

        if action == "update":
            if not todo_id:
                return "Error: 'todo_id' is required for action=update."
            kwargs_update: dict[str, Any] = {}
            if status is not None:
                kwargs_update["status"] = status
            if priority is not None:
                kwargs_update["priority"] = priority
            if content is not None:
                kwargs_update["content"] = content
            if notes is not None:
                kwargs_update["notes"] = notes
            todo = self._store.update(todo_id, **kwargs_update)
            if todo is None:
                return f"Error: no todo with id '{todo_id}'."
            return f"Updated todo [{todo.id}]: {todo.status.value} / {todo.priority.value}"

        if action == "remove":
            if not todo_id:
                return "Error: 'todo_id' is required for action=remove."
            if self._store.remove(todo_id):
                return f"Removed todo [{todo_id}]."
            return f"Error: no todo with id '{todo_id}'."

        if action == "get":
            if not todo_id:
                return "Error: 'todo_id' is required for action=get."
            todo = self._store.get(todo_id)
            if todo is None:
                return f"Error: no todo with id '{todo_id}'."
            return format_todo_list([todo])

        if action == "list":
            todos = self._store.list()
            counts = self._store.counts()
            header = (
                f"Todos — total {counts['total']} | "
                f"pending {counts['pending']} | "
                f"in_progress {counts['in_progress']} | "
                f"completed {counts['completed']} | "
                f"cancelled {counts['cancelled']}"
            )
            return header + "\n" + format_todo_list(todos)

        if action == "clear_completed":
            n = self._store.clear_completed()
            return f"Cleared {n} completed/cancelled todo(s)."

        if action == "clear_all":
            n = self._store.clear_all()
            return f"Cleared all {n} todo(s)."

        return f"Error: unknown action {action!r}."

    def __repr__(self) -> str:
        return f"<Tool:{self.name} todos={self._store.counts()['total']}>"
