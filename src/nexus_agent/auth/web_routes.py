"""Web endpoints for provider catalog and credential lifecycle."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from pydantic import BaseModel, Field

from nexus_agent.auth import AuthStore
from nexus_agent.llm.providers.catalog import all_providers
from nexus_agent.core.config import save_user_config


class CredentialRequest(BaseModel):
    api_key: str = Field(min_length=1, max_length=10000)


class ProviderConfigRequest(BaseModel):
    model: str | None = Field(default=None, max_length=1000)
    base_url: str | None = Field(default=None, max_length=4000)
    api_url: str | None = Field(default=None, max_length=4000)
    context_size: int | None = Field(default=None, ge=256, le=2_000_000)
    max_tokens: int | None = Field(default=None, ge=1, le=1_000_000)


def register_auth_routes(app: Any) -> None:
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

    @app.get("/api/provider-config")
    async def provider_config():
        from nexus_agent.core.config import load_config
        config = load_config()
        providers = config.get("providers", {})
        output = {}
        if isinstance(providers, dict):
            for provider_id, value in providers.items():
                if not isinstance(value, dict):
                    continue
                output[provider_id] = {
                    key: value[key]
                    for key in ("model", "base_url", "api_url", "context_size", "max_tokens")
                    if key in value
                }
        return {"providers": output}

    @app.put("/api/provider-config/{provider}")
    async def update_provider_config(provider: str, request: Request, payload: ProviderConfigRequest):
        if request.client and request.client.host not in {"127.0.0.1", "::1", "localhost"}:
            raise HTTPException(status_code=403, detail="Provider configuration mutation is restricted to local clients.")
        values = payload.model_dump(exclude_none=True)
        save_user_config({"providers": {provider.lower(): values}})
        return {"provider": provider.lower(), "config": values}

    @app.get("/api/auth")
    async def auth_list():
        return {"credentials": AuthStore().list()}

    @app.put("/api/auth/{provider}")
    async def auth_set(provider: str, request: Request, payload: CredentialRequest):
        if request.client and request.client.host not in {"127.0.0.1", "::1", "localhost"}:
            raise HTTPException(status_code=403, detail="Credential mutation is restricted to local clients.")
        AuthStore().set(provider, payload.api_key)
        return {"provider": provider.lower(), "stored": True}

    @app.delete("/api/auth/{provider}")
    async def auth_delete(provider: str, request: Request):
        if request.client and request.client.host not in {"127.0.0.1", "::1", "localhost"}:
            raise HTTPException(status_code=403, detail="Credential mutation is restricted to local clients.")
        return {"provider": provider.lower(), "removed": AuthStore().remove(provider)}
