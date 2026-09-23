"""
Retry utility with exponential backoff for LLM provider calls.

Wraps provider chat_completion and chat_completion_stream methods
with automatic retry on transient failures (rate limits, timeouts,
connection errors). This addresses the #1 audit finding: provider
resilience score 3/10.
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any, TypeVar

from nexus_agent.llm.base import LLMProvider, LLMResponse, Message, StreamChunk, ToolDefinition

logger = logging.getLogger(__name__)

T = TypeVar("T")

# HTTP status codes that are considered retryable
RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({408, 425, 429, 500, 502, 503, 504})


@dataclass
class RetryPolicy:
    """Configuration for provider retry behavior."""
    max_attempts: int = 3
    initial_backoff_s: float = 1.0
    max_backoff_s: float = 30.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    retry_on_status: frozenset[int] = field(default_factory=lambda: RETRYABLE_STATUS_CODES)

    def backoff_for(self, attempt_index: int) -> float:
        """Compute the backoff delay for the given attempt index (0-based).

        The delay grows exponentially from ``initial_backoff_s`` up to
        ``max_backoff_s``, then caps.  If ``jitter`` is enabled, the
        returned delay is randomised to ±25% to avoid thundering-herd
        effects.
        """
        if attempt_index < 0:
            attempt_index = 0
        delay = self.initial_backoff_s * (self.backoff_multiplier ** attempt_index)
        delay = min(delay, self.max_backoff_s)
        if self.jitter:
            # ±25% jitter
            delay = delay * (0.75 + random.random() * 0.5)
        return delay


@dataclass
class RetryStats:
    """Statistics collected during a retry loop."""
    attempts: int
    total_sleep_s: float
    last_error: BaseException | None = None


# Default policy for cloud providers
DEFAULT_CLOUD_POLICY = RetryPolicy(
    max_attempts=3,
    initial_backoff_s=1.0,
    max_backoff_s=30.0,
    backoff_multiplier=2.0,
)

# Aggressive policy for rate-limited providers
RATE_LIMIT_POLICY = RetryPolicy(
    max_attempts=5,
    initial_backoff_s=2.0,
    max_backoff_s=60.0,
    backoff_multiplier=2.0,
)


def _is_retryable(exc: BaseException, policy: RetryPolicy) -> bool:
    """Check if an exception is transient and worth retrying."""
    import httpx

    # httpx.HTTPStatusError carries the actual response
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in policy.retry_on_status

    # Network / timeout errors from httpx
    if isinstance(exc, (
        httpx.TimeoutException,
        httpx.ConnectError,
        httpx.NetworkError,
        httpx.RemoteProtocolError,
    )):
        return True

    # Standard Python exceptions
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return True

    # String-based matching as fallback (e.g. custom proxy errors)
    err_str = str(exc).lower()
    if any(code in err_str for code in ("429", "500", "502", "503", "529")):
        return True
    if "rate" in err_str or "too many requests" in err_str:
        return True
    if "overloaded" in err_str or "capacity" in err_str or "unavailable" in err_str:
        return True
    if "timeout" in err_str or "timed out" in err_str:
        return True
    if "connection" in err_str and ("refused" in err_str or "reset" in err_str or "error" in err_str):
        return True
    if "connect" in err_str and "error" in err_str:
        return True
    return False


def _retry_after_seconds(exc: BaseException) -> float | None:
    """Try to extract Retry-After header value from exception."""
    import httpx
    if not isinstance(exc, httpx.HTTPStatusError):
        return None
    resp = getattr(exc, "response", None)
    if resp is None:
        return None
    headers = getattr(resp, "headers", {})
    retry_after = headers.get("retry-after") or headers.get("Retry-After")
    if retry_after is None:
        return None
    try:
        return float(retry_after)
    except (ValueError, TypeError):
        # If it's an HTTP-date (e.g. "Wed, 21 Oct 2026 07:28:00 GMT"),
        # we can't parse it easily. Return None to fall back to backoff.
        return None


def with_retry(
    fn: Callable[[], T],
    policy: RetryPolicy | None = None,
    provider_name: str = "unknown",
    on_retry: Callable[[int, float, BaseException], None] | None = None,
) -> tuple[T, RetryStats]:
    """Execute fn with retry and exponential backoff.

    Retries on transient network errors and rate-limit responses.
    Raises the last exception if all attempts fail.

    Args:
        fn: The callable to execute.
        policy: RetryPolicy (uses DEFAULT_CLOUD_POLICY if None).
        provider_name: Label for log messages.
        on_retry: Optional callback ``on_retry(attempt, delay, exc)``
                  fired *before* sleeping.

    Returns:
        Tuple of (result, RetryStats).
    """
    if policy is None:
        policy = DEFAULT_CLOUD_POLICY

    last_exc: BaseException | None = None
    total_sleep_s = 0.0

    for attempt in range(1, policy.max_attempts + 1):
        try:
            result = fn()
            return result, RetryStats(
                attempts=attempt,
                total_sleep_s=total_sleep_s,
                last_error=last_exc,
            )
        except KeyboardInterrupt:
            raise
        except Exception as e:
            last_exc = e
            if attempt >= policy.max_attempts:
                break
            if not _is_retryable(e, policy):
                logger.debug(f"[{provider_name}] Non-retryable error: {e}")
                break
            # Use Retry-After header if available
            retry_after = _retry_after_seconds(e)
            delay: float
            if retry_after is not None and retry_after >= 0:
                delay = min(retry_after, policy.max_backoff_s)
            else:
                delay = policy.backoff_for(attempt - 1)
            logger.warning(
                f"[{provider_name}] Attempt {attempt}/{policy.max_attempts} "
                f"failed: {type(e).__name__}: {e}. "
                f"Retrying in {delay:.1f}s..."
            )
            if on_retry is not None:
                try:
                    on_retry(attempt, delay, e)
                except Exception as cb_exc:
                    logger.warning(f"[{provider_name}] on_retry callback failed: {cb_exc}")
            time.sleep(delay)
            total_sleep_s += delay

    # All attempts exhausted
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("with_retry: empty callable or unknown state")


class RetryProvider(LLMProvider):
    """Wraps an LLMProvider with automatic retry on transient failures.

    Delegates all calls to the inner provider, retrying on:
    - HTTP 429 (rate limit)
    - HTTP 5xx (server errors)
    - Connection/timeout errors
    """

    def __init__(
        self,
        inner: LLMProvider,
        policy: RetryPolicy | None = None,
    ):
        self._inner = inner
        self._policy = policy or DEFAULT_CLOUD_POLICY

    @property
    def name(self) -> str:
        return self._inner.name

    @property
    def model_name(self) -> str:
        return self._inner.model_name

    @property
    def is_loaded(self) -> bool:
        return self._inner.is_loaded

    def get_capabilities(self):
        return self._inner.get_capabilities()

    def chat_completion(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        result, _stats = with_retry(
            lambda: self._inner.chat_completion(messages, tools, temperature, max_tokens, **kwargs),
            policy=self._policy,
            provider_name=self.name,
        )
        return result

    def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Iterator[StreamChunk]:
        result, _stats = with_retry(
            lambda: self._inner.chat_completion_stream(messages, tools, temperature, max_tokens, **kwargs),
            policy=self._policy,
            provider_name=self.name,
        )
        return result

    def get_available_models(self) -> list[dict[str, Any]]:
        result, _stats = with_retry(
            lambda: self._inner.get_available_models(),
            policy=self._policy,
            provider_name=self.name,
        )
        return result

    def count_tokens(self, text: str) -> int:
        return self._inner.count_tokens(text)

    def count_message_tokens(self, messages: list[Message]) -> int:
        return self._inner.count_message_tokens(messages)

    def validate_config(self) -> list[str]:
        return self._inner.validate_config()

    def close(self) -> None:
        self._inner.close()

    def __repr__(self) -> str:
        return f"<RetryProvider wrapping={self._inner!r}>"


def chat_with_retry(
    provider: LLMProvider,
    messages: list[Message],
    tools: list[ToolDefinition] | None = None,
    temperature: float = 0.1,
    max_tokens: int = 4096,
    stream: bool = False,
    policy: RetryPolicy | None = None,
    **kwargs: Any,
) -> tuple[LLMResponse | Iterator[StreamChunk], RetryStats]:
    """Call ``chat_completion`` or ``chat_completion_stream`` with retry.

    Args:
        provider: The LLM provider instance.
        messages: Conversation messages.
        tools: Optional tool definitions.
        temperature: Sampling temperature.
        max_tokens: Max tokens to generate.
        stream: If True, calls ``chat_completion_stream``.
        policy: RetryPolicy (defaults to DEFAULT_CLOUD_POLICY).
        **kwargs: Extra keyword arguments forwarded to the provider.

    Returns:
        Tuple of (LLMResponse or Iterator[StreamChunk], RetryStats).
    """
    if stream:
        result, stats = with_retry(
            lambda: provider.chat_completion_stream(messages, tools, temperature, max_tokens, **kwargs),
            policy=policy,
            provider_name=provider.name,
        )
        return result, stats
    else:
        result, stats = with_retry(
            lambda: provider.chat_completion(messages, tools, temperature, max_tokens, **kwargs),
            policy=policy,
            provider_name=provider.name,
        )
        return result, stats
