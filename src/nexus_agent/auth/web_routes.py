"""Web endpoints for provider catalog and credential lifecycle."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from nexus_agent.auth import AuthStore
from nexus_agent.llm.providers.catalog import all_providers


class CredentialRequest(BaseModel):
    api_key: str = Field(min_length=1, max_length=10000)


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

    @app.get("/api/auth")
    async def auth_list():
        return {"credentials": AuthStore().list()}

    @app.put("/api/auth/{provider}")
    async def auth_set(provider: str, request: CredentialRequest):
        AuthStore().set(provider, request.api_key)
        return {"provider": provider.lower(), "stored": True}

    @app.delete("/api/auth/{provider}")
    async def auth_delete(provider: str):
        return {"provider": provider.lower(), "removed": AuthStore().remove(provider)}
