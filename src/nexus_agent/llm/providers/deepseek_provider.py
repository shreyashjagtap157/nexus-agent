"""DeepSeek Provider implementation."""

from __future__ import annotations

import logging
import os
from typing import Any

from nexus_agent.llm.base import ProviderCapabilities
from nexus_agent.llm.providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek API provider utilizing its OpenAI-compatible endpoint."""

    def __init__(self, config: dict[str, Any]):
        """Initialize DeepSeek provider.

        Args:
            config: Config dict.
        """
        super().__init__(config)
        self._api_key = config.get("api_key") or os.environ.get("DEEPSEEK_API_KEY")
        self._model_name = config.get("model") or "deepseek-chat"
        self._api_url = config.get("api_url") or "https://api.deepseek.com/beta/chat/completions"

    @property
    def name(self) -> str:
        return "deepseek"

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tool_calling=True,
            supports_vision=False,
            supports_streaming=True,
            supports_system_message=True,
            supports_parallel_tool_calls=True,
            max_context_length=64000,
            max_output_tokens=4096,
        )

    def get_available_models(self) -> list[dict[str, Any]]:
        return [
            {"id": "deepseek-chat", "name": "DeepSeek Chat (V3 / R1-Lite)", "provider": "deepseek"},
            {"id": "deepseek-coder", "name": "DeepSeek Coder (Coding Optimized)", "provider": "deepseek"},
        ]

    def validate_config(self) -> list[str]:
        errors = []
        if not self._api_key:
            errors.append("DeepSeek API key (DEEPSEEK_API_KEY) is not set")
        return errors
