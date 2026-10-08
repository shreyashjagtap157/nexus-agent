"""Provider routing for dynamically generated team roles."""
from __future__ import annotations

from typing import Any

from nexus_agent.llm.base import LLMProvider
from nexus_agent.llm.providers.factory import ProviderFactory
from .models import AgentProfile


def make_provider_selector(
    config: dict[str, Any],
    default_provider: LLMProvider,
):
    """Create a role-aware provider selector.

    Configuration is read from:
      team.roles.<model_role or role_id>.provider
      team.roles.<model_role or role_id>.model
      team.roles.<model_role or role_id>.fallbacks

    A missing role mapping returns the default provider.
    """
    specs = config.get("team", {}).get("roles", {})
    if not isinstance(specs, dict):
        specs = {}

    def select(profile: AgentProfile) -> LLMProvider:
        if profile.provider:
            if profile.fallbacks:
                return ProviderFactory.create_with_fallback(
                    profile.provider,
                    profile.fallbacks,
                    config,
                    profile.model,
                )
            return ProviderFactory.create_provider(profile.provider, config, profile.model)
        spec = specs.get(profile.model_role) or specs.get(profile.role_id) or {}
        if not isinstance(spec, dict):
            return default_provider
        provider_name = str(spec.get("provider") or "").strip()
        model = spec.get("model")
        if not provider_name:
            return default_provider
        model_override = str(model).strip() if model is not None else None
        fallbacks = [
            str(item).strip()
            for item in spec.get("fallbacks", [])
            if str(item).strip()
        ]
        if fallbacks:
            return ProviderFactory.create_with_fallback(
                provider_name,
                fallbacks,
                config,
                model_override,
            )
        return ProviderFactory.create_provider(
            provider_name,
            config,
            model_override,
        )

    return select
