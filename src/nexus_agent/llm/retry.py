"""
Provider resilience — retry, backoff, and rate-limit handling.

Wraps any `LLMProvider.chat_completion` call with exponential-backoff retry
on transient errors (timeouts, 5xx, 429). Honors `Retry-After` headers when
the server provides them. The policy is a per-call `RetryPolicy` dataclass
so callers (and configs) can tune it per provider.

The fallback chain (`ProviderFactory.create_with_fallback`) builds on top of
this: it tries the primary provider first, and on hard failure walks the
configured list of fallback providers until one succeeds.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

import httpx

from nexus_agent.llm.base import LLMProvider, LLMResponse, Message, ToolDefinition

logger = logging.getLogger(__name__)

T = TypeVar("T")


# HTTP status codes that should trigger a retry.
# 408 Request Timeout, 409 Conflict (some), 425 Too Early, 429 Rate Limited,
# 500/502/503/504 transient server errors.
RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


@dataclass
class RetryPolicy:
    """Per-call retry policy.

    Attributes:
        max_attempts: Maximum number of attempts (1 = no retry). Default 3.
        initial_backoff_s: Backoff before the first retry. Default 1.0s.
        max_backoff_s: Cap on backoff. Default 30.0s.
        backoff_multiplier: Multiplier per retry. Default 2.0.
        jitter: If True, add up to ±25% random jitter. Default True.
        retry_on_status: HTTP status codes that trigger a retry.
    """

    max_attempts: int = 3
    initial_backoff_s: float = 1.0
    max_backoff_s: float = 30.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    retry_on_status: frozenset[int] = field(default_factory=lambda: RETRYABLE_STATUS_CODES)

    def backoff_for(self, attempt: int) -> float:
        """Return seconds to sleep before retry `attempt` (0-indexed)."""
        delay = min(self.initial_backoff_s * (self.backoff_multiplier ** attempt), self.max_backoff_s)
        if self.jitter:
            delay = delay * (0.75 + random.random() * 0.5)
        return delay


@dataclass
class RetryStats:
    """Outcome of a retry-protected call (for observability + tests)."""

    attempts: int
    total_sleep_s: float
    fallback_used: str | None = None
    last_status: int | None = None
    last_error: str | None = None


def _is_retryable(exc: BaseException, policy: RetryPolicy) -> bool:
    """Return True if `exc` represents a transient error worth retrying."""
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.NetworkError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in policy.retry_on_status
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    return False


def _retry_after_seconds(exc: BaseException) -> float | None:
    """Return a server-suggested retry delay (in seconds) if present."""
    if isinstance(exc, httpx.HTTPStatusError):
        retry_after = exc.response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                # Could be an HTTP-date — not worth parsing, fall through.
                return None
    return None


def with_retry(
    func: Callable[..., T],
    policy: RetryPolicy | None = None,
    *,
    on_retry: Callable[[int, float, BaseException], None] | None = None,
) -> tuple[T, RetryStats]:
    """Run `func` under a retry policy.

    Returns:
        Tuple of (result, stats). Raises the last exception if all attempts fail.
    """
    policy = policy or RetryPolicy()
    stats = RetryStats(attempts=0, total_sleep_s=0.0)
    last_exc: BaseException | None = None
    for attempt in range(policy.max_attempts):
        stats.attempts = attempt + 1
        try:
            return func(), stats
        except (httpx.HTTPError, ConnectionError, TimeoutError, OSError) as e:
            last_exc = e
            if attempt + 1 >= policy.max_attempts or not _is_retryable(e, policy):
                stats.last_error = f"{type(e).__name__}: {e}"
                if isinstance(e, httpx.HTTPStatusError):
                    stats.last_status = e.response.status_code
                raise
            server_suggested = _retry_after_seconds(e)
            delay = server_suggested if server_suggested is not None else policy.backoff_for(attempt)
            stats.total_sleep_s += delay
            if isinstance(e, httpx.HTTPStatusError):
                stats.last_status = e.response.status_code
            logger.warning(
                f"Retryable error (attempt {attempt + 1}/{policy.max_attempts}): "
                f"{type(e).__name__}: {e} — sleeping {delay:.2f}s"
            )
            if on_retry:
                try:
                    on_retry(attempt + 1, delay, e)
                except (OSError, ValueError, TypeError, RuntimeError) as cb_err:
                    logger.debug(f"on_retry callback raised: {cb_err}")
            time.sleep(delay)
    # Defensive — should be unreachable.
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("with_retry exited without result or exception")


def chat_with_retry(
    provider: LLMProvider,
    messages: list[Message],
    *,
    tools: list[ToolDefinition] | None = None,
    temperature: float = 0.1,
    max_tokens: int = 4096,
    policy: RetryPolicy | None = None,
    stream: bool = False,
    **kwargs: Any,
) -> tuple[LLMResponse | Any, RetryStats]:
    """Call `provider.chat_completion` (or streaming variant) under a retry policy.

    When `stream=True` we don't use `with_retry` because the caller wants the
    raw iterator. Callers can still wrap their own iteration in `with_retry`
    for partial-output recovery if needed.

    Returns:
        For non-streaming: (LLMResponse, stats).
        For streaming: (Iterator[StreamChunk], stats with attempts=1).
    """
    if stream:
        # No retry on streaming — caller has the iterator.
        return provider.chat_completion_stream(
            messages, tools, temperature, max_tokens, **kwargs
        ), RetryStats(attempts=1, total_sleep_s=0.0)
    policy = policy or RetryPolicy()
    return with_retry(
        lambda: provider.chat_completion(messages, tools, temperature, max_tokens, **kwargs),
        policy=policy,
    )
