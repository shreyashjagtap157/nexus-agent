"""Groq Provider implementation."""

from __future__ import annotations

import logging
import os
from typing import Any

from nexus_agent.llm.base import ProviderCapabilities
from nexus_agent.llm.providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class GroqProvider(OpenAIProvider):
    """Groq API provider utilizing its OpenAI-compatible endpoint."""

    def __init__(self, config: dict[str, Any]):
        """Initialize Groq provider.

        Args:
            config: Config dict.
        """
        groq_config = dict(config)
        groq_config.setdefault("api_key", os.environ.get("GROQ_API_KEY"))
        groq_config.setdefault("model", "llama3-70b-8192")
        groq_config.setdefault("api_url", "https://api.groq.com/openai/v1/chat/completions")
        super().__init__(groq_config)

    @property
    def name(self) -> str:
        return "groq"

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tool_calling=True,
            supports_vision=False,
            supports_streaming=True,
            supports_system_message=True,
            supports_parallel_tool_calls=False,
            max_context_length=8192,
            max_output_tokens=4096,
        )

    def get_available_models(self) -> list[dict[str, Any]]:
        return [
            {"id": "llama3-70b-8192", "name": "Llama 3 70B (8k)", "provider": "groq"},
            {"id": "llama3-8b-8192", "name": "Llama 3 8B (8k)", "provider": "groq"},
            {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7B (32k)", "provider": "groq"},
            {"id": "gemma2-9b-it", "name": "Gemma 2 9B (8k)", "provider": "groq"},
        ]

    def validate_config(self) -> list[str]:
        errors = []
        if not self._api_key:
            errors.append("Groq API key (GROQ_API_KEY) is not set")
        return errors
