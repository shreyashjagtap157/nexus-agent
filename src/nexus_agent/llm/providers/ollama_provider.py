"""Ollama Provider implementation."""

from __future__ import annotations

import logging
from typing import Any

from nexus_agent.llm.base import ProviderCapabilities
from nexus_agent.llm.providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class OllamaProvider(OpenAIProvider):
    """Ollama local provider using its OpenAI-compatible endpoint."""

    def __init__(self, config: dict[str, Any]):
        """Initialize Ollama provider.

        Args:
            config: Config dict.
        """
        ollama_config = dict(config)
        ollama_config.setdefault("api_key", None)  # Ollama doesn't require API key
        ollama_config.setdefault("model", "llama3")
        ollama_config.setdefault("api_url", "http://localhost:11434/v1/chat/completions")
        super().__init__(ollama_config)

    @property
    def name(self) -> str:
        return "ollama"

    def get_capabilities(self) -> ProviderCapabilities:
        # Most modern Ollama models support system messages and streaming, but tool calling depends on model
        return ProviderCapabilities(
            supports_tool_calling=True,
            supports_vision=False,
            supports_streaming=True,
            supports_system_message=True,
            supports_parallel_tool_calls=False,
            max_context_length=8192,
            max_output_tokens=2048,
        )

    def get_available_models(self) -> list[dict[str, Any]]:
        # In a real environment, we'd query http://localhost:11434/api/tags
        # We will return common defaults or read from config if provided
        configured = self._config.get("available_models")
        if configured:
            return [{"id": m, "name": f"{m} (Configured)", "provider": "ollama"} for m in configured]
        return [
            {"id": "llama3", "name": "Llama 3", "provider": "ollama"},
            {"id": "mistral", "name": "Mistral", "provider": "ollama"},
            {"id": "phi3", "name": "Phi 3", "provider": "ollama"},
            {"id": "codegemma", "name": "CodeGemma", "provider": "ollama"},
        ]

    def validate_config(self) -> list[str]:
        # No api key validation required
        return []
