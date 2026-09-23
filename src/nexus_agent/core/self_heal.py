"""
Self-Healing Execution Engine — Retry orchestration with intelligent error diagnosis.

Wraps tool execution in a retry-with-diagnosis loop, enabling the agent to
automatically recover from transient failures and feed error context back
to the LLM for corrective re-invocation.

Features:
- Error classification (transient, semantic, fatal)
- Exponential backoff with configurable retries
- Timeout recovery with per-tool limits
- Structured diagnosis prompt generation for LLM correction
- Full telemetry event emission for each retry attempt
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class FailureType(str, Enum):
    """Classification of tool execution failures."""
    TRANSIENT = "transient"    # Network, timeout, resource busy → retry directly
    SEMANTIC = "semantic"      # Wrong arguments, bad path → ask LLM to re-plan
    FATAL = "fatal"            # Permission denied, missing dependency → report to user
    UNKNOWN = "unknown"        # Unclassified error


@dataclass
class RetryAttempt:
    """Record of a single retry attempt."""
    attempt_number: int
    tool_name: str
    arguments: dict[str, Any]
    error_message: str
    failure_type: FailureType
    duration_ms: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class HealingResult:
    """Result of self-healing execution."""
    success: bool
    final_output: str
    attempts: list[RetryAttempt] = field(default_factory=list)
    total_retries: int = 0
    healed: bool = False       # True if succeeded after at least one failure
    failure_type: FailureType | None = None
    diagnosis: str | None = None


# --------------------------------------------------------------------------- #
#  Error classification heuristics                                             #
# --------------------------------------------------------------------------- #

# Patterns that indicate transient (retryable) errors
_TRANSIENT_PATTERNS: tuple[str, ...] = (
    "timed out", "timeout", "connection refused", "connection reset",
    "resource temporarily unavailable", "try again", "busy",
    "rate limit", "too many requests", "429", "503", "502",
    "temporary failure", "network unreachable", "host unreachable",
    "broken pipe", "eof", "incomplete read",
)

# Patterns that indicate semantic (re-plannable) errors
_SEMANTIC_PATTERNS: tuple[str, ...] = (
    "no such file", "file not found", "not found", "does not exist",
    "invalid argument", "invalid parameter", "invalid path",
    "syntax error", "parse error", "unexpected token",
    "type error", "name error", "attribute error",
    "missing required", "expected", "unknown tool",
    "no match found", "no results",
)

# Patterns that indicate fatal (non-recoverable) errors
_FATAL_PATTERNS: tuple[str, ...] = (
    "permission denied", "access denied", "forbidden",
    "authentication failed", "unauthorized", "401", "403",
    "not installed", "command not found", "no such command",
    "out of memory", "disk full", "quota exceeded",
    "execution denied", "blocked",
)


class FailureClassifier:
    """Classifies tool execution errors into failure types.

    Uses pattern matching heuristics to determine whether an error
    is transient (retry), semantic (re-plan), or fatal (report).
    """

    def classify(self, error_message: str) -> FailureType:
        """Classify an error message into a FailureType."""
        lower_msg = error_message.lower()

        for pattern in _FATAL_PATTERNS:
            if pattern in lower_msg:
                return FailureType.FATAL

        for pattern in _TRANSIENT_PATTERNS:
            if pattern in lower_msg:
                return FailureType.TRANSIENT

        for pattern in _SEMANTIC_PATTERNS:
            if pattern in lower_msg:
                return FailureType.SEMANTIC

        return FailureType.UNKNOWN


def classify_failure(error_message: str) -> FailureType:
    """Standalone wrapper for FailureClassifier.classify()."""
    return _classifier.classify(error_message)


class DiagnosisBuilder:
    """Builds structured diagnosis prompts for LLM correction.

    Creates detailed error context that the LLM can use to
    understand what went wrong and generate corrective tool calls.
    """

    def build_prompt(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        error_message: str,
        failure_type: FailureType,
        attempt_history: list[RetryAttempt],
    ) -> str:
        """Build a structured diagnosis prompt."""
        lines: list[str] = [
            "## ⚠️ Tool Execution Failure — Diagnosis Report",
            "",
            f"**Tool:** `{tool_name}`",
            f"**Failure Type:** `{failure_type.value}`",
            f"**Attempt:** {len(attempt_history) + 1}",
            "",
            "### Error Message",
            f"```\n{error_message}\n```",
            "",
            "### Arguments Used",
        ]

        for key, value in arguments.items():
            val_str = str(value)
            if len(val_str) > 200:
                val_str = val_str[:200] + "..."
            lines.append(f"- `{key}`: {val_str}")

        if attempt_history:
            lines.append("")
            lines.append("### Previous Attempts")
            for attempt in attempt_history[-3:]:
                lines.append(
                    f"- Attempt {attempt.attempt_number}: "
                    f"`{attempt.failure_type.value}` — {attempt.error_message[:100]}"
                )

        lines.extend([
            "",
            "### Recommended Action",
        ])

        if failure_type == FailureType.TRANSIENT:
            lines.append(
                "This appears to be a transient error. The system will retry automatically. "
                "If the error persists, consider alternative approaches."
            )
        elif failure_type == FailureType.SEMANTIC:
            lines.append(
                "This appears to be a semantic error (wrong arguments or path). "
                "Please review the arguments and try again with corrected values. "
                "Check file paths exist, verify parameter types, and ensure the target is valid."
            )
        elif failure_type == FailureType.FATAL:
            lines.append(
                "This is a fatal error that cannot be resolved by retrying. "
                "Report the issue to the user and suggest manual intervention or an alternative approach."
            )
        else:
            lines.append(
                "The error type is unclear. Try an alternative approach or tool to accomplish the same goal."
            )

        return "\n".join(lines)


# Module-level singleton instances
_classifier = FailureClassifier()
_diagnosis_builder = DiagnosisBuilder()


def build_diagnosis_prompt(
    tool_name: str,
    arguments: dict[str, Any],
    error_message: str,
    failure_type: FailureType,
    attempt_history: list[RetryAttempt],
) -> str:
    """Standalone wrapper for DiagnosisBuilder.build_prompt()."""
    return _diagnosis_builder.build_prompt(
        tool_name=tool_name,
        arguments=arguments,
        error_message=error_message,
        failure_type=failure_type,
        attempt_history=attempt_history,
    )


class SelfHealingExecutor:
    """Self-healing wrapper around tool execution.

    Adds retry logic with exponential backoff, error classification,
    and structured diagnosis prompts for LLM-guided recovery.

    Usage:
        healer = SelfHealingExecutor(max_retries=3)
        result = healer.execute_with_healing(
            tool=my_tool,
            tool_call=call,
            on_event=emit_event,
        )
        if not result.success:
            # Feed result.diagnosis back to LLM
            ...
    """

    # Per-tool timeout overrides (seconds)
    TOOL_TIMEOUTS: dict[str, int] = {
        "shell": 120,
        "git": 60,
        "browser": 90,
        "web_search": 30,
        "rag_search": 30,
        "read_file": 10,
        "write_file": 10,
        "code_edit": 15,
        "batch_edit": 30,
        "lsp_query": 20,
    }

    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        base_delay: float = 0.5,
        max_delay: float = 10.0,
    ):
        """Initialize the self-healing executor.

        Args:
            max_retries: Maximum number of retry attempts for transient errors.
            backoff_factor: Multiplier for exponential backoff.
            base_delay: Initial delay between retries (seconds).
            max_delay: Maximum delay between retries (seconds).
        """
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._classifier = _classifier
        self._diagnosis_builder = _diagnosis_builder
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="self_heal")

    def execute_with_healing(
        self,
        tool: Any,
        arguments: dict[str, Any],
        tool_call_id: str = "",
        on_event: Callable[[str, Any], None] | None = None,
    ) -> HealingResult:
        """Execute a tool with self-healing retry logic.

        Args:
            tool: The tool instance to execute.
            arguments: Arguments to pass to tool.execute().
            tool_call_id: ID of the originating tool call.
            on_event: Optional callback for telemetry events.

        Returns:
            HealingResult with success status, output, and diagnosis.
        """
        attempts: list[RetryAttempt] = []
        tool_name = getattr(tool, "name", str(tool))
        last_error = ""
        last_failure_type = FailureType.UNKNOWN

        for attempt_num in range(1, self.max_retries + 1):
            start_time = time.time()

            try:
                # Execute the tool with thread-level timeout enforcement
                timeout = self.TOOL_TIMEOUTS.get(tool_name, 60)

                def worker():
                    return tool.execute(**arguments)

                future = self._executor.submit(worker)
                result = future.result(timeout=timeout)
                duration_ms = (time.time() - start_time) * 1000

                # Check if result indicates an error (tools return error strings)
                result_str = str(result) if result is not None else ""
                if result_str.startswith("Error:") or result_str.startswith("⚠️"):
                    raise RuntimeError(result_str)

                # Success
                if on_event:
                    on_event("self_heal_success", {
                        "tool": tool_name,
                        "attempt": attempt_num,
                        "healed": attempt_num > 1,
                        "duration_ms": duration_ms,
                    })

                return HealingResult(
                    success=True,
                    final_output=result_str or "Success (no output)",
                    attempts=attempts,
                    total_retries=attempt_num - 1,
                    healed=attempt_num > 1,
                )

            except (RuntimeError, ValueError, OSError) as e:
                duration_ms = (time.time() - start_time) * 1000
                error_msg = str(e)
                failure_type = self._classifier.classify(error_msg)

                attempt = RetryAttempt(
                    attempt_number=attempt_num,
                    tool_name=tool_name,
                    arguments=arguments,
                    error_message=error_msg,
                    failure_type=failure_type,
                    duration_ms=duration_ms,
                )
                attempts.append(attempt)
                last_error = error_msg
                last_failure_type = failure_type

                logger.warning(
                    f"Self-healing attempt {attempt_num}/{self.max_retries} "
                    f"for tool '{tool_name}': {failure_type.value} — {error_msg[:100]}"
                )

                if on_event:
                    on_event("self_heal_retry", {
                        "tool": tool_name,
                        "attempt": attempt_num,
                        "failure_type": failure_type.value,
                        "error": error_msg[:200],
                        "duration_ms": duration_ms,
                    })

                # Fatal errors: don't retry
                if failure_type == FailureType.FATAL:
                    logger.error(f"Fatal error for tool '{tool_name}': {error_msg}")
                    break

                # Semantic errors: don't retry (LLM needs to re-plan)
                if failure_type == FailureType.SEMANTIC and attempt_num > 1:
                    # Allow one retry for semantic errors in case it's a timing issue
                    break

                # Transient/unknown: retry with backoff
                if attempt_num < self.max_retries:
                    delay = min(
                        self.base_delay * (self.backoff_factor ** (attempt_num - 1)),
                        self.max_delay,
                    )
                    logger.info(f"Retrying in {delay:.1f}s...")
                    time.sleep(delay)

        # All retries exhausted — generate diagnosis
        diagnosis = self._diagnosis_builder.build_prompt(
            tool_name=tool_name,
            arguments=arguments,
            error_message=last_error,
            failure_type=last_failure_type,
            attempt_history=attempts,
        )

        if on_event:
            on_event("self_heal_failed", {
                "tool": tool_name,
                "total_attempts": len(attempts),
                "failure_type": last_failure_type.value,
                "diagnosis_length": len(diagnosis),
            })

        return HealingResult(
            success=False,
            final_output=f"Error after {len(attempts)} attempts: {last_error}",
            attempts=attempts,
            total_retries=len(attempts),
            healed=False,
            failure_type=last_failure_type,
            diagnosis=diagnosis,
        )
