"""Google Gemini Provider implementation."""

from __future__ import annotations

import logging
import os
from typing import Any

from nexus_agent.llm.base import ProviderCapabilities
from nexus_agent.llm.providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class GoogleProvider(OpenAIProvider):
    """Google Gemini provider utilizing the OpenAI-compatible endpoint."""

    def __init__(self, config: dict[str, Any]):
        """Initialize Google Gemini provider.

        Args:
            config: Config dict.
        """
        google_config = dict(config)
        if not google_config.get("api_key"):
            google_config["api_key"] = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not google_config.get("model"):
            google_config["model"] = "gemini-1.5-pro"
        if not google_config.get("api_url"):
            google_config["api_url"] = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        super().__init__(google_config)

    @property
    def name(self) -> str:
        return "google"

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tool_calling=True,
            supports_vision=True,
            supports_streaming=True,
            supports_system_message=True,
            supports_parallel_tool_calls=False,  # Gemini doesn't support parallel tools well in this layer
            max_context_length=1000000,          # Gemini has huge context
            max_output_tokens=8192,
        )

    def get_available_models(self) -> list[dict[str, Any]]:
        return [
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro (Analytical)", "provider": "google"},
            {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash (Fast)", "provider": "google"},
            {"id": "gemini-2.0-flash-exp", "name": "Gemini 2.0 Flash (Experimental)", "provider": "google"},
        ]

    def validate_config(self) -> list[str]:
        errors = []
        if not self._api_key:
            errors.append("Gemini API key (GEMINI_API_KEY) is not set")
        return errors
