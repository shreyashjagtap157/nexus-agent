"""Provider Factory — Central loader for local and cloud LLM providers."""

from __future__ import annotations

import hashlib
import importlib
import logging
import threading
from typing import Any

from nexus_agent.llm.base import LLMProvider

logger = logging.getLogger(__name__)


# Provider name -> (module_path, class_name)
_PROVIDER_MAP: dict[str, tuple[str, str]] = {
    "openai": ("nexus_agent.llm.providers.openai_provider", "OpenAIProvider"),
    "anthropic": ("nexus_agent.llm.providers.anthropic_provider", "AnthropicProvider"),
    "google": ("nexus_agent.llm.providers.google_provider", "GoogleProvider"),
    "ollama": ("nexus_agent.llm.providers.ollama_provider", "OllamaProvider"),
    "openrouter": ("nexus_agent.llm.providers.openrouter_provider", "OpenRouterProvider"),
    "groq": ("nexus_agent.llm.providers.groq_provider", "GroqProvider"),
    "deepseek": ("nexus_agent.llm.providers.deepseek_provider", "DeepSeekProvider"),
    "bedrock": ("nexus_agent.llm.providers.aws_bedrock_provider", "AWSBedrockProvider"),
    "custom": ("nexus_agent.llm.providers.custom_openai_provider", "CustomOpenAIProvider"),
}


class ProviderFactory:
    """Instantiates the correct LLM provider engine based on settings.

    Providers are imported lazily and instances are cached to avoid
    reloading the same provider with the same config.
    """

    _instances: dict[str, LLMProvider] = {}
    _lock: threading.Lock = threading.Lock()

    @staticmethod
    def _load_provider_module(name: str):
        """Lazy-import the requested provider module via dict lookup."""
        entry = _PROVIDER_MAP.get(name)
        if entry is None:
            raise ValueError(f"Unknown provider: {name}")
        module_path, class_name = entry
        module = importlib.import_module(module_path)
        return getattr(module, class_name)

    @staticmethod
    def create_provider(
        provider_name: str,
        config: dict[str, Any],
        model_path_or_name: str | None = None,
    ) -> LLMProvider:
        """Create (or return cached) LLMProvider instance.

        Args:
            provider_name: Name of the provider (local, openai, anthropic, etc.)
            config: Full application configuration dictionary.
            model_path_or_name: Optional override for the model path/name.

        Returns:
            An LLMProvider instance.
        """
        name = provider_name.lower().strip()
        logger.info(f"Creating LLM provider: {name}")

        provider_config = config.get("providers", {}).get(name, {})
        if model_path_or_name:
            provider_config = dict(provider_config)
            provider_config["model"] = model_path_or_name

        # Build a cache key — local providers may have model-specific state
        # Include config hash to avoid stale cache hits
        config_str = str(sorted(provider_config.items()))
        config_hash = hashlib.md5(config_str.encode()).hexdigest()[:8]
        cache_key = f"{name}:{model_path_or_name or ''}:{config_hash}"
        with ProviderFactory._lock:
            cached = ProviderFactory._instances.get(cache_key)
            if cached is not None:
                logger.debug(f"Returning cached provider instance for {cache_key}")
                return cached

        if name == "local":
            from nexus_agent.llm.runtime_manager import RuntimeManager
            rm = RuntimeManager(config)
            instance = rm.select_engine(model_path_or_name)
        else:
            provider_cls = ProviderFactory._load_provider_module(name)
            instance = provider_cls(provider_config)

        with ProviderFactory._lock:
            ProviderFactory._instances[cache_key] = instance
        return instance

    @staticmethod
    def clear_cache():
        """Clear all cached provider instances, properly closing resources."""
        with ProviderFactory._lock:
            for key, provider in list(ProviderFactory._instances.items()):
                try:
                    provider.close()
                except (OSError, RuntimeError) as e:
                    logger.warning(f"Failed to close provider {key}: {e}")
            ProviderFactory._instances.clear()
