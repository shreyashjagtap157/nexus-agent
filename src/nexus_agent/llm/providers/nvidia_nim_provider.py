"""NVIDIA NIM OpenAI-compatible provider with pending-result polling."""
from __future__ import annotations

import os
import time
from typing import Any

import httpx

from nexus_agent.llm.base import LLMResponse, ToolCall
from nexus_agent.llm.providers.openai_provider import OpenAIProvider


class NvidiaNIMProvider(OpenAIProvider):
    """NVIDIA NIM chat-completions provider.

    NVIDIA documents both immediate 200 responses and asynchronous 202
    responses carrying a requestId. The latter are polled through the
    provider's /status/{requestId} endpoint.
    """

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
        self._timeout_seconds = float(config.get("timeout_seconds", 120.0))
        self._pending_poll_seconds = float(config.get("pending_poll_seconds", 1.0))
        self._pending_max_wait_seconds = float(config.get("pending_max_wait_seconds", 600.0))
        self._status_url = str(
            config.get("status_url")
            or self._api_url.rsplit("/chat/completions", 1)[0] + "/status"
        )

    @property
    def name(self) -> str:
        return "nvidia_nim"

    def get_capabilities(self):
        from nexus_agent.llm.base import ProviderCapabilities

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
            errors.append(
                "NVIDIA NIM API key is missing. Set NVIDIA_NIM_API_KEY or providers.nvidia_nim.api_key."
            )
        if not self._api_url:
            errors.append("NVIDIA NIM API URL is missing.")
        if not self._model_name:
            errors.append("NVIDIA NIM model is missing.")
        return errors

    def _headers(self) -> dict[str, str]:
        if not self._api_key:
            raise ValueError("NVIDIA NIM API key is missing.")
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _extract_response(self, payload: dict[str, Any]) -> LLMResponse:
        choice = (payload.get("choices") or [{}])[0]
        message = choice.get("message", {}) or {}
        raw_tool_calls = message.get("tool_calls") or []
        tool_calls = None
        if raw_tool_calls:
            tool_calls = [
                ToolCall.from_openai_format(item)
                for item in raw_tool_calls
            ]
        return LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason"),
            usage=payload.get("usage"),
            model=self._model_name,
        )

    def chat_completion(
        self,
        messages,
        tools=None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        payload = self._prepare_payload(
            messages,
            tools,
            temperature,
            max_tokens,
            stream=False,
        )
        payload.update(kwargs)
        payload["model"] = self._model_name

        # NIM-specific generation controls are read from provider config and
        # only sent to this provider so generic OpenAI-compatible endpoints
        # are not forced to accept them.
        for key in ("top_p", "reasoning_budget", "seed", "chat_template_kwargs"):
            if key in self._config and self._config[key] is not None:
                payload[key] = self._config[key]

        deadline = time.monotonic() + self._pending_max_wait_seconds
        with httpx.Client(timeout=self._timeout_seconds) as client:
            response = client.post(
                self._api_url,
                headers=self._headers(),
                json=payload,
            )

            if response.status_code == 202:
                data = response.json()
                request_id = data.get("requestId") or data.get("request_id")
                if not request_id:
                    raise RuntimeError("NVIDIA NIM returned 202 without requestId.")
                return self._poll_pending(client, str(request_id), deadline)

            response.raise_for_status()
            return self._extract_response(response.json())

    def _poll_pending(
        self,
        client: httpx.Client,
        request_id: str,
        deadline: float,
    ) -> LLMResponse:
        status_url = f"{self._status_url.rstrip('/')}/{request_id}"
        while True:
            response = client.get(status_url, headers=self._headers())

            if response.status_code == 200:
                return self._extract_response(response.json())

            if response.status_code == 202:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"NVIDIA NIM request {request_id} remained pending for "
                        f"{self._pending_max_wait_seconds:.1f}s."
                    )
                time.sleep(max(0.1, self._pending_poll_seconds))
                continue

            response.raise_for_status()
