"""
Code Editing Tool — Intelligent diff-based code editing.

Provides surgical code editing with search-and-replace,
line-range replacement, and diff preview capabilities.
"""

from __future__ import annotations

import difflib
import logging
from pathlib import Path
from typing import Any

from nexus_agent.tools.base import Tool, ToolError

logger = logging.getLogger(__name__)


class CodeEditTool(Tool):
    """Edit code files using search-and-replace."""

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.cwd()

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return (
            "Edit a file by replacing specific content. Provide the exact text to find "
            "and the replacement text. The tool will show a diff of the changes. "
            "Use this for precise, targeted edits rather than rewriting entire files."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "path": {
                "type": "string",
                "description": "Path to the file to edit",
            },
            "old_content": {
                "type": "string",
                "description": "The exact text to find and replace (must match exactly)",
            },
            "new_content": {
                "type": "string",
                "description": "The replacement text",
            },
            "replace_all": {
                "type": "boolean",
                "description": "Replace all occurrences instead of just the first (default: false)",
                "required": False,
            },
        }

    @property
    def permission_level(self) -> str:
        return "read-write"

    def execute(self, path: str, old_content: str, new_content: str,
                **kwargs: Any) -> str:
        replace_all = kwargs.get("replace_all", False)

        if not old_content:
            return "Error: old_content cannot be empty."

        try:
            file_path = self._resolve_path(path)
        except (ValueError, ToolError) as e:
            logger.error("Path resolution failed for %s: %s", path, e, exc_info=True)
            return "Error: Invalid path."

        if not file_path.exists():
            return "Error: File not found."

        try:
            original = file_path.read_text(encoding="utf-8")
        except OSError as e:
            logger.error("Error reading file %s: %s", path, e, exc_info=True)
            return "Error: Failed to read file."

        # Check that old_content exists
        if old_content not in original:
            # Try to find a close match
            lines = original.splitlines()
            target_lines = old_content.splitlines()
            if target_lines:
                matches = difflib.get_close_matches(
                    target_lines[0], lines, n=3, cutoff=0.6
                )
                if matches:
                    suggestions = "\n".join(f"  - {m}" for m in matches)
                    return (
                        f"Error: Could not find the exact text to replace.\n"
                        f"Similar lines found:\n{suggestions}\n"
                        f"Please provide the exact text to match."
                    )
            return "Error: Could not find the exact text to replace in the file."

        # Count occurrences
        count = original.count(old_content)
        if count > 1 and not replace_all:
            return (
                f"Warning: Found {count} occurrences of the target text. "
                f"Set replace_all=true to replace all, or provide a more specific match."
            )

        # Apply the edit
        new_file = original.replace(old_content, new_content, -1 if replace_all else 1)

        # Generate diff
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            new_file.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
        diff_text = "\n".join(diff)

        # Write the file
        try:
            file_path.write_text(new_file, encoding="utf-8")
        except OSError as e:
            logger.error("Error writing file %s: %s", path, e, exc_info=True)
            return "Error: Failed to write file."

        return f"File edited successfully: {path}\n\n```diff\n{diff_text}\n```"

    def _resolve_path(self, path: str) -> Path:
        return Tool.resolve_workspace_path(self.workspace, path)


class InsertLinesTool(Tool):
    """Insert lines at a specific position in a file."""

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.cwd()

    @property
    def name(self) -> str:
        return "insert_lines"

    @property
    def description(self) -> str:
        return (
            "Insert new lines at a specific line number in a file. "
            "The new content is inserted before the specified line."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "path": {
                "type": "string",
                "description": "Path to the file",
            },
            "line_number": {
                "type": "integer",
                "description": "Line number to insert before (1-indexed)",
            },
            "content": {
                "type": "string",
                "description": "Content to insert",
            },
        }

    @property
    def permission_level(self) -> str:
        return "read-write"

    def execute(self, path: str, line_number: int, content: str,
                **kwargs: Any) -> str:
        try:
            file_path = self._resolve_path(path)
        except (ValueError, ToolError) as e:
            logger.error("Path resolution failed for %s: %s", path, e, exc_info=True)
            return "Error: Invalid path."

        if not file_path.exists():
            return "Error: File not found."

        try:
            original = file_path.read_text(encoding="utf-8")
            lines = original.splitlines(keepends=True)
        except OSError as e:
            logger.error("Error reading file %s: %s", path, e, exc_info=True)
            return "Error: Failed to read file."

        # Validate line_number range
        if line_number < 1 or line_number > len(lines) + 1:
            return f"Error: line_number {line_number} is out of range (file has {len(lines)} lines)."

        idx = line_number - 1

        # Insert content
        new_lines = content.splitlines(keepends=True)
        if new_lines and not new_lines[-1].endswith("\n"):
            # Only append \n if target file doesn't end with one
            if not original.endswith("\n"):
                new_lines[-1] += "\n"

        lines[idx:idx] = new_lines

        try:
            file_path.write_text("".join(lines), encoding="utf-8")
        except OSError as e:
            logger.error("Error writing file %s: %s", path, e, exc_info=True)
            return "Error: Failed to write file."

        return (
            f"Inserted {len(new_lines)} lines at line {line_number} in {path}"
        )

    def _resolve_path(self, path: str) -> Path:
        return Tool.resolve_workspace_path(self.workspace, path)
