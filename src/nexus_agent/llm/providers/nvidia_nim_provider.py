"""NVIDIA NIM OpenAI-compatible provider."""
from __future__ import annotations

import os
from typing import Any

from nexus_agent.llm.base import ProviderCapabilities
from nexus_agent.llm.providers.openai_provider import OpenAIProvider


class NvidiaNIMProvider(OpenAIProvider):
    """NVIDIA NIM chat-completions provider using the OpenAI-compatible API."""

    DEFAULT_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
    DEFAULT_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self._api_key = (
            config.get("api_key")
            or config.get("api_key_env_value")
            or os.environ.get("NVIDIA_NIM_API_KEY")
        )
        self._model_name = config.get("model") or self.DEFAULT_MODEL
        self._api_url = config.get("api_url") or self.DEFAULT_API_URL

    @property
    def name(self) -> str:
        return "nvidia_nim"

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tool_calling=True,
            supports_vision=False,
            supports_streaming=True,
            supports_system_message=True,
            supports_parallel_tool_calls=False,
            max_context_length=int(self._config.get("context_size", 128000)),
            max_output_tokens=int(self._config.get("max_tokens", 16384)),
        )

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        if not self._api_key:
            errors.append("NVIDIA NIM API key is missing. Set NVIDIA_NIM_API_KEY or providers.nvidia_nim.api_key.")
        if not self._api_url:
            errors.append("NVIDIA NIM API URL is missing.")
        if not self._model_name:
            errors.append("NVIDIA NIM model is missing.")
        return errors
