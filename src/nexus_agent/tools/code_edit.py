"""
Code Editing Tool — Intelligent diff-based code editing.

Provides surgical code editing with search-and-replace,
line-range replacement, and diff preview capabilities.

For Python files, edits go through an AST-aware validation gate that:
  1. Compiles the original file to detect a pre-existing syntax error.
  2. After the textual edit, re-parses the result with ``ast.parse`` and refuses
     to write the file if the edit produced a broken module.
  3. Optionally rounds-trip through ``ast.unparse`` so indentation and spacing
     are normalised (set ``canonicalize=true`` in the call).
"""

from __future__ import annotations

import ast
import difflib
import logging
import re
from pathlib import Path
from typing import Any

from nexus_agent.tools.base import Tool, ToolError

logger = logging.getLogger(__name__)


_PY_SUFFIXES = {".py", ".pyi"}


def _ast_validate_python(source: str, path_label: str) -> str | None:
    """Return None if the source parses cleanly, else an error message."""
    try:
        ast.parse(source, filename=path_label)
        return None
    except SyntaxError as e:
        return (
            f"❌ AST validation failed for {path_label}: "
            f"line {e.lineno}, col {e.offset}: {e.msg}"
        )


def _ast_canonicalize(source: str) -> str | None:
    """Round-trip source via ``ast.unparse`` to normalise formatting.

    Returns ``None`` if the source cannot be parsed (caller should fall back to
    raw text). Preserves a trailing newline if one was present.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    trailing_nl = source.endswith("\n")
    try:
        unparsed = ast.unparse(tree)
    except (AttributeError, RecursionError, ValueError):
        return None
    return unparsed + ("\n" if trailing_nl and not unparsed.endswith("\n") else "")


class CodeEditTool(Tool):
    """Edit code files using search-and-replace with optional AST validation."""

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
            "For Python files, set validate_ast=true to refuse edits that produce "
            "syntax errors. Use this for precise, targeted edits rather than "
            "rewriting entire files."
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
            "validate_ast": {
                "type": "boolean",
                "description": "For Python files, refuse the edit if the result fails ast.parse (default: true)",
                "required": False,
            },
            "canonicalize": {
                "type": "boolean",
                "description": "For Python files, normalise the result via ast.unparse (default: false)",
                "required": False,
            },
        }

    @property
    def permission_level(self) -> str:
        return "read-write"

    def execute(self, path: str, old_content: str, new_content: str,
                **kwargs: Any) -> str:
        replace_all = kwargs.get("replace_all", False)
        validate_ast = kwargs.get("validate_ast", True)
        canonicalize = kwargs.get("canonicalize", False)

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

        is_python = file_path.suffix.lower() in _PY_SUFFIXES

        # AST gate: ensure the ORIGINAL file parses before we touch it.
        if is_python and validate_ast:
            pre_err = _ast_validate_python(original, str(file_path))
            if pre_err:
                return (
                    f"Error: Original file has a syntax error; refusing to edit "
                    f"until it is fixed.\n{pre_err}"
                )

        # Apply the edit
        new_file = original.replace(old_content, new_content, -1 if replace_all else 1)

        # AST gate: ensure the RESULT parses.
        if is_python and validate_ast:
            post_err = _ast_validate_python(new_file, str(file_path))
            if post_err:
                return (
                    f"Error: Edit would produce invalid Python; refusing to write.\n{post_err}\n"
                    f"Hint: try validate_ast=false if you really want to write it, "
                    f"or fix the syntax in new_content."
                )

        # Optional canonicalization (Python only)
        canonicalize_note = ""
        if is_python and canonicalize:
            canon = _ast_canonicalize(new_file)
            if canon is not None and canon != new_file:
                canonicalize_note = "\n(Normalised formatting via ast.unparse.)"
                new_file = canon

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

        return f"File edited successfully: {path}{canonicalize_note}\n\n```diff\n{diff_text}\n```"

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
        if not new_lines:
            # ``content`` was empty or only whitespace
            return f"No content to insert; nothing changed in {path}"
        if not new_lines[-1].endswith("\n"):
            # Ensure the inserted block is terminated with a newline so we
            # don't glue it onto the existing line at the splice point.
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
