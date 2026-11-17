"""Web endpoints for provider catalog, credential lifecycle and tenant management.

The provider/credential endpoints manage the local user auth store. The tenant
endpoints expose the multi-user identity foundation from ``AuthStore`` so that
the implemented user/role/permission operations are reachable over the API.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

from nexus_agent.auth.store import AuthStore
from nexus_agent.core.config import _strip_secrets, load_config, save_user_config
from nexus_agent.llm.base import Message, Role
from nexus_agent.llm.providers.catalog import all_providers
from nexus_agent.llm.providers.models_dev import ModelsDevCatalog
from nexus_agent.storage.layout import StorageLayout


class UserRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    profile: dict[str, Any] = Field(default_factory=dict)


class RoleRequest(BaseModel):
    role: dict[str, Any]


class PermissionRequest(BaseModel):
    resource: str = Field(min_length=1, max_length=200)
    permission: str = Field(min_length=1, max_length=100)
    value: bool = Field(default=True)


class UpdateUserRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    tenant_id: str = Field(min_length=1, max_length=100)
    updates: dict[str, Any] = Field(default_factory=dict)


class CredentialRequest(BaseModel):
    api_key: str = Field(min_length=1, max_length=10000)


class ProviderTestRequest(BaseModel):
    model: str | None = Field(default=None, max_length=500)
    prompt: str = Field(
        default="Respond with exactly: NexusAgent provider test OK", max_length=4000
    )
    max_tokens: int = Field(default=64, ge=1, le=512)


def _local_only(request: Any) -> None:
    client = getattr(request, "client", None)
    if client is None or client.host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(
            status_code=403, detail="Provider configuration is restricted to local clients."
        )


class ProviderConfigRequest(BaseModel):
    model: str | None = Field(default=None, max_length=1000)
    base_url: str | None = Field(default=None, max_length=4000)
    api_url: str | None = Field(default=None, max_length=4000)
    context_size: int | None = Field(default=None, ge=256, le=2_000_000)
    max_tokens: int | None = Field(default=None, ge=1, le=1_000_000)
    reasoning_budget: int | None = Field(default=None, ge=1, le=2_000_000)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    timeout_seconds: float | None = Field(default=None, ge=1.0, le=3600.0)
    pending_poll_seconds: float | None = Field(default=None, ge=0.1, le=60.0)
    pending_max_wait_seconds: float | None = Field(default=None, ge=1.0, le=86400.0)


def register_auth_routes(app: Any, state_manager: Any | None = None) -> None:

    @app.post("/api/providers/{provider}/test")
    async def test_provider(provider: str, request: Request, payload: ProviderTestRequest):
        _local_only(request)
        from nexus_agent.llm.providers.factory import ProviderFactory

        workspace = Path(
            state_manager.get("workspace") if state_manager is not None else Path.cwd()
        ).resolve()
        config = (
            state_manager.get("config")
            if state_manager is not None
            else load_config(workspace=workspace)
        )
        try:
            started = time.perf_counter()
            engine = ProviderFactory.create_provider(provider, config, payload.model)
            response = engine.chat_completion(
                [
                    Message(
                        role=Role.SYSTEM,
                        content="You are performing a connectivity test. Do not reveal secrets.",
                    ),
                    Message(role=Role.USER, content=payload.prompt),
                ],
                temperature=0.0,
                max_tokens=payload.max_tokens,
            )
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            return {
                "ok": True,
                "provider": engine.name,
                "model": engine.model_name,
                "latency_ms": elapsed_ms,
                "response": (response.content or "")[:4000],
            }
        except (RuntimeError, ValueError, OSError, TimeoutError, ConnectionError) as exc:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            return {
                "ok": False,
                "provider": provider,
                "latency_ms": elapsed_ms,
                "error": str(exc)[:4000],
            }

    @app.get("/api/providers")
    async def providers():
        return {
            "providers": [
                {
                    "id": item.id,
                    "name": item.name,
                    "protocol": item.protocol,
                    "base_url": item.base_url,
                    "env_key": item.env_key,
                    "supports_custom_models": item.supports_custom_models,
                }
                for item in all_providers()
            ]
        }

    @app.post("/api/providers/{provider}/activate")
    async def activate_provider(
        provider: str, request: Request, payload: ProviderTestRequest | None = None
    ):
        _local_only(request)
        from nexus_agent.core.config import load_config, save_user_config
        from nexus_agent.llm.providers.factory import ProviderFactory

        workspace = Path(
            state_manager.get("workspace") if state_manager is not None else Path.cwd()
        ).resolve()
        config = (
            state_manager.get("config")
            if state_manager is not None
            else load_config(workspace=workspace)
        )
        provider_name = provider.strip().lower()
        requested_model = payload.model if payload is not None else None
        try:
            new_engine = ProviderFactory.create_provider(provider_name, config, requested_model)
        except (ImportError, RuntimeError, ValueError, OSError) as exc:
            raise HTTPException(
                status_code=400, detail=f"Unable to activate provider {provider_name}: {exc}"
            ) from exc

        if state_manager is not None:
            old_engine = state_manager.get("engine")
            state_manager.set("engine", new_engine)
            active_config = state_manager.get("config") or {}
            active_config.setdefault("providers", {})["active"] = provider_name
            state_manager.set("config", active_config)
            save_user_config({"providers": {"active": provider_name}})
            if old_engine is not None and old_engine is not new_engine:
                try:
                    old_engine.close()
                except (OSError, RuntimeError):
                    pass
        else:
            save_user_config({"providers": {"active": provider_name}})

        return {"provider": provider_name, "model": new_engine.model_name, "active": True}

    @app.get("/api/provider-config")
    async def provider_config(request: Request):
        _local_only(request)
        workspace = Path(
            state_manager.get("workspace") if state_manager is not None else Path.cwd()
        ).resolve()
        config = (
            state_manager.get("config")
            if state_manager is not None
            else load_config(workspace=workspace)
        )
        providers = config.get("providers", {})
        output = {}
        if isinstance(providers, dict):
            for provider_id, value in providers.items():
                if not isinstance(value, dict):
                    continue
                output[provider_id] = {
                    key: value[key]
                    for key in (
                        "model",
                        "base_url",
                        "api_url",
                        "context_size",
                        "max_tokens",
                        "reasoning_budget",
                        "top_p",
                        "timeout_seconds",
                        "pending_poll_seconds",
                        "pending_max_wait_seconds",
                    )
                    if key in value
                }
        return {
            "active": providers.get("active", "local"),
            "providers": output,
        }

    @app.put("/api/provider-config/{provider}")
    async def update_provider_config(
        provider: str, request: Request, payload: ProviderConfigRequest
    ):
        _local_only(request)
        values = payload.model_dump(exclude_none=True)
        provider_id = provider.lower()
        save_user_config({"providers": {provider_id: _strip_secrets(values)}})
        if state_manager is not None:
            config = state_manager.get("config") or {}
            config.setdefault("providers", {}).setdefault(provider_id, {}).update(values)
            state_manager.set("config", config)
        return {"provider": provider_id, "config": _strip_secrets(values)}

    @app.get("/api/providers/models")
    async def provider_models(request: Request, provider: str, refresh: bool = False):
        _local_only(request)
        workspace = Path(
            state_manager.get("workspace") if state_manager is not None else Path.cwd()
        ).resolve()
        catalog = ModelsDevCatalog(StorageLayout(workspace).caches / "models-dev.json")
        return {
            "provider": provider,
            "models": catalog.models(provider, refresh=refresh),
        }

    @app.get("/api/auth")
    async def auth_list(request: Request):
        _local_only(request)
        return {"credentials": AuthStore().list()}

    @app.put("/api/auth/{provider}")
    async def auth_set(provider: str, request: Request, payload: CredentialRequest):
        _local_only(request)
        AuthStore().set(provider, payload.api_key)
        return {"provider": provider.lower(), "stored": True}

    @app.delete("/api/auth/{provider}")
    async def auth_delete(provider: str, request: Request):
        _local_only(request)
        return {
            "provider": provider.lower(),
            "removed": AuthStore().remove(provider),
        }

    # ── Multi-user tenant / identity management ────────────────────────────
    # These routes wire up the tenant-scoped AuthStore operations (users,
    # roles, permissions) that were previously implemented but unreachable.

    @app.get("/api/tenants/{tenant_id}")
    async def tenant_stats(tenant_id: str, request: Request):
        _local_only(request)
        return AuthStore().get_tenant_stats(tenant_id)

    @app.get("/api/tenants/{tenant_id}/users")
    async def tenant_users(tenant_id: str, request: Request):
        _local_only(request)
        return {"users": AuthStore().list_users(tenant_id)}

    @app.post("/api/tenants/{tenant_id}/users")
    async def tenant_add_user(tenant_id: str, request: Request, payload: UserRequest):
        _local_only(request)
        store = AuthStore()
        try:
            store.add_user(payload.user_id, tenant_id, payload.profile)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        user = store.get_user(payload.user_id, tenant_id)
        return {"user_id": payload.user_id, "tenant_id": tenant_id, "user": user}

    @app.get("/api/tenants/{tenant_id}/users/{user_id}")
    async def tenant_get_user(tenant_id: str, user_id: str, request: Request):
        _local_only(request)
        user = AuthStore().get_user(user_id, tenant_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")
        return {"user_id": user_id, "tenant_id": tenant_id, "user": user}

    @app.patch("/api/tenants/{tenant_id}/users/{user_id}")
    async def tenant_update_user(
        tenant_id: str, user_id: str, request: Request, payload: UpdateUserRequest
    ):
        _local_only(request)
        updated = AuthStore().update_user(payload.user_id, payload.tenant_id, payload.updates)
        if not updated:
            raise HTTPException(status_code=404, detail="User or tenant not found.")
        return {
            "user_id": payload.user_id,
            "tenant_id": payload.tenant_id,
            "updated": True,
        }

    @app.delete("/api/tenants/{tenant_id}/users/{user_id}")
    async def tenant_delete_user(tenant_id: str, user_id: str, request: Request):
        _local_only(request)
        removed = AuthStore().delete_user(user_id, tenant_id)
        if not removed:
            raise HTTPException(status_code=404, detail="User not found.")
        return {"user_id": user_id, "tenant_id": tenant_id, "removed": True}

    @app.put("/api/tenants/{tenant_id}/users/{user_id}/roles")
    async def tenant_add_role(tenant_id: str, user_id: str, request: Request, payload: RoleRequest):
        _local_only(request)
        assigned = AuthStore().add_role(user_id, tenant_id, payload.role)
        if not assigned:
            raise HTTPException(status_code=404, detail="User or tenant not found.")
        return {"user_id": user_id, "tenant_id": tenant_id, "assigned": True}

    @app.delete("/api/tenants/{tenant_id}/users/{user_id}/roles/{role_name}")
    async def tenant_remove_role(tenant_id: str, user_id: str, role_name: str, request: Request):
        _local_only(request)
        store = AuthStore()
        if store.get_user(user_id, tenant_id) is None:
            raise HTTPException(status_code=404, detail="User or tenant not found.")
        # Role removal is idempotent: removing an absent role is a no-op success.
        store.remove_role(user_id, tenant_id, role_name)
        return {"user_id": user_id, "tenant_id": tenant_id, "role": role_name, "removed": True}

    @app.put("/api/tenants/{tenant_id}/users/{user_id}/permissions")
    async def tenant_set_permission(
        tenant_id: str, user_id: str, request: Request, payload: PermissionRequest
    ):
        _local_only(request)
        granted = AuthStore().set_user_permission(
            user_id,
            tenant_id,
            payload.resource,
            payload.permission,
            payload.value,
        )
        if not granted:
            raise HTTPException(status_code=404, detail="User or tenant not found.")
        return {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "resource": payload.resource,
            "permission": payload.permission,
            "value": payload.value,
        }

    @app.get("/api/tenants/{tenant_id}/users/{user_id}/permissions")
    async def tenant_get_permission(
        tenant_id: str,
        user_id: str,
        request: Request,
        resource: str,
        permission: str,
    ):
        _local_only(request)
        value = AuthStore().get_user_permission(user_id, tenant_id, resource, permission)
        return {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "resource": resource,
            "permission": permission,
            "value": value,
        }
