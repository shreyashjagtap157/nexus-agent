"""NVIDIA NIM OpenAI-compatible provider."""
from __future__ import annotations

import os
import time
from typing import Any

import httpx

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


    def chat_completion(
        self,
        messages,
        tools=None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ):
        """Handle NIM's synchronous 200 and asynchronous 202 invocation paths."""
        payload = self._prepare_payload(messages, tools, temperature, max_tokens, stream=False)
        payload.update(kwargs)
        if "reasoning_budget" in self._config and "reasoning_budget" not in payload:
            payload["reasoning_budget"] = self._config["reasoning_budget"]
        if "top_p" in self._config and "top_p" not in payload:
            payload["top_p"] = self._config["top_p"]

        headers = self._get_headers()
        poll_seconds = max(0.25, float(self._config.get("pending_poll_seconds", 1.0)))
        max_wait_seconds = max(5.0, float(self._config.get("pending_max_wait_seconds", 300.0)))
        deadline = time.monotonic() + max_wait_seconds

        with httpx.Client(timeout=float(self._config.get("timeout_seconds", 120.0))) as client:
            response = client.post(self._api_url, headers=headers, json=payload)
            if response.status_code == 202:
                body = response.json()
                request_id = body.get("requestId")
                if not request_id:
                    response.raise_for_status()
                    raise RuntimeError("NVIDIA NIM returned HTTP 202 without requestId.")
                status_url = self._api_url.rsplit("/chat/completions", 1)[0] + f"/status/{request_id}"
                while time.monotonic() < deadline:
                    time.sleep(poll_seconds)
                    polled = client.get(status_url, headers={"Authorization": headers["Authorization"], "Accept": "application/json"})
                    if polled.status_code == 202:
                        continue
                    polled.raise_for_status()
                    response = polled
                    break
                else:
                    raise TimeoutError(
                        f"NVIDIA NIM invocation {request_id} remained pending for {max_wait_seconds:.1f}s."
                    )
            response.raise_for_status()
            result = response.json()

        choice = (result.get("choices") or [{}])[0]
        message = choice.get("message", {})
        from nexus_agent.llm.base import LLMResponse, ToolCall
        raw_tool_calls = message.get("tool_calls") or []
        tool_calls = [ToolCall.from_openai_format(item) for item in raw_tool_calls]
        return LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls or None,
            finish_reason=choice.get("finish_reason"),
            usage=result.get("usage"),
            model=self._model_name,
        )

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tool_calling=True,
            supports_vision=False,
            supports_streaming=True,
            supports_system_message=True,
            supports_parallel_tool_calls=False,
            max_context_length=int(self._config.get("context_size", 1_000_000)),
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
