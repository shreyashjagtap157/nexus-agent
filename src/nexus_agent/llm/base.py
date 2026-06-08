"""
Abstract LLM provider interface.

Defines the standardized interface that all LLM providers must implement,
following the provider abstraction pattern from opencode. This allows
seamless switching between local models and cloud providers.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(str, Enum):
    """Message roles in a conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ToolDefinition:
    """Definition of a tool the LLM can call.

    Follows the OpenAI function calling schema for maximum compatibility.
    """
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    required_params: list[str] = field(default_factory=list)

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI-compatible tool definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required_params,
                },
            },
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "required_params": self.required_params,
        }


@dataclass
class ToolCall:
    """A tool call requested by the LLM."""
    id: str
    name: str
    arguments: dict[str, Any]

    @classmethod
    def from_openai_format(cls, tool_call: dict[str, Any]) -> ToolCall:
        """Parse from OpenAI-format tool call."""
        func = tool_call.get("function", {})
        args = func.get("arguments", "{}")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {"raw": args}
        return cls(
            id=tool_call.get("id", ""),
            name=func.get("name", ""),
            arguments=args,
        )


@dataclass
class Message:
    """A message in a conversation."""
    role: Role
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI-compatible message format."""
        msg: dict[str, Any] = {"role": self.role.value}

        if self.content is not None:
            msg["content"] = self.content

        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, default=str),
                    },
                }
                for tc in self.tool_calls
            ]

        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id

        if self.name:
            msg["name"] = self.name

        return msg


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    finish_reason: str | None = None
    usage: dict[str, int] | None = None
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        """Check if the response contains tool calls."""
        return bool(self.tool_calls)


@dataclass
class StreamChunk:
    """A chunk of a streaming response."""
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    finish_reason: str | None = None
    is_final: bool = False


@dataclass
class ProviderCapabilities:
    """Capabilities of an LLM provider."""
    supports_tool_calling: bool = False
    supports_vision: bool = False
    supports_streaming: bool = True
    supports_system_message: bool = True
    supports_parallel_tool_calls: bool = False
    max_context_length: int = 4096
    max_output_tokens: int = 4096
    supports_effort_levels: bool = False
    supported_effort_levels: list[str] = field(default_factory=list)


class LLMProvider(ABC):
    """Abstract base class for all LLM providers.

    All providers (local engine, OpenAI, Anthropic, etc.) implement this
    interface, enabling seamless provider switching. Inspired by opencode's
    provider-agnostic architecture.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'local', 'openai', 'anthropic')."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Currently active model name."""
        ...

    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        """Get provider capabilities."""
        ...

    @abstractmethod
    def chat_completion(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a chat completion (synchronous).

        Args:
            messages: Conversation history.
            tools: Available tools for function calling.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.

        Returns:
            LLMResponse with content and/or tool calls.
        """
        ...

    @abstractmethod
    def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Iterator[StreamChunk]:
        """Generate a streaming chat completion.

        Yields StreamChunk objects as tokens are generated.
        """
        ...

    @abstractmethod
    def get_available_models(self) -> list[dict[str, Any]]:
        """List available models for this provider."""
        ...

    def count_tokens(self, text: str) -> int:
        """Estimate token count for a text string.

        Default implementation uses a rough heuristic. Providers can
        override with exact tokenizer counts.
        """
        # Rough estimate: ~4 chars per token for English text
        return len(text) // 4

    def count_message_tokens(self, messages: list[Message]) -> int:
        """Estimate total tokens in a message list."""
        total = 0
        for msg in messages:
            if msg.content:
                total += self.count_tokens(msg.content)
            # Account for message structure overhead
            total += 4  # role, formatting tokens
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    try:
                        args_str = json.dumps(tc.arguments)
                    except (TypeError, ValueError):
                        args_str = str(tc.arguments)
                    total += self.count_tokens(args_str) + 10
        return total

    def validate_config(self) -> list[str]:
        """Validate provider configuration. Returns list of error messages."""
        return []

    @property
    def is_loaded(self) -> bool:
        """Whether the provider is fully loaded and ready.
        Cloud providers are always considered loaded once created;
        local providers override this to reflect actual engine state.
        """
        return True

    def close(self) -> None:
        """Clean up resources. Override in providers that need cleanup."""
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} model={self.model_name}>"
