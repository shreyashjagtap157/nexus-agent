"""OpenAI Provider implementation."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from typing import Any

import httpx

from nexus_agent.llm.base import (
    LLMProvider,
    LLMResponse,
    Message,
    ProviderCapabilities,
    StreamChunk,
    ToolCall,
    ToolDefinition,
)

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    def __init__(self, config: dict[str, Any]):
        """Initialize OpenAI provider.

        Args:
            config: Config dict (must contain API key and optional default model).
        """
        self._config = config
        self._api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY")
        self._model_name = config.get("model") or "gpt-4o"
        self._api_url = config.get("api_url") or "https://api.openai.com/v1/chat/completions"

    @property
    def name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model_name

    def get_capabilities(self) -> ProviderCapabilities:
        # OpenAI models have rich support for tools, parallel calls, vision, streaming
        return ProviderCapabilities(
            supports_tool_calling=True,
            supports_vision=True,
            supports_streaming=True,
            supports_system_message=True,
            supports_parallel_tool_calls=True,
            max_context_length=128000,
            max_output_tokens=4096,
        )

    def _get_headers(self) -> dict[str, str]:
        if not self._api_key:
            raise ValueError("OpenAI API key is missing. Set it in config or via OPENAI_API_KEY env var.")
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _prepare_payload(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model_name,
            "messages": [msg.to_openai_format() for msg in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if tools:
            payload["tools"] = [t.to_openai_format() for t in tools]

        # Support OpenAI o-series reasoning effort
        if self._model_name.startswith("o1-") or self._model_name.startswith("o3-"):
            effort = self._config.get("effort_level") or "medium"
            payload = {k: v for k, v in payload.items() if k not in ("temperature", "stream")}
            payload["reasoning_effort"] = effort

        return payload


    def chat_completion(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        payload = self._prepare_payload(messages, tools, temperature, max_tokens, stream=False)
        payload.update(kwargs)

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                self._api_url,
                headers=self._get_headers(),
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

        choice = (result.get("choices") or [{}])[0]
        message = choice.get("message", {})

        tool_calls = None
        raw_tc = message.get("tool_calls")
        if raw_tc:
            tool_calls = [ToolCall.from_openai_format(tc) for tc in raw_tc]

        return LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason"),
            usage=result.get("usage"),
            model=self._model_name,
        )

    def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Iterator[StreamChunk]:
        payload = self._prepare_payload(messages, tools, temperature, max_tokens, stream=True)
        payload.update(kwargs)

        headers = self._get_headers()
        accumulated_tool_calls: dict[int, dict[str, Any]] = {}

        with httpx.Client(timeout=60.0) as client:
            with client.stream("POST", self._api_url, headers=headers, json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        choice = chunk["choices"][0] if chunk.get("choices") else {}
                        delta = choice.get("delta", {})
                        finish = choice.get("finish_reason")
                        content = delta.get("content")

                        # Parse streaming tool calls
                        raw_tc = delta.get("tool_calls")
                        chunk_tool_calls = None

                        if raw_tc:
                            for tc_delta in raw_tc:
                                idx = tc_delta.get("index", 0)
                                if idx not in accumulated_tool_calls:
                                    accumulated_tool_calls[idx] = {
                                        "id": tc_delta.get("id", ""),
                                        "function": {"name": "", "arguments": ""},
                                    }
                                acc = accumulated_tool_calls[idx]
                                if tc_delta.get("id"):
                                    acc["id"] = tc_delta["id"]
                                func = tc_delta.get("function", {})
                                if "name" in func:
                                    acc["function"]["name"] += func["name"]
                                if "arguments" in func:
                                    acc["function"]["arguments"] += func["arguments"]

                        if finish == "tool_calls" and accumulated_tool_calls:
                            chunk_tool_calls = [
                                ToolCall.from_openai_format(tc)
                                for tc in accumulated_tool_calls.values()
                            ]
                            accumulated_tool_calls.clear()

                        yield StreamChunk(
                            content=content,
                            tool_calls=chunk_tool_calls,
                            finish_reason=finish,
                            is_final=finish is not None,
                        )

    def get_available_models(self) -> list[dict[str, Any]]:
        return [
            {"id": "gpt-4o", "name": "GPT-4o (Default)", "provider": "openai"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini (Fast)", "provider": "openai"},
            {"id": "o1-mini", "name": "o1-mini (Reasoning)", "provider": "openai"},
            {"id": "o3-mini", "name": "o3-mini (Reasoning)", "provider": "openai"},
        ]

    def validate_config(self) -> list[str]:
        errors = []
        if not self._api_key:
            errors.append("OpenAI API key (OPENAI_API_KEY) is not set")
        return errors
