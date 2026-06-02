"""
Context Window Management.

Handles intelligent context window management to prevent exceeding
the model's maximum context length. Implements auto-compaction
by summarizing older messages when approaching the limit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from nexus_agent.llm.base import LLMProvider, Message, Role

logger = logging.getLogger(__name__)

# Constants for context management
COMPACT_SUMMARY_MAX_CONTENT_LENGTH = 200
DEFAULT_MAX_TOKENS = 4096


@dataclass
class ContextStats:
    """Statistics about current context usage."""
    total_tokens: int
    max_tokens: int
    usage_percent: float
    message_count: int
    system_tokens: int
    user_tokens: int
    assistant_tokens: int
    tool_tokens: int


class ContextManager:
    """Manages context window to prevent overflow.

    When the conversation approaches the context limit, automatically
    summarizes older messages to free space while retaining important
    context. Inspired by opencode's auto-compact feature.
    """

    def __init__(
        self,
        provider: LLMProvider,
        compact_threshold: float = 0.85,
        min_recent_messages: int = 6,
    ):
        """Initialize context manager.

        Args:
            provider: LLM provider (for token counting).
            compact_threshold: Compact when usage exceeds this fraction.
            min_recent_messages: Always keep at least this many recent messages.
        """
        self.provider = provider
        self.compact_threshold = compact_threshold
        self.min_recent_messages = min_recent_messages
        try:
            self._max_tokens = int(provider.get_capabilities().max_context_length)
        except (AttributeError, ValueError, TypeError):
            self._max_tokens = DEFAULT_MAX_TOKENS

    def get_stats(self, messages: list[Message]) -> ContextStats:
        """Get detailed context usage statistics."""
        total = 0
        system_tokens = 0
        user_tokens = 0
        assistant_tokens = 0
        tool_tokens = 0

        for msg in messages:
            tokens_val = self.provider.count_tokens(msg.content or "")
            try:
                tokens = int(tokens_val)
            except (ValueError, TypeError):
                tokens = len(msg.content or "") // 4 or 1
            total += tokens

            match msg.role:
                case Role.SYSTEM:
                    system_tokens += tokens
                case Role.USER:
                    user_tokens += tokens
                case Role.ASSISTANT:
                    assistant_tokens += tokens
                case Role.TOOL:
                    tool_tokens += tokens

        return ContextStats(
            total_tokens=total,
            max_tokens=self._max_tokens,
            usage_percent=total / self._max_tokens if self._max_tokens > 0 else 0,
            message_count=len(messages),
            system_tokens=system_tokens,
            user_tokens=user_tokens,
            assistant_tokens=assistant_tokens,
            tool_tokens=tool_tokens,
        )

    def should_compact(self, messages: list[Message]) -> bool:
        """Check if the context should be compacted."""
        stats = self.get_stats(messages)
        return stats.usage_percent >= self.compact_threshold

    def compact(self, messages: list[Message]) -> list[Message]:
        """Compact the context by summarizing older messages.

        Strategy:
        1. Keep all system prompts intact
        2. Keep the most recent N messages intact
        3. Summarize everything in between into a condensed context message

        Returns:
            New message list with compacted history.
        """
        if len(messages) <= self.min_recent_messages + 1:
            return messages  # Nothing to compact

        stats = self.get_stats(messages)
        if stats.usage_percent < self.compact_threshold:
            return messages  # Not needed

        logger.info(
            f"Compacting context: {stats.usage_percent:.0%} usage, "
            f"{stats.message_count} messages"
        )

        # Separate system prompts, old messages, and recent messages
        system_msgs = [m for m in messages if m.role == Role.SYSTEM]
        non_system = [m for m in messages if m.role != Role.SYSTEM]

        if len(non_system) <= self.min_recent_messages:
            return messages

        # Keep recent messages intact
        recent = non_system[-self.min_recent_messages:]
        old = non_system[:-self.min_recent_messages]

        # Summarize old messages
        summary_parts: list[str] = []
        for msg in old:
            role = msg.role.value.upper()
            content = msg.content or ""
            if msg.tool_calls:
                tools_str = ", ".join(tc.name for tc in msg.tool_calls)
                content += f" [Called tools: {tools_str}]"
            if len(content) > COMPACT_SUMMARY_MAX_CONTENT_LENGTH:
                content = content[:COMPACT_SUMMARY_MAX_CONTENT_LENGTH] + "..."
            summary_parts.append(f"[{role}]: {content}")

        summary = (
            "[CONVERSATION HISTORY SUMMARY]\n"
            "The following is a condensed summary of earlier conversation:\n\n"
            + "\n".join(summary_parts)
        )

        summary_msg = Message(role=Role.USER, content=summary)

        compacted = system_msgs + [summary_msg] + recent

        new_stats = self.get_stats(compacted)
        logger.info(
            f"Compacted: {stats.message_count} → {len(compacted)} messages, "
            f"{stats.usage_percent:.0%} → {new_stats.usage_percent:.0%} usage"
        )

        return compacted

    def trim_tool_output(self, output: str, max_chars: int = 8000) -> str:
        """Trim tool output to prevent excessive context consumption.

        Large outputs (e.g., file contents, command outputs) are truncated
        intelligently to preserve the most useful information.
        """
        if len(output) <= max_chars:
            return output

        # Keep the beginning and end, truncate the middle
        head_size = int(max_chars * 0.7)
        tail_size = int(max_chars * 0.25)

        head = output[:head_size]
        tail = output[-tail_size:]
        omitted = len(output) - head_size - tail_size

        return (
            f"{head}\n\n"
            f"[... {omitted} characters omitted ...]\n\n"
            f"{tail}"
        )
