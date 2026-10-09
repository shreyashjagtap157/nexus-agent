"""Restore files from NexusAgent's reversible runtime trash."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from nexus_agent.tools.base import Tool


class RestoreFileTool(Tool):
    def __init__(self, workspace: Path | None = None, trash_dir: Path | None = None):
        self.workspace = (workspace or Path.cwd()).resolve()
        self.trash_dir = (
            trash_dir or (self.workspace / ".nexus-agent" / "runtime" / "trash")
        ).resolve()

    @property
    def name(self) -> str:
        return "restore_file"

    @property
    def description(self) -> str:
        return "List or restore files from NexusAgent runtime trash after reversible deletion."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "action": {"type": "string", "description": "list or restore"},
            "trash_name": {"type": "string", "description": "Trash filename returned by list"},
            "destination": {
                "type": "string",
                "description": "Workspace-relative restore destination; required for restore",
            },
        }

    @property
    def permission_level(self) -> str:
        return "read-write"

    def execute(
        self, action: str, trash_name: str = "", destination: str = "", **kwargs: Any
    ) -> str:
        self.trash_dir.mkdir(parents=True, exist_ok=True)
        action = action.strip().lower()
        if action == "list":
            items = sorted(self.trash_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
            return (
                "\n".join(
                    f"{p.name} ({p.stat().st_size} bytes)" for p in items[:500] if p.is_file()
                )
                or "Trash is empty."
            )
        if action != "restore":
            return "Error: action must be list or restore."
        if not trash_name or not destination:
            return "Error: trash_name and destination are required."
        source = (self.trash_dir / Path(trash_name).name).resolve()
        target = (self.workspace / destination).resolve()
        try:
            target.relative_to(self.workspace)
        except ValueError:
            return "Error: destination escapes workspace."
        if not source.exists() or not source.is_file():
            return "Error: trash entry not found."
        if target.exists():
            return "Error: destination already exists."
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        return f"Restored {destination}."
