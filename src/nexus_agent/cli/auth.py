"""Persistent API key storage — stores credentials securely at ~/.nexus-agent/auth.json.

Follows opencode's pattern of persisting provider credentials locally
so they survive across CLI restarts without requiring environment variables.

NOTE: Base64 obfuscation is NOT cryptographic security. For production use,
consider using the OS keychain (e.g., keyring library) instead.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import stat
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet
    HAS_FERNET = True
except ImportError:
    HAS_FERNET = False
    logger.info("cryptography not installed; falling back to base64 obfuscation only. "
                "Install with: pip install cryptography")

AUTH_FILENAME = "auth.json"


class AuthStore:
    """Manages API key persistence for cloud providers.

    Keys are stored in ``~/.nexus-agent/auth.json`` with restricted
    file permissions (owner-only read/write on POSIX systems).

    Format::

        {
            "anthropic": {
                "api_key": "sk-ant-...",
                "added": "2026-05-27T12:00:00Z",
                "last_used": "2026-05-27T14:30:00Z"
            },
            ...
        }
    """

    # Maps provider name → environment variable to set
    PROVIDER_ENV_KEYS: dict[str, str] = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "groq": "GROQ_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "fireworks": "FIREWORKS_API_KEY",
        "together": "TOGETHER_API_KEY",
        "perplexity": "PPLX_API_KEY",
        "nvidia": "NVIDIA_API_KEY",
        "mistral": "MISTRAL_API_KEY",
    }

    def __init__(self, data_dir: str | None = None):
        if data_dir:
            self._path = Path(data_dir) / AUTH_FILENAME
        else:
            self._path = Path.home() / ".nexus-agent" / AUTH_FILENAME
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict[str, Any]] = {}
        self._fernet = self._init_fernet()
        self._load()

    @staticmethod
    def _init_fernet():
        """Initialize Fernet cipher from machine-specific key."""
        if not HAS_FERNET:
            return None
        try:
            machine_id = str(uuid.getnode())
            key = hashlib.sha256(machine_id.encode()).digest()
            return Fernet(base64.urlsafe_b64encode(key))
        except (ValueError, TypeError, OSError) as e:
            logger.warning(f"Failed to initialize Fernet: {e}")
            return None

    @staticmethod
    def _encrypt(plain: str, fernet) -> str:
        """Encrypt a string using Fernet, falling back to base64."""
        if fernet:
            try:
                token = fernet.encrypt(plain.encode())
                return base64.b64encode(token).decode()
            except (ValueError, TypeError):
                pass
        return base64.b64encode(plain.encode()).decode()

    @staticmethod
    def _decrypt(encoded: str, fernet) -> str:
        """Decrypt a string using Fernet, falling back to base64."""
        if fernet:
            try:
                token = base64.b64decode(encoded.encode())
                return fernet.decrypt(token).decode()
            except (ValueError, TypeError, OSError):
                pass
        return AuthStore._deobfuscate(encoded)

    def _load(self):
        """Load saved credentials from disk."""
        try:
            if self._path.exists():
                with open(str(self._path), encoding="utf-8") as f:
                    raw = json.load(f)
                self._data = self._deobfuscate_data(raw)
        except (OSError, ValueError) as e:
            logger.warning(f"Failed to load auth store: {e}")
            self._data = {}

    def _save(self):
        """Persist credentials to disk with restricted permissions."""
        try:
            encrypted = self._obfuscate_data(self._data)
            with open(str(self._path), "w", encoding="utf-8") as f:
                json.dump(encrypted, f, indent=2)
            # Restrict file permissions to owner-only on POSIX
            if os.name != "nt":
                try:
                    os.chmod(str(self._path), stat.S_IRUSR | stat.S_IWUSR)
                except OSError:
                    pass
            elif os.name == "nt":
                try:
                    subprocess.run(
                        ["icacls", str(self._path), "/inheritance:r", "/grant", f"{os.environ['USERNAME']}:(F)"],
                        capture_output=True, timeout=10,
                    )
                except (OSError, subprocess.TimeoutExpired, ValueError):
                    pass
        except (OSError, TypeError) as e:
            logger.warning(f"Failed to save auth store: {e}")

    @staticmethod
    def _obfuscate(plain: str) -> str:
        """Basic obfuscation for at-rest API keys (not cryptographic)."""
        return base64.b64encode(plain.encode()).decode()

    @staticmethod
    def _deobfuscate(encoded: str) -> str:
        """Reverse basic obfuscation."""
        try:
            return base64.b64decode(encoded.encode()).decode()
        except ValueError:
            return encoded

    def _obfuscate_data(self, data: dict) -> dict:
        result = {}
        for provider, entry in data.items():
            entry_copy = dict(entry)
            if "api_key" in entry_copy:
                entry_copy["api_key"] = self._encrypt(entry_copy["api_key"], self._fernet)
            result[provider] = entry_copy
        return result

    def _deobfuscate_data(self, data: dict) -> dict:
        result = {}
        for provider, entry in data.items():
            entry_copy = dict(entry)
            if "api_key" in entry_copy:
                entry_copy["api_key"] = self._decrypt(entry_copy["api_key"], self._fernet)
            result[provider] = entry_copy
        return result

    def save_key(self, provider: str, api_key: str) -> None:
        """Save an API key for a provider.

        Args:
            provider: Provider name (e.g. 'anthropic', 'openai').
            api_key: The API key string.
        """
        now = datetime.now(timezone.utc).isoformat()
        entry = self._data.get(provider, {})
        entry["api_key"] = api_key
        if "added" not in entry:
            entry["added"] = now
        entry["last_used"] = now
        self._data[provider] = entry
        self._save()

    def get_key(self, provider: str) -> str | None:
        """Retrieve a saved API key for a provider.

        Returns None if no key is stored.
        """
        entry = self._data.get(provider)
        if entry:
            return entry.get("api_key")
        return None

    def remove_key(self, provider: str) -> bool:
        """Remove a stored API key. Returns True if it existed."""
        if provider in self._data:
            del self._data[provider]
            self._save()
            return True
        return False

    def list_providers(self) -> dict[str, dict[str, Any]]:
        """Return all stored provider entries (without exposing full keys).

        Returns a dict of provider → {masked_key, added, last_used}.
        """
        result = {}
        for name, entry in self._data.items():
            key = entry.get("api_key", "")
            masked = key[:8] + "…" + key[-4:] if len(key) > 12 else "***"
            result[name] = {
                "masked_key": masked,
                "added": entry.get("added", ""),
                "last_used": entry.get("last_used", ""),
            }
        return result

    def has_key(self, provider: str) -> bool:
        """Check if a provider has a stored key."""
        entry = self._data.get(provider)
        return bool(entry and entry.get("api_key"))

    def load_into_env(self) -> int:
        """Load all stored API keys into environment variables.

        Called once at CLI startup. Does NOT overwrite keys already
        present in the environment (explicit env vars take priority).

        Returns:
            Number of keys loaded.
        """
        loaded = 0
        changed = False
        now = datetime.now(timezone.utc).isoformat()
        for provider, entry in self._data.items():
            api_key = entry.get("api_key")
            if not api_key:
                continue
            env_var = self.PROVIDER_ENV_KEYS.get(provider, f"{provider.upper()}_API_KEY")
            if env_var not in os.environ:
                os.environ[env_var] = api_key
                loaded += 1
            if entry.get("last_used") != now:
                entry["last_used"] = now
                changed = True
        if changed:
            self._save()
        return loaded

    def get_env_key(self, provider: str) -> str:
        """Get the environment variable name for a provider."""
        return self.PROVIDER_ENV_KEYS.get(provider, f"{provider.upper()}_API_KEY")

    def get_status(self) -> dict[str, str]:
        """Get connection status for all known providers.

        Returns a dict of provider → status string (✓ connected / ✗ not configured).
        """
        status = {}
        for provider in self.PROVIDER_ENV_KEYS:
            env_var = self.PROVIDER_ENV_KEYS[provider]
            if os.environ.get(env_var):
                status[provider] = "✓ connected (env)"
            elif self.has_key(provider):
                status[provider] = "✓ connected (saved)"
            else:
                status[provider] = "✗ not configured"
        return status
