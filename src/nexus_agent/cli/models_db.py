"""Model storage — stores models with metadata, usage stats, and capabilities.

Extended schema supports tracking context size, capabilities, usage
statistics, and provider information for each model entry.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MODELS_DB_FILENAME = "models_db.json"


class ModelsDB:
    """Persistent storage for model entries with extended metadata.

    Schema per model entry::

        {
            "name": "claude-sonnet-4",
            "path_or_id": "claude-sonnet-4-20250514",
            "provider": "anthropic",
            "context_size": 200000,
            "capabilities": {
                "vision": true,
                "tool_calling": true,
                "streaming": true
            },
            "last_used": "2026-05-27T12:00:00Z",
            "total_tokens": 0,
            "total_cost": 0.0,
            "sessions": 0,
            "added": "2026-05-27T12:00:00Z"
        }

    Backward-compatible: entries that are plain strings (old format)
    are automatically migrated to the extended schema on load.
    """

    def __init__(self, data_dir: str | None = None):
        if data_dir:
            self._path = Path(data_dir) / MODELS_DB_FILENAME
        else:
            self._path = Path.home() / ".nexus-agent" / MODELS_DB_FILENAME
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._models: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self):
        try:
            if self._path.exists():
                with open(str(self._path), encoding="utf-8") as f:
                    raw = json.load(f)
                # Migrate old format: {name: path_string} → {name: dict}
                if isinstance(raw, dict):
                    for name, value in raw.items():
                        if isinstance(value, str):
                            # Old format — migrate
                            self._models[name] = self._make_entry(
                                path_or_id=value,
                                provider="local",
                            )
                        elif isinstance(value, dict):
                            self._models[name] = value
                        else:
                            self._models[name] = {"path_or_id": str(value)}
        except (OSError, ValueError) as e:
            logger.warning(f"Failed to load models db: {e}")
            self._models = {}
            # Back up corrupted file before it gets silently overwritten on next save
            try:
                if self._path.exists():
                    import shutil
                    shutil.copy2(str(self._path), str(self._path) + ".bak")
                    logger.warning(f"Corrupted models database backed up to {self._path}.bak")
            except (OSError, ValueError) as backup_ex:
                logger.error(f"Failed to back up corrupted models database: {backup_ex}")

    def _save(self):
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=str(self._path.parent),
                prefix="models_db_", suffix=".tmp",
            )
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._models, f, indent=2)
            os.replace(tmp_path, str(self._path))
        except (OSError, ValueError, TypeError) as e:
            logger.warning(f"Failed to save models db: {e}")

    @staticmethod
    def _make_entry(
        path_or_id: str = "",
        provider: str = "local",
        context_size: int = 0,
        capabilities: dict[str, bool] | None = None,
    ) -> dict[str, Any]:
        """Create a new model entry dict with default values."""
        now = datetime.now(timezone.utc).isoformat()
        return {
            "path_or_id": path_or_id,
            "provider": provider,
            "context_size": context_size,
            "capabilities": capabilities or {
                "vision": False,
                "tool_calling": True,
                "streaming": True,
            },
            "last_used": now,
            "total_tokens": 0,
            "total_cost": 0.0,
            "sessions": 0,
            "added": now,
        }

    def add(self, name: str, path_or_id: str = "", provider: str = "local",
            context_size: int = 0, capabilities: dict[str, bool] | None = None):
        """Add or update a model entry with extended metadata."""
        existing = self._models.get(name)
        if existing:
            # Preserve existing stats, update identity fields
            existing["path_or_id"] = path_or_id or existing.get("path_or_id", "")
            existing["provider"] = provider or existing.get("provider", "local")
            if context_size is not None:
                existing["context_size"] = context_size
            if capabilities:
                existing["capabilities"] = capabilities
        else:
            self._models[name] = self._make_entry(
                path_or_id=path_or_id,
                provider=provider,
                context_size=context_size,
                capabilities=capabilities,
            )
        self._save()

    def remove(self, name: str) -> bool:
        """Remove a model entry. Returns True if existed."""
        if name in self._models:
            del self._models[name]
            self._save()
            return True
        return False

    def get(self, name: str) -> dict[str, Any] | None:
        """Get full model entry dict, or None."""
        return self._models.get(name)

    def get_path(self, name: str) -> str | None:
        """Get model path/id string (backward compatible)."""
        entry = self._models.get(name)
        if entry:
            if isinstance(entry, dict):
                return entry.get("path_or_id", "")
            return str(entry)  # Old format
        return None

    def list(self) -> dict[str, dict[str, Any]]:
        return dict(self._models)

    def names(self) -> list[str]:
        return list(self._models.keys())

    def find_by_path(self, path: str) -> str | None:
        for name, entry in self._models.items():
            entry_path = entry.get("path_or_id", "") if isinstance(entry, dict) else str(entry)
            if os.path.normpath(entry_path) == os.path.normpath(path):
                return name
        return None

    def auto_name(self, path: str) -> str:
        """Generate a readable name from a file path."""
        stem = Path(path).stem
        if len(stem) > 30:
            stem = stem[:30]
        # Deduplicate
        base = stem
        counter = 1
        while stem in self._models:
            stem = f"{base}_{counter}"
            counter += 1
        return stem

    # ── Usage Tracking ─────────────────────────────────────────────────

    def record_usage(self, name: str, tokens: int = 0, cost: float = 0.0):
        """Record token usage and cost for a model.

        Args:
            name: Model name.
            tokens: Number of tokens used in this interaction.
            cost: Estimated cost of this interaction.
        """
        entry = self._models.get(name)
        if not entry:
            return
        entry["total_tokens"] = entry.get("total_tokens", 0) + tokens
        entry["total_cost"] = entry.get("total_cost", 0.0) + cost
        entry["last_used"] = datetime.now(timezone.utc).isoformat()
        self._save()

    def record_session_start(self, name: str):
        """Increment session counter for a model."""
        entry = self._models.get(name)
        if entry:
            entry["sessions"] = entry.get("sessions", 0) + 1
            entry["last_used"] = datetime.now(timezone.utc).isoformat()
            self._save()

    def get_stats(self, name: str) -> dict[str, Any]:
        """Get usage statistics for a model.

        Returns:
            Dict with total_tokens, total_cost, sessions, last_used, etc.
        """
        entry = self._models.get(name, {})
        return {
            "name": name,
            "provider": entry.get("provider", "unknown"),
            "context_size": entry.get("context_size", 0),
            "total_tokens": entry.get("total_tokens", 0),
            "total_cost": entry.get("total_cost", 0.0),
            "sessions": entry.get("sessions", 0),
            "last_used": entry.get("last_used", "never"),
            "added": entry.get("added", ""),
            "capabilities": entry.get("capabilities", {}),
        }

    def get_all_stats(self) -> list[dict[str, Any]]:
        """Get usage statistics for all models."""
        return [self.get_stats(name) for name in self._models]

    def refresh_details(self, name: str, context_size: int = 0,
                       capabilities: dict[str, bool] | None = None):
        """Update model details (e.g. after re-fetching from API).

        Args:
            name: Model name.
            context_size: Updated context window size.
            capabilities: Updated capability flags.
        """
        entry = self._models.get(name)
        if not entry:
            return
        if context_size is not None:
            entry["context_size"] = context_size
        if capabilities:
            entry["capabilities"] = capabilities
        self._save()
