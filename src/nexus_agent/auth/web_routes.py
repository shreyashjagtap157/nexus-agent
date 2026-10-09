"""Web endpoints for provider catalog and credential lifecycle."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

from nexus_agent.auth import AuthStore
from nexus_agent.core.config import _strip_secrets, load_config, save_user_config
from nexus_agent.llm.base import Message, Role
from nexus_agent.llm.providers.catalog import all_providers
from nexus_agent.llm.providers.models_dev import ModelsDevCatalog
from nexus_agent.storage.layout import StorageLayout


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
