"""Batch Edit Tool — Claude-code-style atomic multi-file search-and-replace editor."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from nexus_agent.tools.base import Tool

logger = logging.getLogger(__name__)


class BatchEditTool(Tool):
    """Atomic multi-file search-replace tool.

    Allows editing multiple contiguous blocks of code across several files in
    a single transaction. Ensures atomicity: if any individual edit fails, all
    previously edited files are immediately rolled back.
    """

    def __init__(self, workspace: Path):
        super().__init__()
        self.workspace = Path(workspace).resolve()

    @property
    def name(self) -> str:
        return "batch_edit"

    @property
    def description(self) -> str:
        return (
            "Perform multiple precise search-and-replace edits across one or more files. "
            "This operation is fully atomic: if any search block cannot be located or is "
            "ambiguous, the entire batch is rolled back to protect the codebase."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "edits": {
                "type": "array",
                "description": "List of individual search-replace edit structures.",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Workspace relative or absolute path to target file.",
                        },
                        "target_content": {
                            "type": "string",
                            "description": "The exact block of code to search for. Must match exactly including indentation.",
                        },
                        "replacement_content": {
                            "type": "string",
                            "description": "The block of code to replace the target content with.",
                        }
                    },
                    "required": ["path", "target_content", "replacement_content"],
                }
            }
        }

    @property
    def required_params(self) -> list[str]:
        return ["edits"]

    @property
    def permission_level(self) -> str:
        return "read-write"

    def execute(self, edits: list[dict[str, str]]) -> str:
        if not edits:
            return "No edits were submitted. Nothing to change."

        for edit in edits:
            if not isinstance(edit, dict):
                return "Error: Each edit must be a dictionary with path, target_content, and replacement_content."
            if "path" not in edit or "target_content" not in edit or "replacement_content" not in edit:
                return "Error: Each edit must have path, target_content, and replacement_content fields."

        in_memory_files: dict[Path, str] = {}
        original_contents: dict[Path, str] = {}
        error_msg = None

        try:
            for idx, edit in enumerate(edits):
                rel_path = edit["path"]
                target = edit["target_content"]
                replacement = edit["replacement_content"]

                try:
                    target_file = Tool.resolve_workspace_path(self.workspace, rel_path)
                except ValueError as e:
                    error_msg = f"Path escapes workspace: {rel_path} ({e})"
                    raise ValueError(error_msg)

                if not target_file.exists():
                    error_msg = f"File not found to edit: {rel_path}"
                    raise FileNotFoundError(error_msg)

                max_size = 10 * 1024 * 1024
                try:
                    file_size = target_file.stat().st_size
                except OSError as e:
                    error_msg = f"Cannot stat file {rel_path}: {e}"
                    raise OSError(error_msg) from e
                if file_size > max_size:
                    error_msg = f"File too large for batch edit: {rel_path} ({file_size / 1024 / 1024:.1f}MB > 10MB)"
                    raise ValueError(error_msg)

                if target_file in in_memory_files:
                    content = in_memory_files[target_file]
                else:
                    content = target_file.read_text(encoding="utf-8")
                    original_contents[target_file] = content
                    in_memory_files[target_file] = content

                occurrences = content.count(target)
                if occurrences == 0:
                    error_msg = (
                        f"Search block at index {idx} in {rel_path} could not be located. "
                        f"Ensure the code block matches spaces, lines, and characters exactly."
                    )
                    raise ValueError(error_msg)
                elif occurrences > 1:
                    matches = []
                    for li, line in enumerate(content.splitlines(), 1):
                        if target in line:
                            matches.append(f"  line {li}")
                    error_msg = (
                        f"Search block at index {idx} in {rel_path} matched {occurrences} times. "
                        f"Found at: {', '.join(matches[:5])}. "
                        f"Submit a larger unique block to resolve ambiguity."
                    )
                    raise ValueError(error_msg)

                in_memory_files[target_file] = content.replace(target, replacement, 1)

            completed_paths: list[Path] = []
            for target_file, modified_text in in_memory_files.items():
                self._atomic_write(target_file, modified_text.encode("utf-8"))
                completed_paths.append(target_file)

            summary = []
            for path in completed_paths:
                summary.append(f"  - Clean replacement completed: {path.relative_to(self.workspace)}")
            return (
                f"✅ Atomic batch transaction succeeded! Successfully modified {len(completed_paths)} files:\n" +
                "\n".join(summary)
            )

        except (ValueError, FileNotFoundError, OSError) as e:
            logger.warning(f"Batch edit failed: {e}. Initiating rollback transaction...")
            for path, original_text in original_contents.items():
                try:
                    current_on_disk = path.read_text(encoding="utf-8")
                    if current_on_disk != original_text:
                        logger.error(
                            f"Rollback aborted for {path}: file was modified on disk after our write. "
                            f"Manual intervention required."
                        )
                        continue
                    self._atomic_write(path, original_text.encode("utf-8"))
                except (OSError, ValueError) as re:
                    logger.error(f"FATAL: Rollback failure for file {path}: {re}")
            raise RuntimeError(f"Batch edit failed: {e}") from e

        finally:
            in_memory_files.clear()
            original_contents.clear()

    def _atomic_write(self, path: Path, data: bytes) -> None:
        dir_path = path.parent
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except (OSError, ValueError):
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
