"""Provider configuration API. Secrets are handled by AuthStore, not config files."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from nexus_agent.core.config import load_config, save_user_config


class ProviderConfigRequest(BaseModel):
    model: str | None = Field(default=None, max_length=1000)
    base_url: str | None = Field(default=None, max_length=4000)
    api_url: str | None = Field(default=None, max_length=4000)
    context_size: int | None = Field(default=None, ge=128, le=10_000_000)
    max_tokens: int | None = Field(default=None, ge=1, le=1_000_000)
    effort_level: str | None = Field(default=None, max_length=32)
    extra: dict[str, Any] = Field(default_factory=dict)


def register_provider_config_routes(app: Any, state_manager: Any) -> None:
    @app.get("/api/provider-config")
    async def provider_config_get():
        config = load_config(workspace=Path(state_manager.get("workspace") or Path.cwd()))
        providers = config.get("providers", {})
        output: dict[str, Any] = {}
        if isinstance(providers, dict):
            for name, value in providers.items():
                if not isinstance(value, dict):
                    continue
                safe = dict(value)
                for secret_key in ("api_key", "api_secret", "secret_key", "password", "token"):
                    safe.pop(secret_key, None)
                output[name] = safe
        return {"providers": output}

    @app.put("/api/provider-config/{provider}")
    async def provider_config_put(provider: str, request: ProviderConfigRequest):
        provider_id = provider.strip().lower()
        if not provider_id or any(ch in provider_id for ch in "/\\\n\r"):
            raise HTTPException(status_code=400, detail="Invalid provider ID.")
        patch = {
            key: value
            for key, value in request.model_dump().items()
            if key != "extra" and value is not None
        }
        if request.extra:
            patch.update(request.extra)
        if not patch:
            raise HTTPException(status_code=400, detail="No provider configuration fields supplied.")
        save_user_config({"providers": {provider_id: patch}})
        return {"provider": provider_id, "saved": True}
