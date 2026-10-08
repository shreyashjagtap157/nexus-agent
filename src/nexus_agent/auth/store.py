"""Secure local credential store inspired by modern agent CLIs."""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from nexus_agent.storage.layout import StorageLayout


class AuthStore:
    """Persist provider credentials separately from model configuration."""

    def __init__(self, path: Path | None = None):
        self.path = path or StorageLayout(Path.cwd()).auth_file
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".auth-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.write("
")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        finally:
            if os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

    def set(self, provider: str, key: str, *, metadata: dict[str, Any] | None = None) -> None:
        if not provider.strip() or not key.strip():
            raise ValueError("Provider and credential key are required.")
        with self._lock:
            data = self._read()
            data[provider.strip().lower()] = {
                "type": "api_key",
                "key": key,
                "metadata": metadata or {},
            }
            self._write(data)

    def get(self, provider: str) -> str | None:
        with self._lock:
            item = self._read().get(provider.strip().lower())
        if isinstance(item, dict):
            value = item.get("key")
            return str(value) if value else None
        return None

    def metadata(self, provider: str) -> dict[str, Any]:
        with self._lock:
            item = self._read().get(provider.strip().lower(), {})
        return item.get("metadata", {}) if isinstance(item, dict) and isinstance(item.get("metadata"), dict) else {}

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            data = self._read()
        rows = []
        for provider, item in sorted(data.items()):
            key = str(item.get("key", "")) if isinstance(item, dict) else ""
            masked = (key[:4] + "…" + key[-4:]) if len(key) > 10 else ("*" * len(key))
            rows.append({"provider": provider, "type": item.get("type", "api_key") if isinstance(item, dict) else "api_key", "key": masked})
        return rows

    def remove(self, provider: str) -> bool:
        with self._lock:
            data = self._read()
            existed = provider.strip().lower() in data
            data.pop(provider.strip().lower(), None)
            if existed:
                self._write(data)
            return existed
