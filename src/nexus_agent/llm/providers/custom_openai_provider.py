"""Custom OpenAI-compatible Provider implementation."""

from __future__ import annotations

import logging
from typing import Any

from nexus_agent.llm.base import ProviderCapabilities
from nexus_agent.llm.providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class CustomOpenAIProvider(OpenAIProvider):
    """Custom OpenAI-compatible API provider (LM Studio, LocalAI, vLLM, etc.)."""

    def __init__(self, config: dict[str, Any]):
        """Initialize Custom OpenAI provider.

        Args:
            config: Config dict.
        """
        super().__init__(config)
        self._api_key = config.get("api_key") or "custom"  # Often not required for local hosts
        self._model_name = config.get("model") or "custom-model"
        self._api_url = config.get("api_url") or "http://localhost:8000/v1/chat/completions"

    @property
    def name(self) -> str:
        return "custom"

    def get_capabilities(self) -> ProviderCapabilities:
        # Default custom expectations
        return ProviderCapabilities(
            supports_tool_calling=self._config.get("supports_tool_calling", True),
            supports_vision=self._config.get("supports_vision", False),
            supports_streaming=True,
            supports_system_message=True,
            supports_parallel_tool_calls=False,
            max_context_length=self._config.get("context_size", 4096),
            max_output_tokens=self._config.get("context_size", 4096) // 2,
        )

    def get_available_models(self) -> list[dict[str, Any]]:
        return [
            {"id": self._model_name, "name": f"{self._model_name} (Custom Endpoint)", "provider": "custom"},
        ]

    def validate_config(self) -> list[str]:
        errors = []
        if not self._api_url:
            errors.append("Custom endpoint URL (api_url) is missing")
        return errors
