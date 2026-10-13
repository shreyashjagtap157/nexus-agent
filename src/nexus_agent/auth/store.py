"""Secure local credential store with optional OS keychain integration."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
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

    def __init__(self, path: Path | None = None, *, backend: str = "auto"):
        normalized_backend = str(backend).strip().lower()
        if normalized_backend not in {"auto", "file", "keyring"}:
            raise ValueError("Credential backend must be auto, file or keyring.")
        if normalized_backend == "keyring" and keyring is None:
            raise RuntimeError(
                "The OS keyring backend was requested but keyring support is unavailable."
            )

        self.path = path or StorageLayout(Path.cwd()).auth_file
        self._backend = normalized_backend
        self._use_keyring = normalized_backend == "keyring" or (
            normalized_backend == "auto" and keyring is not None and path is None
        )
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
            if self._use_keyring:
                try:
                    keyring.set_password(self._KEYRING_SERVICE, provider_id, key)
                    data[provider_id] = {"type": "keyring", "metadata": metadata or {}}
                    self._write(data)
                    return
                except Exception as exc:
                    if self._backend == "keyring":
                        raise RuntimeError(
                            "The OS keyring could not store the credential."
                        ) from exc
            data[provider_id] = {"type": "api_key", "key": key, "metadata": metadata or {}}
            self._write(data)

    def get(self, provider: str) -> str | None:
        provider_id = provider.strip().lower()
        with self._lock:
            item = self._read().get(provider_id)
        if isinstance(item, dict) and item.get("type") == "keyring":
            if not self._use_keyring or keyring is None:
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
        return (
            dict(item.get("metadata", {}))
            if isinstance(item, dict) and isinstance(item.get("metadata"), dict)
            else {}
        )

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            data = self._read()
        rows = []
        for provider, item in sorted(data.items()):
            item_type = item.get("type", "api_key") if isinstance(item, dict) else "api_key"
            rows.append(
                {
                    "provider": provider,
                    "type": item_type,
                    "key": "[keyring]" if item_type == "keyring" else "[stored]",
                }
            )
        return rows

    def remove(self, provider: str) -> bool:
        provider_id = provider.strip().lower()
        with self._lock:
            data = self._read()
            item = data.get(provider_id)
            existed = provider_id in data
            if (
                existed
                and isinstance(item, dict)
                and item.get("type") == "keyring"
                and keyring is not None
            ):
                try:
                    keyring.delete_password(self._KEYRING_SERVICE, provider_id)
                except Exception:
                    pass
            data.pop(provider_id, None)
            if existed:
                self._write(data)
            return existed

    def add_user(self, user_id: str, tenant_id: str, profile: dict[str, Any]) -> None:
        """Create a new user within a tenant."""
        tenant_id = tenant_id.strip().lower()
        user_id = user_id.strip().lower()
        if not tenant_id or not user_id:
            raise ValueError("Tenant ID and user ID are required.")

        with self._lock:
            data = self._read()

            # Initialize tenant structure
            tenants = data.get("__tenants__", {})
            if tenant_id not in tenants:
                tenants[tenant_id] = {"created_at": time.time()}
            tenant_data = tenants[tenant_id]

            # Check if user exists
            users = tenant_data.get("users", {})
            if user_id in users:
                raise ValueError(f"User '{user_id}' already exists in tenant '{tenant_id}'.")

            # Add user profile with tenant-scoped permissions
            users[user_id] = {
                **profile,
                "tenant_id": tenant_id,
                "created_at": time.time(),
                "profile_version": 1,
                "permissions": profile.get("permissions", {}),
                "roles": profile.get("roles", []),
                "settings": profile.get("settings", {}),
            }

            tenants[tenant_id]["users"] = users
            data["__tenants__"] = tenants
            self._write(data)

    def get_user(self, user_id: str, tenant_id: str) -> dict[str, Any] | None:
        """Retrieve user profile with tenant context."""
        tenant_id = tenant_id.strip().lower()
        user_id = user_id.strip().lower()

        with self._lock:
            data = self._read()
            tenants = data.get("__tenants__", {})
            tenant_data = tenants.get(tenant_id)
            if not tenant_data:
                return None

            users = tenant_data.get("users", {})
            return dict(users.get(user_id)) if user_id in users else None

    def update_user(self, user_id: str, tenant_id: str, updates: dict[str, Any]) -> bool:
        """Update user profile within tenant."""
        tenant_id = tenant_id.strip().lower()
        user_id = user_id.strip().lower()

        with self._lock:
            data = self._read()
            tenants = data.get("__tenants__", {})
            tenant_data = tenants.get(tenant_id)
            if not tenant_data:
                return False

            users = tenant_data.get("users", {})
            if user_id not in users:
                return False

            # Merge updates (preserve sensitive fields)
            user_profile = dict(users[user_id])
            safe_updates = {
                key: value for key, value in updates.items()
                if key not in {"tenant_id", "user_id", "created_at", "profile_version"}
            }

            # Update profile version for schema evolution
            user_profile.update(safe_updates)
            user_profile["profile_version"] = user_profile.get("profile_version", 1) + 1
            user_profile["updated_at"] = time.time()

            users[user_id] = user_profile
            tenant_data["users"] = users
            data["__tenants__"] = tenants
            self._write(data)
            return True

    def delete_user(self, user_id: str, tenant_id: str) -> bool:
        """Delete user and all associated data within tenant."""
        tenant_id = tenant_id.strip().lower()
        user_id = user_id.strip().lower()

        with self._lock:
            data = self._read()
            tenants = data.get("__tenants__", {})
            tenant_data = tenants.get(tenant_id)
            if not tenant_data:
                return False

            users = tenant_data.get("users", {})
            if user_id not in users:
                return False

            del users[user_id]
            tenant_data["users"] = users

            # Optional: Also delete tenant if empty
            # if not users:
            #     del tenants[tenant_id]

            data["__tenants__"] = tenants
            self._write(data)
            return True

    def list_users(self, tenant_id: str) -> list[dict[str, Any]]:
        """List all users within a tenant."""
        tenant_id = tenant_id.strip().lower()

        with self._lock:
            data = self._read()
            tenants = data.get("__tenants__", {})
            tenant_data = tenants.get(tenant_id)
            if not tenant_data:
                return []

            users = tenant_data.get("users", {})
            return [
                {
                    "user_id": user_id,
                    "profile": dict(profile),
                }
                for user_id, profile in sorted(users.items())
            ]

    def add_role(self, user_id: str, tenant_id: str, role: dict[str, Any]) -> bool:
        """Assign a role to a user within tenant."""
        tenant_id = tenant_id.strip().lower()
        user_id = user_id.strip().lower()

        with self._lock:
            data = self._read()
            tenants = data.get("__tenants__", {})
            tenant_data = tenants.get(tenant_id)
            if not tenant_data:
                return False

            users = tenant_data.get("users", {})
            if user_id not in users:
                return False

            user_profile = dict(users[user_id])
            roles = user_profile.get("roles", [])

            # Check if role already exists
            existing_role = next(
                (r for r in roles if r.get("name") == role.get("name")),
                None,
            )
            if existing_role:
                # Update existing role
                idx = roles.index(existing_role)
                roles[idx] = {**existing_role, **role, "updated_at": time.time()}
            else:
                # Add new role
                roles.append({
                    **role,
                    "assigned_at": time.time(),
                    "role_version": 1,
                })

            user_profile["roles"] = roles
            user_profile["updated_at"] = time.time()
            users[user_id] = user_profile
            tenant_data["users"] = users
            data["__tenants__"] = tenants
            self._write(data)
            return True

    def remove_role(self, user_id: str, tenant_id: str, role_name: str) -> bool:
        """Remove a role from user within tenant."""
        tenant_id = tenant_id.strip().lower()
        user_id = user_id.strip().lower()

        with self._lock:
            data = self._read()
            tenants = data.get("__tenants__", {})
            tenant_data = tenants.get(tenant_id)
            if not tenant_data:
                return False

            users = tenant_data.get("users", {})
            if user_id not in users:
                return False

            user_profile = dict(users[user_id])
            roles = user_profile.get("roles", [])

            # Remove role by name
            original_len = len(roles)
            roles = [r for r in roles if r.get("name") != role_name]

            if len(roles) == original_len:
                return False

            user_profile["roles"] = roles
            user_profile["updated_at"] = time.time()
            users[user_id] = user_profile
            tenant_data["users"] = users
            data["__tenants__"] = tenants
            self._write(data)
            return True

    def set_user_permission(
        self,
        user_id: str,
        tenant_id: str,
        resource: str,
        permission: str,
        value: bool = True,
    ) -> bool:
        """Grant or revoke a permission for user within tenant."""
        tenant_id = tenant_id.strip().lower()
        user_id = user_id.strip().lower()

        with self._lock:
            data = self._read()
            tenants = data.get("__tenants__", {})
            tenant_data = tenants.get(tenant_id)
            if not tenant_data:
                return False

            users = tenant_data.get("users", {})
            if user_id not in users:
                return False

            user_profile = dict(users[user_id])
            permissions = user_profile.get("permissions", {})

            # Update permission
            if not permissions:
                permissions = {}

            if not permissions.get(resource):
                permissions[resource] = {}

            permissions[resource][permission] = value

            # Clean up empty permissions
            if not any(permissions.get(r) for r in permissions):
                permissions = {}

            user_profile["permissions"] = permissions
            user_profile["updated_at"] = time.time()
            users[user_id] = user_profile
            tenant_data["users"] = users
            data["__tenants__"] = tenants
            self._write(data)
            return True

    def get_user_permission(
        self,
        user_id: str,
        tenant_id: str,
        resource: str,
        permission: str,
    ) -> bool:
        """Check if user has specific permission within tenant."""
        tenant_id = tenant_id.strip().lower()
        user_id = user_id.strip().lower()

        with self._lock:
            data = self._read()
            tenants = data.get("__tenants__", {})
            tenant_data = tenants.get(tenant_id)
            if not tenant_data:
                return False

            users = tenant_data.get("users", {})
            if user_id not in users:
                return False

            user_profile = dict(users[user_id])
            permissions = user_profile.get("permissions", {})

            return bool(permissions.get(resource, {}).get(permission, False))

    def get_tenant_users_by_role(
        self, tenant_id: str, role_name: str
    ) -> list[dict[str, Any]]:
        """Get all users in tenant with specific role."""
        tenant_id = tenant_id.strip().lower()

        with self._lock:
            data = self._read()
            tenants = data.get("__tenants__", {})
            tenant_data = tenants.get(tenant_id)
            if not tenant_data:
                return []

            users = tenant_data.get("users", {})
            result = []

            for user_id, profile in users.items():
                roles = profile.get("roles", [])
                user_roles = [r.get("name") for r in roles if isinstance(r, dict)]

                if role_name in user_roles:
                    result.append({
                        "user_id": user_id,
                        "profile": dict(profile),
                        "roles": user_roles,
                    })

            return result

    def get_tenant_stats(self, tenant_id: str) -> dict[str, Any]:
        """Get statistics for a tenant."""
        tenant_id = tenant_id.strip().lower()

        with self._lock:
            data = self._read()
            tenants = data.get("__tenants__", {})
            tenant_data = tenants.get(tenant_id)
            if not tenant_data:
                return {"error": "Tenant not found"}

            users = tenant_data.get("users", {})

            return {
                "tenant_id": tenant_id,
                "user_count": len(users),
                "created_at": tenant_data.get("created_at"),
                "last_updated": tenant_data.get("last_updated"),
            }
