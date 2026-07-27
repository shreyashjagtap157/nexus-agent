"""AWS Bedrock Provider implementation."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from typing import Any

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

logger = logging.getLogger(__name__)

try:
    import boto3
    BEDROCK_AVAILABLE = True
except ImportError:
    BEDROCK_AVAILABLE = False


class AWSBedrockProvider(LLMProvider):
    """AWS Bedrock provider."""

    def __init__(self, config: dict[str, Any]):
        """Initialize AWS Bedrock provider.

        Args:
            config: Config dict.
        """
        self._config = config
        self._model_name = config.get("model") or "anthropic.claude-3-5-sonnet-20241022-v2:0"
        self._region = config.get("region") or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"

        self._client = None
        if BEDROCK_AVAILABLE:
            try:
                session = boto3.Session(
                    region_name=self._region,
                )
                self._client = session.client("bedrock-runtime")
            except (ValueError, OSError, RuntimeError) as e:
                logger.warning(f"Failed to initialize AWS Bedrock client: {e}")

    @property
    def name(self) -> str:
        return "bedrock"

    @property
    def model_name(self) -> str:
        return self._model_name

    def get_capabilities(self) -> ProviderCapabilities:
        # Bedrock models (like Claude) support tools, vision, streaming
        return ProviderCapabilities(
            supports_tool_calling=True,
            supports_vision=True,
            supports_streaming=True,
            supports_system_message=True,
            supports_parallel_tool_calls=True,
            max_context_length=200000,
            max_output_tokens=4096,
        )

    def _prepare_converse_arguments(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Convert standard Messages to Bedrock Converse API parameters."""
        bedrock_messages = []
        system_prompts = []

        for msg in messages:
            if msg.role == Role.SYSTEM:
                if msg.content:
                    system_prompts.append({"text": msg.content})
                continue

            content_blocks = []
            if msg.content:
                content_blocks.append({"text": msg.content})

            if msg.tool_calls:
                for tc in msg.tool_calls:
                    content_blocks.append({
                        "toolUse": {
                            "toolUseId": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        }
                    })

            if msg.role == Role.TOOL:
                # Tool responses go to a user block with toolResult in Bedrock Converse API
                bedrock_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "toolResult": {
                                "toolUseId": msg.tool_call_id or "",
                                "content": [{"text": msg.content or ""}],
                                "status": "success",
                            }
                        }
                    ]
                })
            else:
                role_map = {Role.USER: "user", Role.ASSISTANT: "assistant"}
                bedrock_messages.append({
                    "role": role_map.get(msg.role, "user"),
                    "content": content_blocks
                })

        converse_args: dict[str, Any] = {
            "modelId": self._model_name,
            "messages": bedrock_messages,
            "inferenceConfig": {
                "temperature": temperature,
                "maxTokens": max_tokens,
            }
        }

        if system_prompts:
            converse_args["system"] = system_prompts

        if tools:
            bedrock_tools = []
            for t in tools:
                bedrock_tools.append({
                    "toolSpec": {
                        "name": t.name,
                        "description": t.description,
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": t.parameters,
                                "required": t.required_params,
                            }
                        }
                    }
                })
            converse_args["toolConfig"] = {"tools": bedrock_tools}

        return converse_args

    def chat_completion(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        if not BEDROCK_AVAILABLE:
            raise RuntimeError("boto3 package not installed. Run pip install boto3 to use AWS Bedrock.")
        if not self._client:
            raise ValueError("AWS Bedrock client is not initialized. Check AWS credentials.")

        args = self._prepare_converse_arguments(messages, tools, temperature, max_tokens)
        args.update(kwargs)

        response = self._client.converse(**args)
        output_msg = response.get("output", {}).get("message", {})
        content_blocks = output_msg.get("content", [])

        text_content = ""
        tool_calls = None

        for block in content_blocks:
            if "text" in block:
                text_content += block["text"]
            elif "toolUse" in block:
                if tool_calls is None:
                    tool_calls = []
                tu = block["toolUse"]
                tool_calls.append(ToolCall(
                    id=tu["toolUseId"],
                    name=tu["name"],
                    arguments=tu["input"],
                ))

        stop_reason = response.get("stopReason")
        finish_reason = "stop" if stop_reason == "end_turn" else stop_reason

        return LLMResponse(
            content=text_content or None,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage={
                "prompt_tokens": response.get("usage", {}).get("inputTokens", 0),
                "completion_tokens": response.get("usage", {}).get("outputTokens", 0),
                "total_tokens": response.get("usage", {}).get("totalTokens", 0),
            },
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
        if not BEDROCK_AVAILABLE:
            raise RuntimeError("boto3 package not installed. Run pip install boto3 to use AWS Bedrock.")
        if not self._client:
            raise ValueError("AWS Bedrock client is not initialized. Check AWS credentials.")

        args = self._prepare_converse_arguments(messages, tools, temperature, max_tokens)
        args.update(kwargs)

        response = self._client.converse_stream(**args)
        stream = response.get("stream", [])

        accumulated_tool_calls: dict[str, dict[str, Any]] = {}

        for event in stream:
            if "contentBlockStart" in event:
                block = event["contentBlockStart"].get("start", {})
                if "toolUse" in block:
                    tu = block["toolUse"]
                    accumulated_tool_calls[tu["toolUseId"]] = {
                        "id": tu["toolUseId"],
                        "name": tu["name"],
                        "input_str": "",
                    }
            elif "contentBlockDelta" in event:
                delta = event["contentBlockDelta"].get("delta", {})
                if "text" in delta:
                    yield StreamChunk(content=delta["text"])
                elif "toolUse" in delta:
                    # Bedrock toolUse JSON chunk
                    tu_delta = delta["toolUse"]
                    for tc in accumulated_tool_calls.values():
                        tc["input_str"] += tu_delta.get("input", "")
            elif "messageStop" in event:
                stop_reason = event["messageStop"].get("stopReason")
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
                    finish_reason=stop_reason,
                    is_final=True,
                )

    def get_available_models(self) -> list[dict[str, Any]]:
        return [
            {"id": "anthropic.claude-3-5-sonnet-20241022-v2:0", "name": "Claude 3.5 Sonnet (AWS Bedrock)", "provider": "bedrock"},
            {"id": "amazon.nova-pro-v1:0", "name": "Amazon Nova Pro", "provider": "bedrock"},
            {"id": "amazon.nova-lite-v1:0", "name": "Amazon Nova Lite", "provider": "bedrock"},
        ]

    def validate_config(self) -> list[str]:
        errors = []
        if not BEDROCK_AVAILABLE:
            errors.append("boto3 package not installed (run pip install boto3)")
        if not self._client:
            errors.append("AWS Bedrock client is not initialized. Check AWS credentials.")
        return errors
