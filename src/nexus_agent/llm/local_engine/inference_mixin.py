from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from typing import Any

from nexus_agent.llm.base import (
    LLMResponse,
    Message,
    StreamChunk,
    ToolDefinition,
)
from nexus_agent.llm.base import (
    ToolCall as BaseToolCall,
)

logger = logging.getLogger(__name__)


class InferenceMixin:
    _llm: Any
    _model_name_str: str

    def _ensure_loaded(self) -> None:
        ...

    def chat_completion(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        self._ensure_loaded()

        formatted_messages = []
        for msg in messages:
            formatted_messages.append(msg.to_openai_format())

        kwargs_req: dict[str, Any] = {"messages": formatted_messages}
        if tools:
            kwargs_req["tools"] = [t.to_openai_format() for t in tools]

        try:
            result = self._llm.create_chat_completion(
                **kwargs_req,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                **kwargs,
            )
        except (ValueError, RuntimeError, KeyError) as e:
            logger.error(f"Local model inference error: {e}")
            raise RuntimeError(f"Local model inference failed: {e}") from e

        choice = (result.get("choices") or [{}])[0]
        message = choice.get("message", {})

        tool_calls = None
        raw_tool_calls = message.get("tool_calls")
        if raw_tool_calls:
            tool_calls = []
            for tc in raw_tool_calls:
                tool_calls.append(BaseToolCall.from_openai_format(tc))

        return LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason"),
            usage=result.get("usage"),
            model=self._model_name_str,
        )

    def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Iterator[StreamChunk]:
        self._ensure_loaded()

        formatted_messages = []
        for msg in messages:
            formatted_messages.append(msg.to_openai_format())

        kwargs_req: dict[str, Any] = {"messages": formatted_messages}
        if tools:
            kwargs_req["tools"] = [t.to_openai_format() for t in tools]

        try:
            stream = self._llm.create_chat_completion(
                **kwargs_req,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs,
            )
        except (ValueError, RuntimeError, KeyError) as e:
            logger.error(f"Local model streaming error: {e}")
            raise RuntimeError(f"Local model streaming failed: {e}") from e

        accumulated_tool_calls: dict[int, dict[str, Any]] = {}

        for chunk in stream:
            choice = (chunk.get("choices") or [{}])[0]
            delta = choice.get("delta", {})
            finish = choice.get("finish_reason")

            content = delta.get("content")
            raw_tc = delta.get("tool_calls")
            chunk_tool_calls = None

            if raw_tc:
                for tc_delta in raw_tc:
                    idx = tc_delta.get("index", 0)
                    if idx not in accumulated_tool_calls:
                        accumulated_tool_calls[idx] = {
                            "id": tc_delta.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                            "function": {"name": "", "arguments": ""},
                        }
                    acc = accumulated_tool_calls[idx]
                    func = tc_delta.get("function", {})
                    if "name" in func:
                        acc["function"]["name"] += func["name"]
                    if "arguments" in func:
                        acc["function"]["arguments"] += func["arguments"]

            if finish and finish == "tool_calls" and accumulated_tool_calls:
                chunk_tool_calls = [
                    BaseToolCall.from_openai_format(tc)
                    for tc in accumulated_tool_calls.values()
                ]

            yield StreamChunk(
                content=content,
                tool_calls=chunk_tool_calls,
                finish_reason=finish,
                is_final=finish is not None,
            )
