"""Optional LiteLLM bridge for broad provider compatibility."""
from __future__ import annotations

from typing import Any, Iterator

from nexus_agent.llm.base import (
    LLMProvider,
    LLMResponse,
    Message,
    ProviderCapabilities,
    StreamChunk,
    ToolCall,
    ToolDefinition,
)


class LiteLLMProvider(LLMProvider):
    """Use LiteLLM as a compatibility layer for provider/model combinations."""

    def __init__(self, config: dict[str, Any]):
        try:
            import litellm
        except ImportError as exc:
            raise RuntimeError(
                "LiteLLM support is not installed. Install nexus-agent[providers]."
            ) from exc
        self._litellm = litellm
        self._config = config
        self._model_name = str(config.get("model") or "").strip()
        self._api_key = config.get("api_key")
        self._api_base = config.get("api_base") or config.get("base_url")
        self._context_size = int(config.get("context_size", 128000))
        self._max_output = int(config.get("max_tokens", 16384))

        if not self._model_name:
            raise ValueError("LiteLLM provider requires providers.litellm.model.")

    @property
    def name(self) -> str:
        return "litellm"

    @property
    def model_name(self) -> str:
        return self._model_name

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tool_calling=True,
            supports_vision=bool(self._config.get("supports_vision", False)),
            supports_streaming=True,
            supports_system_message=True,
            supports_parallel_tool_calls=bool(
                self._config.get("supports_parallel_tool_calls", True)
            ),
            max_context_length=self._context_size,
            max_output_tokens=self._max_output,
        )

    @staticmethod
    def _messages(messages: list[Message]) -> list[dict[str, Any]]:
        return [message.to_openai_format() for message in messages]

    @staticmethod
    def _tools(tools: list[ToolDefinition] | None) -> list[dict[str, Any]] | None:
        return [tool.to_openai_format() for tool in tools] if tools else None

    @staticmethod
    def _tool_calls(message: Any) -> list[ToolCall] | None:
        raw = getattr(message, "tool_calls", None)
        if not raw:
            return None
        result: list[ToolCall] = []
        for item in raw:
            try:
                function = getattr(item, "function", None)
                name = getattr(function, "name", None) if function is not None else None
                arguments = getattr(function, "arguments", None) if function is not None else None
                if not isinstance(arguments, str):
                    arguments = "{}" if arguments is None else str(arguments)
                try:
                    import json
                    parsed = json.loads(arguments)
                except (TypeError, ValueError):
                    parsed = {"raw": arguments}
                result.append(
                    ToolCall(
                        id=str(getattr(item, "id", "") or ""),
                        name=str(name or ""),
                        arguments=parsed if isinstance(parsed, dict) else {"value": parsed},
                    )
                )
            except (AttributeError, TypeError):
                continue
        return result or None

    @staticmethod
    def _usage(response: Any) -> dict[str, int] | None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return None
        if isinstance(usage, dict):
            return {str(k): int(v) for k, v in usage.items() if isinstance(v, (int, float))}
        if hasattr(usage, "model_dump"):
            data = usage.model_dump()
            return {str(k): int(v) for k, v in data.items() if isinstance(v, (int, float))}
        return None

    def _kwargs(self, temperature: float, max_tokens: int, kwargs: dict[str, Any]) -> dict[str, Any]:
        payload = dict(kwargs)
        payload.setdefault("temperature", temperature)
        payload.setdefault("max_tokens", max_tokens)
        if self._api_key:
            payload.setdefault("api_key", self._api_key)
        if self._api_base:
            payload.setdefault("api_base", self._api_base)
        return payload

    def chat_completion(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        response = self._litellm.completion(
            model=self._model_name,
            messages=self._messages(messages),
            tools=self._tools(tools),
            **self._kwargs(temperature, max_tokens, kwargs),
        )
        choice = response.choices[0]
        message = choice.message
        return LLMResponse(
            content=getattr(message, "content", None),
            tool_calls=self._tool_calls(message),
            finish_reason=getattr(choice, "finish_reason", None),
            usage=self._usage(response),
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
        response = self._litellm.completion(
            model=self._model_name,
            messages=self._messages(messages),
            tools=self._tools(tools),
            stream=True,
            **self._kwargs(temperature, max_tokens, kwargs),
        )
        for chunk in response:
            choice = chunk.choices[0] if getattr(chunk, "choices", None) else None
            if choice is None:
                continue
            delta = getattr(choice, "delta", None)
            content = getattr(delta, "content", None)
            finish = getattr(choice, "finish_reason", None)
            tool_calls = self._tool_calls(delta)
            yield StreamChunk(
                content=content,
                tool_calls=tool_calls,
                finish_reason=finish,
                is_final=finish is not None,
            )

    def get_available_models(self) -> list[dict[str, Any]]:
        return [
            {
                "id": self._model_name,
                "name": self._model_name,
                "provider": "litellm",
            }
        ]

    def validate_config(self) -> list[str]:
        return ["LiteLLM model is missing."] if not self._model_name else []
