"""
File Operations Tool — Read, write, search, and manage files.

Provides the agent with filesystem access for reading code,
writing changes, searching for patterns, and listing directories.
"""

from __future__ import annotations

import fnmatch
import logging
import os
import re
from pathlib import Path
from typing import Any

from nexus_agent.tools.base import Tool, ToolError

logger = logging.getLogger(__name__)


MAX_READ_SIZE = 10 * 1024 * 1024  # 10MB
MAX_WRITE_SIZE = 50 * 1024 * 1024  # 50MB

ALLOWED_SEARCH_EXTENSIONS = {
    ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml",
    ".js", ".ts", ".jsx", ".tsx", ".rs", ".go", ".java",
    ".c", ".h", ".cpp", ".hpp", ".css", ".scss", ".less",
    ".html", ".xml", ".sql", ".sh", ".bat", ".ps1",
    ".cfg", ".ini", ".conf", ".env", ".gitignore",
    ".csv", ".rst", ".tex", ".vue", ".svelte",
}


class ReadFileTool(Tool):
    """Read the contents of a file."""

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.cwd()

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            "Read the contents of a file at the given path. "
            "Returns the file contents with line numbers. "
            "Use start_line and end_line to read a specific range."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "path": {
                "type": "string",
                "description": "Path to the file (relative to workspace or absolute)",
            },
            "start_line": {
                "type": "integer",
                "description": "Start line number (1-indexed, optional)",
                "required": False,
            },
            "end_line": {
                "type": "integer",
                "description": "End line number (1-indexed, inclusive, optional)",
                "required": False,
            },
        }

    @property
    def permission_level(self) -> str:
        return "read-only"

    def execute(self, path: str, start_line: int | None = None,
                end_line: int | None = None, **kwargs: Any) -> str:
        try:
            file_path = self._resolve_path(path)
        except (ValueError, ToolError) as e:
            logger.error("Path resolution failed for %s: %s", path, e, exc_info=True)
            return "Error: Invalid path."

        if not file_path.exists():
            return "Error: File not found."

        if not file_path.is_file():
            return "Error: Not a file."

        # Enforce max read size to prevent OOM
        try:
            st_size = file_path.stat().st_size
            if st_size > MAX_READ_SIZE:
                return f"Error: File too large to read ({st_size / 1024 / 1024:.1f}MB > 10MB limit)"
        except OSError:
            return "Error: Cannot access file."

        try:
            content = file_path.read_text(encoding="utf-8", errors="strict")
        except UnicodeDecodeError as e:
            logger.warning("Encoding error reading %s: %s", path, e)
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError, ValueError) as e2:
                logger.error("Failed to read file %s: %s", path, e2, exc_info=True)
                return "Error: Failed to read file."
        except (OSError, ValueError) as e:
            logger.error("Failed to read file %s: %s", path, e, exc_info=True)
            return "Error: Failed to read file."

        lines = content.splitlines()
        total_lines = len(lines)

        # Apply line range
        if start_line is not None or end_line is not None:
            if start_line is not None and start_line < 1:
                return f"Error: start_line must be >= 1, got {start_line}."
            if end_line is not None and end_line < 1:
                return f"Error: end_line must be >= 1, got {end_line}."
            start = (start_line if start_line is not None else 1) - 1
            end = end_line if end_line is not None else total_lines
            if start < 0 or start >= total_lines:
                return f"Error: start_line {start_line} is out of range (file has {total_lines} lines)."
            if end < 1 or end > total_lines:
                return f"Error: end_line {end_line} is out of range (file has {total_lines} lines)."
            if start >= end:
                return "Error: start_line must be less than end_line."
            lines = lines[start:end]
            offset = start
        else:
            offset = 0
            # Limit output for very large files
            if total_lines > 500:
                lines = lines[:500]
                lines.append(f"... ({total_lines - 500} more lines)")

        # Add line numbers
        numbered = []
        for i, line in enumerate(lines):
            line_num = i + offset + 1
            numbered.append(f"{line_num:4d} | {line}")

        return "\n".join(numbered)

    def _resolve_path(self, path: str) -> Path:
        return Tool.resolve_workspace_path(self.workspace, path)


class WriteFileTool(Tool):
    """Write content to a file."""

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.cwd()

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return (
            "Write content to a file. Creates parent directories if needed. "
            "Use this for creating new files or completely replacing file contents."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "path": {
                "type": "string",
                "description": "Path to the file (relative to workspace or absolute)",
            },
            "content": {
                "type": "string",
                "description": "The content to write to the file",
            },
        }

    @property
    def permission_level(self) -> str:
        return "read-write"

    def execute(self, path: str, content: str, **kwargs: Any) -> str:
        try:
            file_path = self._resolve_path(path)
        except (ValueError, ToolError) as e:
            logger.error("Path resolution failed for %s: %s", path, e, exc_info=True)
            return "Error: Invalid path."

        # Block writes to .git/ paths to prevent hook injection
        if any(part.lower() == ".git" for part in file_path.parts):
            return "Error: Writing to .git/ paths is not allowed."

        # Enforce write size limit to prevent OOM
        content_bytes = content.encode("utf-8")
        if len(content_bytes) > MAX_WRITE_SIZE:
            return f"Error: Content too large to write ({len(content_bytes)} bytes > 50MB limit)"

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            # Validate created directories stay within workspace
            try:
                file_path.parent.resolve().relative_to(self.workspace.resolve())
            except ValueError:
                # Remove any created dirs if they escaped workspace
                if file_path.parent.exists() and file_path.parent != self.workspace:
                    try:
                        file_path.parent.rmdir()
                    except OSError:
                        pass
                return "Error: Directory creation would escape the workspace."
            file_path.write_text(content, encoding="utf-8")
            return f"Successfully wrote {len(content)} characters to {path}"
        except OSError as e:
            logger.error("Error writing file %s: %s", path, e, exc_info=True)
            return "Error: Failed to write file."

    def _resolve_path(self, path: str) -> Path:
        return Tool.resolve_workspace_path(self.workspace, path)


class SearchFilesTool(Tool):
    """Search for patterns in files using regex."""

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.cwd()

    @property
    def name(self) -> str:
        return "search_files"

    @property
    def description(self) -> str:
        return (
            "Search for a pattern (regex) across files in the workspace. "
            "Returns matching lines with file paths and line numbers. "
            "Use include_glob to filter by file type (e.g., '*.py')."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "pattern": {
                "type": "string",
                "description": "Regex pattern to search for",
            },
            "path": {
                "type": "string",
                "description": "Directory or file to search in (default: workspace root)",
                "required": False,
            },
            "include_glob": {
                "type": "string",
                "description": "Glob pattern to filter files (e.g., '*.py', '*.js')",
                "required": False,
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 50)",
                "required": False,
            },
        }

    @property
    def permission_level(self) -> str:
        return "read-only"

    def execute(self, pattern: str, path: str | None = None,
                include_glob: str | None = None,
                max_results: int = 50, **kwargs: Any) -> str:
        if path:
            try:
                search_path = Tool.resolve_workspace_path(self.workspace, path)
            except ValueError as e:
                logger.error("Path resolution failed: %s", e, exc_info=True)
                return "Error: Invalid path."
        else:
            search_path = self.workspace.resolve()

        if not search_path.exists():
            return "Error: Path not found."

        # ReDoS protection: block patterns with catastrophic backtracking risk
        if any(bad in pattern for bad in ["*+", "++", "?+", "*?", "+?", "??", "**"]):
            return "Error: Dangerous regular expression pattern (nested/consecutive quantifiers detected)."
        if re.search(r'\([^\)]*[\*\+\?][^\)]*\)[\*\+\?]', pattern):
            return "Error: Dangerous regular expression pattern (potential ReDoS nesting detected)."
        if re.search(r'\(\?:[^\)]*[\*\+\?][^\)]*\)[\*\+\?]', pattern):
            return "Error: Dangerous regular expression pattern (nested quantifiers in group)."
        if re.search(r'\[\^[^\]]*\][\*\+\?][\*\+\?]', pattern):
            return "Error: Dangerous regular expression pattern (consecutive quantifiers on character class)."
        # Pattern complexity check: reject excessively long patterns or those with too many groups
        if len(pattern) > 500:
            return "Error: Pattern too long (max 500 characters)."
        if pattern.count("(") > 20:
            return "Error: Pattern contains too many capturing groups (max 20)."

        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return f"Error: Invalid regex pattern: {e}"

        results: list[str] = []
        files_searched = 0

        # Get files to search using lazy evaluation
        if search_path.is_file():
            file_iter = iter([search_path])
        else:
            file_iter = self._iter_files(search_path)

        for file_path in file_iter:
            if not file_path.is_file():
                continue

            # Allow .env and .gitignore in search, skip all other hidden files
            if file_path.name.startswith(".") and file_path.name not in {".env", ".gitignore"}:
                continue

            # Apply glob filter
            if include_glob and not fnmatch.fnmatch(file_path.name, include_glob):
                continue

            # Skip common non-text directories
            skip_dirs = {"node_modules", "__pycache__", ".git", "venv", ".venv", "dist", "build"}
            if any(d in file_path.parts for d in skip_dirs):
                continue

            # Performance safety: skip files larger than 1MB
            try:
                if file_path.stat().st_size > 1 * 1024 * 1024:
                    continue
            except OSError:
                continue

            # Extension whitelist: only search text-based source files
            if file_path.suffix.lower() not in ALLOWED_SEARCH_EXTENSIONS:
                continue

            # Content safety: check first 1KB for null bytes to skip binary binaries
            try:
                with open(file_path, "rb") as f:
                    if b"\x00" in f.read(1024):
                        continue
            except (OSError, ValueError):
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                files_searched += 1
            except (OSError, UnicodeDecodeError, ValueError):
                continue

            content_lines = content.splitlines()
            for i, line in enumerate(content_lines, 1):
                if regex.search(line):
                    try:
                        rel_path = file_path.relative_to(self.workspace)
                    except ValueError:
                        rel_path = file_path
                    results.append(f"{rel_path}:{i}: {line.strip()}")

                    if len(results) >= max_results:
                        results.append(f"\n... (max {max_results} results reached)")
                        return "\n".join(results)

        if not results:
            return f"No matches found for '{pattern}' in {files_searched} files"

        return "\n".join(results)

    def _iter_files(self, search_path: Path):
        """Lazily iterate files under search_path using os.scandir to avoid OOM from rglob."""
        try:
            with os.scandir(str(search_path)) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            # Skip hidden directories (except .env, .gitignore)
                            if entry.name.startswith(".") and entry.name not in {".env", ".gitignore"}:
                                continue
                            skip_dirs = {"node_modules", "__pycache__", ".git", "venv", ".venv", "dist", "build"}
                            if entry.name in skip_dirs:
                                continue
                            yield from self._iter_files(Path(entry.path))
                        elif entry.is_file():
                            yield Path(entry.path)
                    except OSError:
                        continue
        except PermissionError:
            return
        except OSError:
            return


class ListDirectoryTool(Tool):
    """List directory contents with file info."""

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.cwd()

    @property
    def name(self) -> str:
        return "list_directory"

    @property
    def description(self) -> str:
        return (
            "List the contents of a directory. Shows files and subdirectories "
            "with sizes. Use recursive=true for a tree view."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "path": {
                "type": "string",
                "description": "Directory path (default: workspace root)",
                "required": False,
            },
            "recursive": {
                "type": "boolean",
                "description": "List recursively (default: false)",
                "required": False,
            },
            "max_depth": {
                "type": "integer",
                "description": "Maximum depth for recursive listing (default: 3)",
                "required": False,
            },
        }

    @property
    def permission_level(self) -> str:
        return "read-only"

    def execute(self, path: str | None = None, recursive: bool = False,
                max_depth: int = 3, **kwargs: Any) -> str:
        if path:
            try:
                dir_path = Tool.resolve_workspace_path(self.workspace, path)
            except ValueError as e:
                logger.error("Path resolution failed: %s", e, exc_info=True)
                return "Error: Invalid path."
        else:
            dir_path = self.workspace.resolve()

        if not dir_path.exists():
            return "Error: Directory not found."

        if not dir_path.is_dir():
            return "Error: Not a directory."

        lines: list[str] = []
        self._list_dir(dir_path, lines, "", recursive, max_depth, 0)

        if not lines:
            return "Empty directory"

        return "\n".join(lines)

    def _list_dir(self, path: Path, lines: list[str], prefix: str,
                  recursive: bool, max_depth: int, depth: int) -> None:
        if depth > max_depth:
            lines.append(f"{prefix}... (max depth reached)")
            return

        try:
            entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            lines.append(f"{prefix}[Permission denied]")
            return
        except FileNotFoundError:
            lines.append(f"{prefix}[Directory removed during listing]")
            return

        # Skip hidden and common non-relevant dirs
        skip = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox"}

        for entry in entries:
            if entry.name.startswith(".") and entry.name not in {".env", ".gitignore"}:
                continue
            if entry.name in skip:
                continue

            if entry.is_dir():
                try:
                    child_count = sum(1 for _ in entry.iterdir()) if entry.exists() else 0
                except (PermissionError, FileNotFoundError):
                    child_count = 0
                lines.append(f"{prefix}[DIR] {entry.name}/ ({child_count} items)")
                if recursive:
                    self._list_dir(entry, lines, prefix + "  ", True, max_depth, depth + 1)
            else:
                try:
                    size = entry.stat().st_size
                    size_str = self._format_size(size)
                except OSError:
                    size_str = "?B"
                lines.append(f"{prefix}[FILE] {entry.name} ({size_str})")

    @staticmethod
    def _format_size(size: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
