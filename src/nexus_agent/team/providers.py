"""Provider routing for dynamically generated team roles."""
from __future__ import annotations

from typing import Any

from nexus_agent.llm.base import LLMProvider
from nexus_agent.llm.providers.factory import ProviderFactory

from .models import AgentProfile


def _routing_target(value: str) -> tuple[str, str | None]:
    target = str(value or "").strip()
    if not target:
        return "", None
    if "/" not in target:
        return target, None
    provider, model = target.split("/", 1)
    return provider.strip(), model.strip() or None


def make_provider_selector(
    config: dict[str, Any],
    default_provider: LLMProvider,
):
    """Create a role-aware provider selector.

    Configuration is read from:
      team.roles.<model_role or role_id>.provider
      team.roles.<model_role or role_id>.model
      team.roles.<model_role or role_id>.fallbacks

    Fallback entries may be provider names or `provider/model` targets.
    A missing role mapping returns the default provider.
    """
    specs = config.get("team", {}).get("roles", {})
    if not isinstance(specs, dict):
        specs = {}

    def select(profile: AgentProfile) -> LLMProvider:
        spec = specs.get(profile.model_role) or specs.get(profile.role_id) or {}
        if not isinstance(spec, dict):
            spec = {}

        provider_name, provider_model = _routing_target(
            profile.provider or spec.get("provider") or ""
        )
        model = profile.model or spec.get("model") or provider_model
        model_override = str(model).strip() if model is not None else None

        fallback_specs = list(profile.fallbacks or [])
        if not fallback_specs:
            fallback_specs = [
                str(item).strip()
                for item in spec.get("fallbacks", [])
                if str(item).strip()
            ]

        if not provider_name:
            return default_provider

        primary: LLMProvider | None = None
        primary_error: Exception | None = None
        try:
            primary = ProviderFactory.create_provider(
                provider_name,
                config,
                model_override,
            )
        except (ValueError, ImportError, OSError, RuntimeError) as exc:
            primary_error = exc

        fallback_targets: list[LLMProvider] = []
        for raw_target in fallback_specs:
            fallback_provider, fallback_model = _routing_target(raw_target)
            if not fallback_provider:
                continue
            try:
                fallback_targets.append(
                    ProviderFactory.create_provider(
                        fallback_provider,
                        config,
                        fallback_model,
                    )
                )
            except (ValueError, ImportError, OSError, RuntimeError):
                continue

        from nexus_agent.llm.providers.factory import FallbackProvider

        if primary is None:
            if not fallback_targets:
                if primary_error is not None:
                    raise primary_error
                return default_provider
            # A primary that cannot initialize is skipped entirely; the first
            # usable fallback becomes the active primary and the remaining
            # providers continue the normal fallback chain.
            return FallbackProvider(fallback_targets[0], fallback_targets[1:])

        if not fallback_targets:
            return primary

        return FallbackProvider(primary, fallback_targets)

    return select
