"""Persistent API key storage — multi-tier security backend.

Supports three storage tiers in order of preference:

1. OS Keychain (macOS Keychain, Windows Credential Manager, Linux Secret Service)
   via the `keyring` library. This is the default when keyring is installed.

2. Fernet symmetric encryption (via `cryptography` library), keyed to the
   machine's UUID. Keys are stored in ``~/.nexus-agent/auth.json``.

3. Base64 obfuscation (fallback). Not cryptographic security, but prevents
   casual plaintext leakage in config files or backups.

Tier selection is automatic — the highest available tier is used by default.
Users can force a specific tier via ``force_backend``.
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

# ── Optional dependency detection ─────────────────────────────────────

try:
    import keyring as _keyring
    from keyring.errors import KeyringError as _KeyringError

    HAS_KEYRING = True
except ImportError:
    _keyring = None  # type: ignore[assignment]
    _KeyringError = RuntimeError
    HAS_KEYRING = False

try:
    from cryptography.fernet import Fernet as _Fernet

    HAS_FERNET = True
except ImportError:
    _Fernet = None  # type: ignore[assignment]
    HAS_FERNET = False

# Maps provider name to environment variable name (module-level for shared access)
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

AUTH_FILENAME = "auth.json"
KEYRING_SERVICE = "nexus-agent"


# ═══════════════════════════════════════════════════════════════════════
# Backend: OS Keychain
# ═══════════════════════════════════════════════════════════════════════

class KeychainBackend:
    """Credentials stored in the OS keychain via the ``keyring`` library.

    Uses the system-native secret store (macOS Keychain, Windows Credential
    Manager, Linux Secret Service / libsecret). Service name is ``nexus-agent``,
    username is the provider name.

    Tier: **highest** — encrypted at rest by the OS, survives disk access.
    """

    SERVICE_NAME = KEYRING_SERVICE

    @staticmethod
    def is_available() -> bool:
        """Return True if the keyring library is installed and a usable backend exists."""
        if not HAS_KEYRING:
            return False
        try:
            # Quick probe — try to access the keyring without creating a credential
            _keyring.get_keyring()
            return True
        except Exception as e:
            logger.debug("Keychain probe failed: %s", e)
            return False

    @staticmethod
    def save_key(provider: str, api_key: str) -> None:
        """Store an API key in the OS keychain.

        Args:
            provider: Provider name (e.g. 'anthropic', 'openai').
            api_key: The API key string.

        Raises:
            KeyringError: If the keyring backend fails.
        """
        _keyring.set_password(KEYRING_SERVICE, provider, api_key)

    @staticmethod
    def get_key(provider: str) -> str | None:
        """Retrieve an API key from the OS keychain.

        Args:
            provider: Provider name.

        Returns:
            The API key string, or None if no key is stored.
        """
        try:
            return _keyring.get_password(KEYRING_SERVICE, provider)
        except _KeyringError as e:
            logger.warning("Keychain read failed for '%s': %s", provider, e)
            return None

    @staticmethod
    def remove_key(provider: str) -> bool:
        """Remove an API key from the OS keychain.

        Args:
            provider: Provider name.

        Returns:
            True if the key was removed, False if it didn't exist.
        """
        try:
            _keyring.delete_password(KEYRING_SERVICE, provider)
            return True
        except _KeyringError:
            return False

    @staticmethod
    def list_providers() -> dict[str, dict[str, Any]]:
        """List all providers with keys in the OS keychain.

        Note: the keyring API does not support listing all stored credentials
        generically. This method returns an empty dict — callers should use
        the JSON file metadata for provider listing and fall back to keychain
        for individual key retrieval.

        Returns:
            Always returns an empty dict (providers must be tracked externally).
        """
        return {}


# ═══════════════════════════════════════════════════════════════════════
# Backend: JSON file with Fernet encryption
# ═══════════════════════════════════════════════════════════════════════

class FernetFileBackend:
    """Credentials stored in ``~/.nexus-agent/auth.json`` with Fernet encryption.

    The encryption key is derived from the machine's MAC address (``uuid.getnode()``),
    so the file is tied to the specific machine and cannot be decrypted elsewhere.

    Tier: **medium** — encrypted at rest, but the key is stored on the same machine.
    """

    def __init__(self, data_dir: str | None = None):
        if data_dir:
            self._path = Path(data_dir) / AUTH_FILENAME
        else:
            self._path = Path.home() / ".nexus-agent" / AUTH_FILENAME
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fernet: Any = self._init_fernet()
        self._data: dict[str, dict[str, Any]] = {}
        self._load()

    # ── Fernet key management ──────────────────────────────────────

    @staticmethod
    def _init_fernet():
        """Initialize Fernet cipher from machine-specific key."""
        if not HAS_FERNET:
            return None
        try:
            machine_id = str(uuid.getnode())
            key = hashlib.sha256(machine_id.encode()).digest()
            return _Fernet(base64.urlsafe_b64encode(key))
        except (ValueError, TypeError, OSError) as e:
            logger.warning("Failed to initialize Fernet: %s", e)
            return None

    @staticmethod
    def _encrypt(plain: str, fernet: Any) -> str:
        """Encrypt a string using Fernet, falling back to base64."""
        if fernet:
            try:
                token = fernet.encrypt(plain.encode())
                return base64.b64encode(token).decode()
            except (ValueError, TypeError):
                pass
        return base64.b64encode(plain.encode()).decode()

    @staticmethod
    def _decrypt(encoded: str, fernet: Any) -> str:
        """Decrypt a string using Fernet, falling back to base64."""
        if fernet:
            try:
                token = base64.b64decode(encoded.encode())
                return fernet.decrypt(token).decode()
            except (ValueError, TypeError, OSError):
                pass
        return FernetFileBackend._deobfuscate(encoded)

    # ── I/O ────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load saved credentials from disk."""
        try:
            if self._path.exists():
                with open(str(self._path), encoding="utf-8") as f:
                    raw = json.load(f)
                self._data = self._deobfuscate_data(raw)
        except (OSError, ValueError) as e:
            logger.warning("Failed to load auth store: %s", e)
            self._data = {}

    def _save(self) -> None:
        """Persist credentials to disk with restricted permissions."""
        try:
            encrypted = self._obfuscate_data(self._data)
            with open(str(self._path), "w", encoding="utf-8") as f:
                json.dump(encrypted, f, indent=2)
            self._restrict_file_permissions()
        except (OSError, TypeError) as e:
            logger.warning("Failed to save auth store: %s", e)

    def _restrict_file_permissions(self) -> None:
        """Restrict file to owner-only read/write on all platforms."""
        if os.name != "nt":
            try:
                os.chmod(str(self._path), stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                pass
        else:
            try:
                subprocess.run(
                    ["icacls", str(self._path), "/inheritance:r", "/grant", f"{os.environ['USERNAME']}:(F)"],
                    capture_output=True, timeout=10,
                )
            except (OSError, subprocess.TimeoutExpired, ValueError, KeyError):
                pass

    # ── Transforms ─────────────────────────────────────────────────

    @staticmethod
    def _obfuscate(plain: str) -> str:
        return base64.b64encode(plain.encode()).decode()

    @staticmethod
    def _deobfuscate(encoded: str) -> str:
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

    # ── Public API ─────────────────────────────────────────────────

    def save_key(self, provider: str, api_key: str) -> None:
        """Save an API key to the encrypted JSON file."""
        now = datetime.now(timezone.utc).isoformat()
        entry = self._data.get(provider, {})
        entry["api_key"] = api_key
        if "added" not in entry:
            entry["added"] = now
        entry["last_used"] = now
        self._data[provider] = entry
        self._save()

    def get_key(self, provider: str) -> str | None:
        """Retrieve an API key from the encrypted JSON file."""
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

    def has_key(self, provider: str) -> bool:
        entry = self._data.get(provider)
        return bool(entry and entry.get("api_key"))

    def list_providers(self) -> dict[str, dict[str, Any]]:
        """Return all stored provider entries (without exposing full keys)."""
        result = {}
        for name, entry in self._data.items():
            key = entry.get("api_key", "")
            masked = key[:8] + "\u2026" + key[-4:] if len(key) > 12 else "***"
            result[name] = {
                "masked_key": masked,
                "added": entry.get("added", ""),
                "last_used": entry.get("last_used", ""),
            }
        return result

    def get_status(self) -> dict[str, str]:
        """Get connection status for all known providers."""
        status = {}
        for provider, env_var in PROVIDER_ENV_KEYS.items():
            if os.environ.get(env_var):
                status[provider] = "\u2713 connected (env)"
            elif self.has_key(provider):
                status[provider] = "\u2713 connected (saved)"
            else:
                status[provider] = "\u2717 not configured"
        return status

    def update_last_used(self, provider: str) -> bool:
        """Update the last_used timestamp for a provider.

        Returns True if the store was modified.
        """
        now = datetime.now(timezone.utc).isoformat()
        entry = self._data.get(provider)
        if entry and entry.get("last_used") != now:
            entry["last_used"] = now
            self._save()
            return True
        return False


# ═══════════════════════════════════════════════════════════════════════
# Unified AuthStore
# ═══════════════════════════════════════════════════════════════════════

class AuthStore:
    """Manages API key persistence for cloud providers.

    Uses a multi-tier security model:
    1. OS keychain (``keyring`` library) — highest security
    2. Fernet-encrypted JSON file — medium security
    3. Base64 obfuscation — minimum security (fallback)

    The best available backend is selected automatically, but callers can
    force a specific backend via ``force_backend``.

    Provider metadata (last_used timestamps, listing) is maintained in the
    JSON file regardless of the key storage backend.
    """

    BACKEND_KEYCHAIN = "keychain"
    BACKEND_FILE = "file"

    def __init__(
        self,
        data_dir: str | None = None,
        force_backend: str | None = None,
    ):
        """Initialize the auth store.

        Args:
            data_dir: Optional custom data directory. Defaults to ``~/.nexus-agent/``.
            force_backend: Force a specific backend (``"keychain"``, ``"file"``).
                If None, the best available backend is selected automatically.
        """
        # Metadata store (always uses the file backend for last_used, added, etc.)
        self._metadata = FernetFileBackend(data_dir=data_dir)

        # Key storage backend selection
        self._key_backend: KeychainBackend | FernetFileBackend
        if force_backend == self.BACKEND_KEYCHAIN:
            if not KeychainBackend.is_available():
                logger.warning(
                    "OS keychain forced but unavailable. "
                    "Install keyring: pip install keyring"
                )
            self._key_backend = KeychainBackend() if KeychainBackend.is_available() else self._metadata
        elif force_backend == self.BACKEND_FILE:
            self._key_backend = self._metadata
        elif KeychainBackend.is_available():
            self._key_backend = KeychainBackend()
            logger.debug("Using OS keychain for credential storage")
        else:
            self._key_backend = self._metadata
            tier = "Fernet" if HAS_FERNET else "base64"
            logger.debug("OS keychain unavailable; using %s file backend", tier)

    # ── Public API ─────────────────────────────────────────────────

    def save_key(self, provider: str, api_key: str) -> None:
        """Save an API key for a provider.

        Args:
            provider: Provider name (e.g. 'anthropic', 'openai').
            api_key: The API key string.
        """
        # Store key in the primary backend first, then always update metadata
        if isinstance(self._key_backend, KeychainBackend):
            try:
                KeychainBackend.save_key(provider, api_key)
            except _KeyringError as e:
                logger.error(
                    "Keychain write failed for '%s': %s — falling back to file",
                    provider, e,
                )
                self._metadata.save_key(provider, api_key)
                return

        # Always update metadata (timestamps, provider listing) — single write path
        self._metadata.save_key(provider, api_key)

    def get_key(self, provider: str) -> str | None:
        """Retrieve a saved API key for a provider.

        Checks key backend first, then file backend, then environment variables.
        Returns None if no key is found anywhere.
        """
        # 1. Try the primary key backend
        if isinstance(self._key_backend, KeychainBackend):
            try:
                key = KeychainBackend.get_key(provider)
                if key is not None:
                    self._metadata.update_last_used(provider)
                    return key
            except _KeyringError as e:
                logger.warning("Keychain read failed for '%s': %s", provider, e)

        # 2. Fall back to file backend
        key = self._metadata.get_key(provider)
        if key is not None:
            return key

        # 3. Fall back to environment variable
        env_var = PROVIDER_ENV_KEYS.get(provider, f"{provider.upper()}_API_KEY")
        return os.environ.get(env_var)

    def remove_key(self, provider: str) -> bool:
        """Remove a stored API key. Returns True if it existed."""
        removed = False
        if isinstance(self._key_backend, KeychainBackend):
            removed = KeychainBackend.remove_key(provider) or removed
        removed = self._metadata.remove_key(provider) or removed
        return removed

    def has_key(self, provider: str) -> bool:
        """Check if a provider has a stored key."""
        if isinstance(self._key_backend, KeychainBackend):
            try:
                if KeychainBackend.get_key(provider) is not None:
                    return True
            except _KeyringError:
                pass
        return self._metadata.has_key(provider)

    def list_providers(self) -> dict[str, dict[str, Any]]:
        """Return all stored provider entries (without exposing full keys).

        Returns a dict of provider → {masked_key, added, last_used}.
        """
        return self._metadata.list_providers()

    def load_into_env(self) -> int:
        """Load all stored API keys into environment variables.

        Called once at CLI startup. Does NOT overwrite keys already
        present in the environment (explicit env vars take priority).

        Returns:
            Number of keys loaded.
        """
        loaded = 0
        for provider, env_var in PROVIDER_ENV_KEYS.items():
            if env_var in os.environ:
                continue
            key = self.get_key(provider)
            if key:
                os.environ[env_var] = key
                loaded += 1
        return loaded

    def get_env_key(self, provider: str) -> str:
        """Get the environment variable name for a provider."""
        return PROVIDER_ENV_KEYS.get(provider, f"{provider.upper()}_API_KEY")

    def get_status(self) -> dict[str, str]:
        """Get connection status for all known providers.

        Returns a dict of provider → status string.
        """
        return self._metadata.get_status()

    def backend_name(self) -> str:
        """Return the active key storage backend name for display."""
        if isinstance(self._key_backend, KeychainBackend):
            try:
                return f"keychain ({_keyring.get_keyring().__class__.__name__})"
            except Exception:
                return "keychain"
        if HAS_FERNET:
            return "fernet (encrypted file)"
        return "base64 (obfuscated file)"
