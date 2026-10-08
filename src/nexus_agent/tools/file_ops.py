"""
File Operations Tool — Read, write, search, and manage files.

Provides the agent with filesystem access for reading code,
writing changes, searching for patterns, and listing directories.
"""

from __future__ import annotations

import fnmatch
import logging
import re
from pathlib import Path
from typing import Any

from nexus_agent.tools.base import Tool, ToolError
from nexus_agent.storage.journal import FileJournal
from nexus_agent.utils.fs import iter_files

logger = logging.getLogger(__name__)


MAX_READ_SIZE = 10 * 1024 * 1024  # 10MB
MAX_WRITE_SIZE = 50 * 1024 * 1024  # 50MB

ALLOWED_SEARCH_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".rs",
    ".go",
    ".java",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".css",
    ".scss",
    ".less",
    ".html",
    ".xml",
    ".sql",
    ".sh",
    ".bat",
    ".ps1",
    ".cfg",
    ".ini",
    ".conf",
    ".env",
    ".gitignore",
    ".csv",
    ".rst",
    ".tex",
    ".vue",
    ".svelte",
}


class ReadFileTool(Tool):
    """Read the contents of a file."""

    def __init__(self, workspace: Path | None = None):
        self.workspace = (workspace or Path.cwd()).resolve()

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

    def execute(
        self, path: str, start_line: int | None = None, end_line: int | None = None, **kwargs: Any
    ) -> str:
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
    """Write content atomically and record an auditable file-change event."""

    def __init__(self, workspace: Path | None = None):
        self.workspace = (workspace or Path.cwd()).resolve()
        self._journal = FileJournal(self.workspace / ".nexus-agent" / "runtime" / "file-journal.db")

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
            previous_hash = FileJournal.digest_file(file_path)
            import os
            import tempfile
            fd, tmp = tempfile.mkstemp(prefix=".nexus-write-", dir=file_path.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp, file_path)
            finally:
                if os.path.exists(tmp):
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass
            new_hash = FileJournal.digest_file(file_path)
            self._journal.record(
                "write",
                str(file_path.relative_to(self.workspace)),
                previous_hash,
                new_hash,
            )
            return f"Successfully wrote {len(content)} characters to {path}"
        except OSError as e:
            logger.error("Error writing file %s: %s", path, e, exc_info=True)
            return "Error: Failed to write file."

    def _resolve_path(self, path: str) -> Path:
        return Tool.resolve_workspace_path(self.workspace, path)


class DeleteFileTool(Tool):
    """Delete files through the NexusAgent reversible-trash boundary."""

    def __init__(self, workspace: Path | None = None, trash_dir: Path | None = None):
        self.workspace = (workspace or Path.cwd()).resolve()
        self.trash_dir = (trash_dir or (self.workspace / ".nexus-agent" / "runtime" / "trash")).resolve()
        self._journal = FileJournal(self.workspace / ".nexus-agent" / "runtime" / "file-journal.db")
        self._journal = FileJournal(self.workspace / ".nexus-agent" / "runtime" / "file-journal.db")

    @property
    def name(self) -> str:
        return "delete_file"

    @property
    def description(self) -> str:
        return "Delete a file or empty directory. Files are moved to NexusAgent runtime trash by default so accidental deletion can be recovered."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "path": {"type": "string", "description": "Workspace-relative or absolute target path."},
            "permanent": {"type": "boolean", "description": "Permanently remove instead of moving to runtime trash. Use only when explicitly requested.", "required": False},
        }

    @property
    def permission_level(self) -> str:
        return "read-write"

    def execute(self, path: str, permanent: bool = False, **kwargs: Any) -> str:
        try:
            target = Tool.resolve_workspace_path(self.workspace, path)
        except (ValueError, ToolError):
            return "Error: Invalid path."
        if not target.exists() and not target.is_symlink():
            return "Error: Path not found."
        if target.resolve() == self.workspace or any(part == ".git" for part in target.parts):
            return "Error: Refusing to delete the workspace root or .git content."
        try:
            previous_hash = FileJournal.digest_file(target)
            if target.is_dir():
                if any(target.iterdir()):
                    return "Error: Refusing to delete a non-empty directory."
                target.rmdir()
                self._journal.record(
                    "delete_directory",
                    str(target.relative_to(self.workspace)),
                )
                return f"Deleted empty directory {path}."
            if permanent:
                previous_hash = FileJournal.digest_file(target)
                target.unlink()
                self._journal.record(
                    "delete_permanent",
                    str(target.relative_to(self.workspace)),
                    previous_hash,
                    None,
                )
                return f"Permanently deleted {path}."
            import time
            import uuid
            self.trash_dir.mkdir(parents=True, exist_ok=True)
            relative = target.relative_to(self.workspace)
            safe_name = f"{int(time.time())}-{uuid.uuid4().hex[:8]}-{relative.name}"
            destination = self.trash_dir / safe_name
            target.rename(destination)
            FileJournal(self.workspace / ".nexus-agent" / "runtime" / "file-journal.db").record(
                "delete_to_trash",
                str(relative),
                previous_hash,
                None,
                details={"trash_name": safe_name},
            )
            return f"Moved {path} to NexusAgent trash: {destination.relative_to(self.workspace)}"
        except (OSError, ValueError) as exc:
            return f"Error: delete failed: {exc}"


class RestoreFileTool(Tool):
    """Restore files from the NexusAgent runtime trash directory."""

    def __init__(self, workspace: Path | None = None, trash_dir: Path | None = None):
        self.workspace = (workspace or Path.cwd()).resolve()
        self.trash_dir = (trash_dir or (self.workspace / ".nexus-agent" / "runtime" / "trash")).resolve()

    @property
    def name(self) -> str:
        return "restore_file"

    @property
    def description(self) -> str:
        return "List trashed files or restore a trashed file to an explicit workspace destination."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "action": {"type": "string", "description": "list or restore"},
            "trash_name": {"type": "string", "description": "Filename inside the runtime trash directory.", "required": False},
            "destination": {"type": "string", "description": "Workspace-relative destination for restore.", "required": False},
        }

    @property
    def permission_level(self) -> str:
        return "read-write"

    def execute(self, action: str, trash_name: str = "", destination: str = "", **kwargs: Any) -> str:
        self.trash_dir.mkdir(parents=True, exist_ok=True)
        action = action.strip().lower()
        if action == "list":
            items = [p.name for p in sorted(self.trash_dir.iterdir(), key=lambda p: p.name) if p.is_file()]
            return "\n".join(items) or "Trash is empty."
        if action != "restore":
            return "Error: action must be list or restore."
        if not trash_name or not destination:
            return "Error: trash_name and destination are required for restore."
        item = (self.trash_dir / Path(trash_name).name).resolve()
        try:
            item.relative_to(self.trash_dir)
        except ValueError:
            return "Error: invalid trash item."
        if not item.is_file():
            return "Error: trash item not found."
        try:
            target = Tool.resolve_workspace_path(self.workspace, destination)
        except (ValueError, ToolError):
            return "Error: invalid destination."
        if target.exists():
            return "Error: destination already exists."
        if any(part == ".git" for part in target.parts):
            return "Error: refusing to restore into .git."
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            previous_hash = FileJournal.digest_file(item)
            item.rename(target)
            self._journal.record(
                "restore",
                str(target.relative_to(self.workspace)),
                previous_hash=previous_hash,
                new_hash=FileJournal.digest_file(target) if target.is_file() else None,
                details={"trash": str(item.relative_to(self.workspace))},
            )
            return f"Restored {destination}."
        except OSError as exc:
            return f"Error: restore failed: {exc}"


class MoveFileTool(Tool):
    """Move or rename a workspace file or empty directory."""

    def __init__(self, workspace: Path | None = None):
        self.workspace = (workspace or Path.cwd()).resolve()
        self._journal = FileJournal(self.workspace / ".nexus-agent" / "runtime" / "file-journal.db")

    @property
    def name(self) -> str:
        return "move_file"

    @property
    def description(self) -> str:
        return "Move or rename a workspace file or directory without allowing paths to escape the workspace."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "source": {"type": "string", "description": "Existing workspace-relative source path."},
            "destination": {"type": "string", "description": "Destination workspace-relative path."},
        }

    @property
    def permission_level(self) -> str:
        return "read-write"

    def execute(self, source: str, destination: str, **kwargs: Any) -> str:
        try:
            src = Tool.resolve_workspace_path(self.workspace, source)
            dst = Tool.resolve_workspace_path(self.workspace, destination)
        except (ValueError, ToolError):
            return "Error: Invalid path."
        if not src.exists():
            return "Error: Source not found."
        if dst.exists():
            return "Error: Destination already exists."
        if any(part == ".git" for part in src.parts + dst.parts):
            return "Error: .git paths are not mutable through this tool."
        try:
            previous_hash = FileJournal.digest_file(src)
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            new_hash = FileJournal.digest_file(dst)
            FileJournal(self.workspace / ".nexus-agent" / "runtime" / "file-journal.db").record(
                "move",
                str(dst.relative_to(self.workspace)),
                previous_hash,
                new_hash,
                details={"source": str(src.relative_to(self.workspace))},
            )
            return f"Moved {source} -> {destination}"
        except OSError as exc:
            return f"Error: move failed: {exc}"


class ParseDataTool(Tool):
    """Parse common structured data formats into bounded JSON."""

    def __init__(self, workspace: Path | None = None):
        self.workspace = (workspace or Path.cwd()).resolve()

    @property
    def name(self) -> str:
        return "parse_data"

    @property
    def description(self) -> str:
        return "Parse JSON, YAML, TOML, CSV, or XML files into structured data. Output is bounded to prevent context exhaustion."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "path": {"type": "string", "description": "Path to a structured data file."},
            "format": {"type": "string", "description": "auto, json, yaml, toml, csv, xml", "required": False},
            "max_chars": {"type": "integer", "description": "Maximum serialized output length.", "required": False},
        }

    @property
    def permission_level(self) -> str:
        return "read-only"

    def execute(self, path: str, format: str = "auto", max_chars: int = 50000, **kwargs: Any) -> str:
        try:
            target = Tool.resolve_workspace_path(self.workspace, path)
            raw = target.read_text(encoding="utf-8")
        except (ValueError, ToolError, OSError, UnicodeDecodeError):
            return "Error: unable to read structured data file."
        fmt = format.lower().strip()
        if fmt == "auto":
            fmt = target.suffix.lower().lstrip(".") or "text"
        try:
            if fmt == "json":
                import json
                data = json.loads(raw)
            elif fmt in {"yaml", "yml"}:
                import yaml
                data = yaml.safe_load(raw)
            elif fmt == "toml":
                import tomllib
                data = tomllib.loads(raw)
            elif fmt == "csv":
                import csv
                import io
                data = list(csv.DictReader(io.StringIO(raw)))
            elif fmt == "xml":
                import xml.etree.ElementTree as ET
                root = ET.fromstring(raw)
                data = self._xml_node(root)
            else:
                return f"Error: unsupported format {fmt!r}."
            import json
            encoded = json.dumps(data, ensure_ascii=False, indent=2, default=str)
            limit = max(100, min(int(max_chars), 2_000_000))
            return encoded[:limit] + ("\\n…[truncated]" if len(encoded) > limit else "")
        except (ValueError, TypeError, OSError, UnicodeDecodeError) as exc:
            return f"Error: parse failed: {exc}"

    def _xml_node(self, element: Any) -> dict[str, Any]:
        children = [self._xml_node(child) for child in list(element)]
        data: dict[str, Any] = {
            "tag": element.tag,
            "attributes": dict(element.attrib),
        }
        if element.text and element.text.strip():
            data["text"] = element.text.strip()
        if children:
            data["children"] = children
        return data


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

    def execute(
        self,
        pattern: str,
        path: str | None = None,
        include_glob: str | None = None,
        max_results: int = 50,
        **kwargs: Any,
    ) -> str:
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
        if re.search(r"\([^\)]*[\*\+\?][^\)]*\)[\*\+\?]", pattern):
            return "Error: Dangerous regular expression pattern (potential ReDoS nesting detected)."
        if re.search(r"\(\?:[^\)]*[\*\+\?][^\)]*\)[\*\+\?]", pattern):
            return "Error: Dangerous regular expression pattern (nested quantifiers in group)."
        if re.search(r"\[\^[^\]]*\][\*\+\?][\*\+\?]", pattern):
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
            file_iter = iter_files(search_path)

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

    def execute(
        self, path: str | None = None, recursive: bool = False, max_depth: int = 3, **kwargs: Any
    ) -> str:
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

    def _list_dir(
        self, path: Path, lines: list[str], prefix: str, recursive: bool, max_depth: int, depth: int
    ) -> None:
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
