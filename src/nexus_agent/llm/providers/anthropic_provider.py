"""Anthropic Provider implementation."""

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
    Role,
    StreamChunk,
    ToolCall,
    ToolDefinition,
)
from nexus_agent.llm.retry import RetryPolicy, with_retry

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic API provider (Claude)."""

    def __init__(self, config: dict[str, Any]):
        """Initialize Anthropic provider.

        Args:
            config: Config dict.
        """
        self._config = config
        self._api_key = config.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
        self._model_name = config.get("model") or "claude-3-5-sonnet-latest"
        self._api_url = config.get("api_url") or "https://api.anthropic.com/v1/messages"

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def model_name(self) -> str:
        return self._model_name

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tool_calling=True,
            supports_vision=True,
            supports_streaming=True,
            supports_system_message=True,  # Passed via top-level parameter
            supports_parallel_tool_calls=True,
            max_context_length=200000,
            max_output_tokens=8192,
        )

    def _get_headers(self) -> dict[str, str]:
        if not self._api_key:
            raise ValueError("Anthropic API key is missing. Set it in config or via ANTHROPIC_API_KEY env var.")
        return {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def _format_messages_and_system(
        self, messages: list[Message]
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Convert standard Messages to Anthropic format and extract system prompt."""
        system_parts: list[str] = []
        formatted = []

        for msg in messages:
            if msg.role == Role.SYSTEM:
                # System prompt goes to top level in Anthropic API
                if msg.content:
                    system_parts.append(msg.content)
                continue

            # Standard user / assistant messages
            if msg.role == Role.USER:
                if msg.content is None:
                    continue
                formatted.append({"role": "user", "content": msg.content})
            elif msg.role == Role.ASSISTANT:
                content_blocks: list[dict[str, Any]] = []
                if msg.content:
                    content_blocks.append({"type": "text", "text": msg.content})

                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        })
                formatted.append({"role": "assistant", "content": content_blocks})

            elif msg.role == Role.TOOL:
                # Tool responses in Anthropic go into user block with type tool_result
                if not msg.tool_call_id:
                    logger.warning(f"Tool message missing tool_call_id: {msg.name}")
                formatted.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id or "",
                            "content": msg.content or "",
                        }
                    ]
                })

        system_content = "\n\n".join(system_parts) if system_parts else None
        return formatted, system_content

    def _format_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        formatted = []
        for t in tools:
            formatted.append({
                "name": t.name,
                "description": t.description,
                "input_schema": {
                    "type": "object",
                    "properties": t.parameters,
                    "required": t.required_params,
                }
            })
        return formatted

    def _prepare_payload(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> dict[str, Any]:
        anthropic_messages, system_prompt = self._format_messages_and_system(messages)

        payload: dict[str, Any] = {
            "model": self._model_name,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }

        if system_prompt:
            payload["system"] = system_prompt

        if tools:
            payload["tools"] = self._format_tools(tools)

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

        policy = RetryPolicy(
            max_attempts=3,
            initial_backoff_s=1.0,
            max_backoff_s=30.0,
        )

        def _do_request() -> LLMResponse:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    self._api_url,
                    headers=self._get_headers(),
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()

            # Parse Anthropic output
            content_blocks = result.get("content", [])
            text_content = ""
            tool_calls = None

            for block in content_blocks:
                if block.get("type") == "text":
                    text_content += block.get("text", "")
                elif block.get("type") == "tool_use":
                    if tool_calls is None:
                        tool_calls = []
                    tool_calls.append(ToolCall(
                        id=block["id"],
                        name=block["name"],
                        arguments=block["input"],
                    ))

            stop_reason = result.get("stop_reason")
            finish_reason = "stop" if stop_reason == "end_turn" else stop_reason

            return LLMResponse(
                content=text_content or None,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage={
                    "prompt_tokens": result.get("usage", {}).get("input_tokens", 0),
                    "completion_tokens": result.get("usage", {}).get("output_tokens", 0),
                    "total_tokens": result.get("usage", {}).get("input_tokens", 0) + result.get("usage", {}).get("output_tokens", 0),
                },
                model=self._model_name,
            )

        response, stats = with_retry(_do_request, policy=policy)
        return response

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
        accumulated_tool_calls: dict[str, dict[str, Any]] = {}

        with httpx.Client(timeout=60.0) as client:
            with client.stream("POST", self._api_url, headers=headers, json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        try:
                            event = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        event_type = event.get("type")
                        if event_type == "content_block_start":
                            block = event.get("content_block", {})
                            if block.get("type") == "tool_use":
                                tc_id = block["id"]
                                accumulated_tool_calls[tc_id] = {
                                    "id": tc_id,
                                    "name": block["name"],
                                    "input_str": "",
                                }
                        elif event_type == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield StreamChunk(content=delta.get("text"))
                            elif delta.get("type") == "input_json_delta":
                                # Accumulate JSON string
                                # Find active tool block
                                for tc in accumulated_tool_calls.values():
                                    tc["input_str"] += delta.get("partial_json", "")
                        elif event_type == "content_block_stop":
                            pass
                        elif event_type == "message_delta":
                            pass
                        elif event_type == "message_stop":
                            # Finalize all accumulated tool calls
                            chunk_tool_calls = []
                            for tc in accumulated_tool_calls.values():
                                try:
                                    args = json.loads(tc["input_str"])
                                except json.JSONDecodeError:
                                    args = {"raw": tc["input_str"]}
                                chunk_tool_calls.append(ToolCall(
                                    id=tc["id"],
                                    name=tc["name"],
                                    arguments=args,
                                ))

                            accumulated_tool_calls.clear()

                            yield StreamChunk(
                                tool_calls=chunk_tool_calls if chunk_tool_calls else None,
                                finish_reason="stop",
                                is_final=True,
                            )

    def get_available_models(self) -> list[dict[str, Any]]:
        return [
            {"id": "claude-3-5-sonnet-latest", "name": "Claude 3.5 Sonnet (Default)", "provider": "anthropic"},
            {"id": "claude-3-5-haiku-latest", "name": "Claude 3.5 Haiku (Fast)", "provider": "anthropic"},
            {"id": "claude-3-opus-latest", "name": "Claude 3 Opus (Advanced)", "provider": "anthropic"},
        ]

    def validate_config(self) -> list[str]:
        errors = []
        if not self._api_key:
            errors.append("Anthropic API key (ANTHROPIC_API_KEY) is not set")
        return errors
