"""Provider Factory — Central loader for local and cloud LLM providers."""

from __future__ import annotations

import hashlib
import importlib
import logging
import threading
from collections.abc import Iterator
from typing import Any

from nexus_agent.llm.base import (
    LLMProvider,
    LLMResponse,
    Message,
    StreamChunk,
    ToolDefinition,
)

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


class FallbackProvider(LLMProvider):
    """Chain of providers tried in order on failure.

    The chain is walked top-to-bottom: `primary` is tried first; on a
    `RuntimeError`/`ConnectionError`/`TimeoutError`/`OSError` (network or
    hard load failure), the next provider in `fallbacks` is tried. The
    first successful response wins. Streaming does not fall back mid-stream
    (the iterator is returned as-is from the provider that produced it).

    The wrapper's `name` is `"<primary>-><fb1>-><fb2>"` and `model_name`
    follows the primary.
    """

    def __init__(
        self,
        primary: LLMProvider,
        fallbacks: list[LLMProvider] | None = None,
    ) -> None:
        self._primary = primary
        self._fallbacks: list[LLMProvider] = list(fallbacks or [])
        self._chain = [self._primary, *self._fallbacks]
        self._last_used: LLMProvider | None = None

    @property
    def name(self) -> str:
        return "->".join(p.name for p in self._chain)

    @property
    def model_name(self) -> str:
        return self._primary.model_name

    @property
    def primary(self) -> LLMProvider:
        return self._primary

    @property
    def last_used(self) -> LLMProvider | None:
        return self._last_used

    def get_capabilities(self) -> Any:
        # Capabilities follow the primary — fallbacks may differ but the
        # caller already accepted the primary's contract.
        return self._primary.get_capabilities()

    def get_available_models(self) -> list[dict[str, Any]]:
        try:
            return self._primary.get_available_models()
        except (OSError, RuntimeError, ValueError, ConnectionError) as e:
            logger.debug(f"primary models() failed: {e}; falling back")
            for fb in self._fallbacks:
                try:
                    return fb.get_available_models()
                except (OSError, RuntimeError, ValueError, ConnectionError) as e2:
                    logger.debug(f"fallback {fb.name} models() failed: {e2}")
        return []

    def _walk(self, op_name: str, fn):
        """Call `fn(provider)` over the chain, returning the first success."""
        last_exc: BaseException | None = None
        for provider in self._chain:
            try:
                result = fn(provider)
                self._last_used = provider
                if provider is not self._primary:
                    logger.info(
                        f"FallbackProvider: {op_name} succeeded via fallback '{provider.name}'"
                    )
                return result
            except (RuntimeError, ConnectionError, TimeoutError, OSError) as e:
                last_exc = e
                logger.warning(
                    f"FallbackProvider: {op_name} failed on '{provider.name}': {e}"
                )
                continue
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("FallbackProvider: empty chain")

    def chat_completion(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        return self._walk(
            "chat_completion",
            lambda p: p.chat_completion(messages, tools, temperature, max_tokens, **kwargs),
        )

    def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Iterator[StreamChunk]:
        # Streaming has no per-call fallback — return the primary's iterator.
        # (Mid-stream fallback is out of scope; callers should retry from
        # the start with the next provider in the chain if needed.)
        return self._primary.chat_completion_stream(
            messages, tools, temperature, max_tokens, **kwargs
        )

    def close(self) -> None:
        for p in self._chain:
            try:
                p.close()
            except (OSError, RuntimeError) as e:
                logger.debug(f"FallbackProvider: close() on '{p.name}' failed: {e}")

    def __repr__(self) -> str:
        return f"<FallbackProvider chain={self.name} last_used={self._last_used and self._last_used.name}>"


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
    def create_with_fallback(
        primary_name: str,
        fallback_names: list[str],
        config: dict[str, Any],
        model_path_or_name: str | None = None,
    ) -> FallbackProvider:
        """Build a `FallbackProvider` from a list of provider names.

        Each name is resolved via `create_provider`. The first provider
        (primary) is tried first; the rest are tried in order on failure.
        If `fallback_names` is empty, this is equivalent to a single-provider
        chain.
        """
        primary = ProviderFactory.create_provider(
            primary_name, config, model_path_or_name
        )
        fallbacks: list[LLMProvider] = []
        for name in fallback_names:
            try:
                fallbacks.append(
                    ProviderFactory.create_provider(name, config, model_path_or_name)
                )
            except (ValueError, ImportError, OSError, RuntimeError) as e:
                logger.warning(
                    f"create_with_fallback: skipping fallback '{name}': {e}"
                )
        return FallbackProvider(primary, fallbacks)

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
