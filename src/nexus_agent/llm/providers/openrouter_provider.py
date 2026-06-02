"""OpenRouter Provider implementation."""

from __future__ import annotations

import logging
import os
from typing import Any

from nexus_agent.llm.base import ProviderCapabilities
from nexus_agent.llm.providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class OpenRouterProvider(OpenAIProvider):
    """OpenRouter provider utilizing its OpenAI-compatible endpoint."""

    def __init__(self, config: dict[str, Any]):
        """Initialize OpenRouter provider.

        Args:
            config: Config dict.
        """
        super().__init__(config)
        self._api_key = config.get("api_key") or os.environ.get("OPENROUTER_API_KEY")
        self._model_name = config.get("model") or "anthropic/claude-3.5-sonnet"
        self._api_url = config.get("api_url") or "https://openrouter.ai/api/v1/chat/completions"

    @property
    def name(self) -> str:
        return "openrouter"

    def get_capabilities(self) -> ProviderCapabilities:
        # OpenRouter supports all standard features since it proxies to other models
        return ProviderCapabilities(
            supports_tool_calling=True,
            supports_vision=True,
            supports_streaming=True,
            supports_system_message=True,
            supports_parallel_tool_calls=True,
            max_context_length=200000,
            max_output_tokens=8192,
        )

    def _get_headers(self) -> dict[str, str]:
        headers = super()._get_headers()
        # OpenRouter expects optional HTTP-Referer and X-Title headers
        headers["HTTP-Referer"] = "https://github.com/google-deepmind/nexus-agent"
        headers["X-Title"] = "NexusAgent"
        return headers

    def get_available_models(self) -> list[dict[str, Any]]:
        return [
            {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet (OpenRouter)", "provider": "openrouter"},
            {"id": "meta-llama/llama-3.1-70b-instruct", "name": "Llama 3.1 70B (OpenRouter)", "provider": "openrouter"},
            {"id": "google/gemini-pro-1.5", "name": "Gemini 1.5 Pro (OpenRouter)", "provider": "openrouter"},
        ]

    def validate_config(self) -> list[str]:
        errors = []
        if not self._api_key:
            errors.append("OpenRouter API key (OPENROUTER_API_KEY) is not set")
        return errors
