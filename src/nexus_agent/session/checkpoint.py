"""
Checkpoint System — File-level rollback inspired by claude-code's /rewind.

Creates snapshots of modified files at key points during a session,
allowing the user to roll back to any previous checkpoint.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Checkpoint:
    """A single checkpoint containing file snapshots."""

    def __init__(
        self,
        checkpoint_id: str,
        description: str,
        files: dict[str, str | None],
        timestamp: float,
        metadata: dict[str, Any] | None = None,
        data_dir: Path | None = None,
    ):
        self.id = checkpoint_id
        self.description = description
        self._files = files
        self._file_paths = list(files.keys())
        self.timestamp = timestamp
        self.metadata = metadata or {}
        self._data_dir = data_dir

    @property
    def files(self) -> dict[str, str | None]:
        """Lazy-load file contents on first access."""
        if self._data_dir and not self._files and self._file_paths:
            self._load_contents()
        return self._files

    def _load_contents(self) -> None:
        """Load file contents from checkpoint directory."""
        if not self._data_dir:
            return
        cp_dir = self._data_dir / self.id
        for file_path in self._file_paths:
            try:
                backup_file = cp_dir / CheckpointManager._safe_filename(file_path)
                if backup_file.exists():
                    self._files[file_path] = backup_file.read_text(encoding="utf-8", errors="replace")
                else:
                    self._files[file_path] = None
            except (OSError, UnicodeDecodeError, ValueError) as ex:
                logger.warning("Could not load backup file %s for checkpoint %s: %s", file_path, self.id, ex)
                self._files[file_path] = None

    def to_dict(self, max_content_length: int | None = None) -> dict[str, Any]:
        files = self.files
        if max_content_length is not None:
            files = {
                k: v[:max_content_length] + "..." if v and len(v) > max_content_length else v
                for k, v in files.items()
            }
        return {
            "id": self.id,
            "description": self.description,
            "files": files,
            "file_count": len(self.files),
            "timestamp": self.timestamp,
            "time_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp)),
            "metadata": self.metadata,
        }


class CheckpointManager:
    """Manages file checkpoints for rollback capability.

    Before the agent modifies files, a checkpoint is created storing
    the original contents. The user can then roll back to any
    checkpoint, restoring files to their previous state.

    Inspired by claude-code's /rewind command.
    """

    def __init__(self, data_dir: str | Path | None = None, max_checkpoints: int = 50):
        self.data_dir = Path(data_dir or "~/.nexus-agent/checkpoints").expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_checkpoints = max_checkpoints
        self._checkpoints: list[Checkpoint] = []
        self._load_index()

    def _index_path(self) -> Path:
        return self.data_dir / "index.json"

    def _load_index(self) -> None:
        """Load checkpoint index from disk."""
        index_path = self._index_path()
        if index_path.exists():
            try:
                data = json.loads(index_path.read_text())
                self._checkpoints = []
                for cp_data in data.get("checkpoints", []):
                    try:
                        file_paths = cp_data.get("file_paths", [])
                        files = {fp: None for fp in file_paths}
                        self._checkpoints.append(Checkpoint(
                            checkpoint_id=cp_data["id"],
                            description=cp_data.get("description", ""),
                            files=files,
                            timestamp=cp_data["timestamp"],
                            metadata=cp_data.get("metadata", {}),
                            data_dir=self.data_dir,
                        ))
                    except (KeyError, ValueError, TypeError, OSError) as cp_ex:
                        logger.warning("Could not load checkpoint %s: %s", cp_data['id'], cp_ex)
                        continue
            except (OSError, ValueError, KeyError) as e:
                logger.warning("Could not load checkpoint index: %s", e)

    def _save_index(self) -> None:
        """Save checkpoint index to disk atomically."""
        data = {
            "checkpoints": [
                {
                    "id": cp.id,
                    "description": cp.description,
                    "file_paths": list(cp.files.keys()),
                    "timestamp": cp.timestamp,
                    "metadata": cp.metadata,
                }
                for cp in self._checkpoints
            ]
        }
        fd, tmp_path = tempfile.mkstemp(
            suffix=".json",
            prefix="checkpoint_index_",
            dir=self.data_dir,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, self._index_path())
        except (OSError, ValueError, TypeError):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    @staticmethod
    def _safe_filename(file_path: str) -> str:
        """Convert a file path to a safe filename for storage."""
        return file_path.replace("/", "_").replace("\\", "_").replace(":", "_")

    def create(
        self,
        files_to_snapshot: list[str],
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Checkpoint:
        """Create a checkpoint by snapshotting the given files.

        Args:
            files_to_snapshot: List of file paths to back up.
            description: Human-readable description.
            metadata: Additional metadata.

        Returns:
            The created Checkpoint.
        """
        checkpoint_id = f"cp_{uuid.uuid4().hex[:16]}"
        cp_dir = self.data_dir / checkpoint_id
        cp_dir.mkdir(parents=True, exist_ok=True)

        files: dict[str, str | None] = {}

        for file_path in files_to_snapshot:
            path = Path(file_path).resolve()
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                    files[file_path] = content
                    # Save backup atomically
                    backup_path = cp_dir / self._safe_filename(file_path)
                    fd, tmp_path = tempfile.mkstemp(
                        suffix=".bak",
                        prefix=self._safe_filename(file_path) + "_",
                        dir=cp_dir,
                    )
                    try:
                        with os.fdopen(fd, "w", encoding="utf-8") as f:
                            f.write(content)
                        os.replace(tmp_path, backup_path)
                    except (OSError, ValueError, UnicodeEncodeError):
                        try:
                            os.unlink(tmp_path)
                        except OSError:
                            pass
                        raise
                except (OSError, UnicodeDecodeError, ValueError) as e:
                    logger.warning("Could not snapshot %s: %s", file_path, e)
                    files[file_path] = None
            else:
                files[file_path] = None  # File doesn't exist yet (will be created)

        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            description=description or f"Checkpoint at {time.strftime('%H:%M:%S')}",
            files=files,
            timestamp=time.time(),
            metadata=metadata,
        )

        self._checkpoints.append(checkpoint)

        # Trim old checkpoints
        while len(self._checkpoints) > self.max_checkpoints:
            old = self._checkpoints.pop(0)
            old_dir = self.data_dir / old.id
            if old_dir.exists():
                shutil.rmtree(old_dir, ignore_errors=True)

        self._save_index()
        logger.info(f"Checkpoint created: {checkpoint_id} ({len(files)} files)")

        return checkpoint

    def rollback(self, checkpoint_id: str) -> dict[str, str]:
        """Roll back to a specific checkpoint.

        Restores all files in the checkpoint to their original state.
        Files that didn't exist at checkpoint time are deleted.

        Args:
            checkpoint_id: ID of the checkpoint to roll back to.

        Returns:
            Dict of file_path → action taken ('restored', 'deleted', 'error').
        """
        checkpoint = self.get(checkpoint_id)
        if not checkpoint:
            raise LookupError(f"Checkpoint not found: {checkpoint_id}")

        results: dict[str, str] = {}

        for file_path, original_content in checkpoint.files.items():
            path = Path(file_path)
            try:
                if original_content is not None:
                    # Restore original content
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(original_content, encoding="utf-8")
                    results[file_path] = "restored"
                else:
                    # File was new — delete it
                    if path.exists():
                        path.unlink()
                        results[file_path] = "deleted"
                    else:
                        results[file_path] = "already_gone"
            except (OSError, ValueError, UnicodeEncodeError) as e:
                results[file_path] = f"error: {e}"
                logger.error(f"Rollback error for {file_path}: {e}")

        logger.info(f"Rolled back to checkpoint {checkpoint_id}: {results}")
        return results

    def get(self, checkpoint_id: str) -> Checkpoint | None:
        """Get a checkpoint by ID."""
        for cp in self._checkpoints:
            if cp.id == checkpoint_id:
                return cp
        return None

    def list_checkpoints(self) -> list[dict[str, Any]]:
        """List all checkpoints (most recent first)."""
        return [cp.to_dict() for cp in reversed(self._checkpoints)]

    def get_latest(self) -> Checkpoint | None:
        """Get the most recent checkpoint."""
        return self._checkpoints[-1] if self._checkpoints else None

    def clear(self) -> None:
        """Remove all checkpoints."""
        for cp in self._checkpoints:
            cp_dir = self.data_dir / cp.id
            if cp_dir.exists():
                shutil.rmtree(cp_dir, ignore_errors=True)
        self._checkpoints.clear()
        self._save_index()
