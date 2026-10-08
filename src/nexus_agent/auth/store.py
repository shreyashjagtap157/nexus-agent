"""Secure local credential store with optional OS keychain integration."""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

try:
    import keyring
except ImportError:
    keyring = None

from nexus_agent.storage.layout import StorageLayout


class AuthStore:
    """Persist provider credentials separately from model configuration."""

    _KEYRING_SERVICE = "NexusAgent"

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
                handle.write("\n")
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
        provider_id = provider.strip().lower()
        if not provider_id or not key.strip():
            raise ValueError("Provider and credential key are required.")
        with self._lock:
            data = self._read()
            if keyring is not None:
                try:
                    keyring.set_password(self._KEYRING_SERVICE, provider_id, key)
                    data[provider_id] = {"type": "keyring", "metadata": metadata or {}}
                    self._write(data)
                    return
                except Exception:
                    pass
            data[provider_id] = {"type": "api_key", "key": key, "metadata": metadata or {}}
            self._write(data)

    def get(self, provider: str) -> str | None:
        provider_id = provider.strip().lower()
        with self._lock:
            item = self._read().get(provider_id)
        if isinstance(item, dict) and item.get("type") == "keyring":
            if keyring is None:
                return None
            try:
                return keyring.get_password(self._KEYRING_SERVICE, provider_id)
            except Exception:
                return None
        if isinstance(item, dict):
            value = item.get("key")
            return str(value) if value else None
        return None

    def metadata(self, provider: str) -> dict[str, Any]:
        provider_id = provider.strip().lower()
        with self._lock:
            item = self._read().get(provider_id, {})
        return dict(item.get("metadata", {})) if isinstance(item, dict) and isinstance(item.get("metadata"), dict) else {}

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            data = self._read()
        rows = []
        for provider, item in sorted(data.items()):
            item_type = item.get("type", "api_key") if isinstance(item, dict) else "api_key"
            rows.append({"provider": provider, "type": item_type, "key": "[keyring]" if item_type == "keyring" else "[stored]"})
        return rows

    def remove(self, provider: str) -> bool:
        provider_id = provider.strip().lower()
        with self._lock:
            data = self._read()
            item = data.get(provider_id)
            existed = provider_id in data
            if existed and isinstance(item, dict) and item.get("type") == "keyring" and keyring is not None:
                try:
                    keyring.delete_password(self._KEYRING_SERVICE, provider_id)
                except Exception:
                    pass
            data.pop(provider_id, None)
            if existed:
                self._write(data)
            return existed
