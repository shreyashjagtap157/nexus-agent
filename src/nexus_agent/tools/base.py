"""
Tool Base Interface — with ACI-style structured output formatting.

Defines the abstract Tool class that all agent tools must implement.
Each tool has a name, description, parameter schema, permission level,
and an execute method.

Implements SWE-Agent's **Agent-Computer Interface (ACI)** pattern:
- ``format_aci_output()`` — wraps raw tool output with structured metadata
- ``handle_empty_output()`` — returns explicit confirmation instead of silence
- ``validate_with_linter()`` — optional syntax validation for code output
- ACI-formatted results include: success/failure status, truncated preview,
  execution time, and error context for the LLM to consume.
"""

from __future__ import annotations

import time
import traceback
from abc import ABC, abstractmethod
from functools import cached_property
from pathlib import Path
from typing import Any


class ToolError(Exception):
    """Error raised by tool execution."""


# ── ACI Output Formatting ────────────────────────────────────────────

# Maximum raw content shown in ACI output summaries to avoid context
# window overflows (matches SWE-agent's ~100 line display convention).
ACI_MAX_PREVIEW_CHARS = 2000
ACI_MAX_PREVIEW_LINES = 100
ACI_TRUNCATION_MSG = "... [output truncated]"
ACI_SUCCESS_EMPTY_MSG = "Command executed successfully and produced no output."


def format_aci_output(
    output: Any,
    success: bool = True,
    tool_name: str = "",
    error: str | None = None,
    execution_time_ms: float = 0.0,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Format a tool execution result following the ACI specification.

    Produces a structured, LLM-friendly string that includes:
    - Explicit success/failure header
    - Truncated content preview with line count
    - Execution performance (time, size)
    - Error context when applicable

    Args:
        output: The raw tool output (string, dict, list, or None).
        success: Whether the tool execution succeeded.
        tool_name: The tool name for context in the output.
        error: Error message if execution failed.
        execution_time_ms: Wall-clock execution time in milliseconds.
        metadata: Additional structured metadata to include.

    Returns:
        A formatted string ready for inclusion in LLM conversation context.
    """
    parts: list[str] = []

    # Convert output to string
    if output is None:
        content_str = ""
    elif isinstance(output, (dict, list)):
        import json
        try:
            content_str = json.dumps(output, indent=2, default=str)
        except (TypeError, ValueError):
            content_str = str(output)
    else:
        content_str = str(output)

    # Success/failure header
    if success:
        parts.append(f"[SUCCESS] {tool_name}" if tool_name else "[SUCCESS]")
    else:
        parts.append(f"[FAILURE] {tool_name}" if tool_name else "[FAILURE]")

    # Handle empty output (ACI pattern: explicit confirmation)
    if success and not content_str.strip():
        parts.append(ACI_SUCCESS_EMPTY_MSG)
        if metadata:
            import json
            try:
                meta_str = json.dumps(metadata, default=str)
                parts.append(f"Metadata: {meta_str}")
            except (TypeError, ValueError):
                pass
        return "\n".join(parts)

    # Truncated content preview (ACI pattern: concise display)
    lines = content_str.split("\n")
    preview_lines = lines[:ACI_MAX_PREVIEW_LINES]
    preview = "\n".join(preview_lines)

    if len(preview) > ACI_MAX_PREVIEW_CHARS:
        preview = preview[:ACI_MAX_PREVIEW_CHARS] + "..."

    total_lines = len(lines)
    total_chars = len(content_str)
    truncated = total_lines > ACI_MAX_PREVIEW_LINES or total_chars > ACI_MAX_PREVIEW_CHARS

    parts.append("")
    parts.append(preview)
    if truncated:
        parts.append(ACI_TRUNCATION_MSG)

    # Footer with stats
    stats: list[str] = []
    stats.append(f"({total_lines} lines, {total_chars} chars")
    if execution_time_ms > 0:
        stats.append(f", {execution_time_ms:.0f}ms")
    stats.append(")")
    parts.append("".join(stats))

    # Error context
    if error:
        parts.append(f"Error: {error}")

    # Additional metadata
    if metadata:
        import json
        try:
            meta_str = json.dumps(metadata, default=str)
            parts.append(f"Metadata: {meta_str}")
        except (TypeError, ValueError):
            pass

    return "\n".join(parts)


def summarize_search_results(results: list[dict[str, Any]], max_files: int = 20) -> str:
    """Summarize code search results into a concise file listing.

    ACI pattern: instead of dumping every match line-by-line, summarize
    by file to prevent context overflow.

    Args:
        results: Raw search results (each with 'path', 'line', 'content' keys).
        max_files: Maximum files to list before truncating.

    Returns:
        Formatted summary string.
    """
    from collections import Counter

    files: Counter = Counter()
    for r in results:
        files[r.get("path", "unknown")] += 1

    total_matches = len(results)
    total_files = len(files)

    lines: list[str] = [f"Search returned {total_matches} matches in {total_files} files"]

    for i, (path, count) in enumerate(files.most_common(max_files)):
        lines.append(f"  {path} ({count} matches)")

    if total_files > max_files:
        lines.append(f"  ... and {total_files - max_files} more files")

    return "\n".join(lines)


def format_linter_feedback(errors: list[dict[str, Any]]) -> str:
    """Format linter/syntax errors for LLM consumption.

    ACI pattern: syntactic enforcement — when code is invalid, the tool
    aborts and returns structured error feedback.

    Args:
        errors: List of linter error dicts with 'line', 'col', 'message' keys.

    Returns:
        Formatted error string.
    """
    if not errors:
        return "No linting errors found."

    lines: list[str] = [
        f"Linting failed with {len(errors)} error(s):",
        "",
    ]
    for e in errors[:20]:
        line = e.get("line", "?")
        col = e.get("col", "?")
        msg = e.get("message", "Unknown error")
        lines.append(f"  L{line}:{col} {msg}")

    if len(errors) > 20:
        lines.append(f"  ... and {len(errors) - 20} more errors")

    return "\n".join(lines)


class Tool(ABC):
    __parameters_cache: dict[str, Any] | None = None
    """Abstract base class for agent tools.

    All tools implement this interface to provide a consistent
    way for the agent to discover and use capabilities.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name (used by LLM for function calling)."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what the tool does."""
        ...

    @cached_property
    def parameters(self) -> dict[str, Any]:
        """JSON Schema for tool parameters."""
        ...

    @property
    def required_params(self) -> list[str]:
        """List of required parameter names."""
        return [
            name for name, schema in self.parameters_schema.items()
            if schema.get("required", True)
        ]

    @property
    def permission_level(self) -> str:
        """Permission level: 'read-only', 'read-write', 'dangerous'."""
        return "read-only"

    @property
    def timeout(self) -> int:
        """Execution timeout in seconds."""
        return 30

    @abstractmethod
    def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with given parameters.

        Returns:
            Tool output (string, dict, or any serializable type).
        """
        ...

    def validate_params(self, **kwargs: Any) -> list[str]:
        """Validate parameters. Returns list of error messages."""
        errors = []
        for name in self.required_params:
            if name not in kwargs or kwargs[name] is None:
                errors.append(f"Missing required parameter: {name}")
            elif isinstance(kwargs[name], str) and not kwargs[name].strip():
                errors.append(f"Required parameter '{name}' cannot be empty or whitespace-only")
        return errors

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Cached JSON Schema for tool parameters."""
        if self.__parameters_cache is None:
            self.__parameters_cache = self.parameters
        return self.__parameters_cache

    def to_definition(self) -> dict[str, Any]:
        """Convert to LLM-compatible tool definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters_schema,
                    "required": self.required_params,
                },
            },
        }

    @staticmethod
    def resolve_workspace_path(workspace: Path, path_str: str) -> Path:
        """Resolve a path string and validate it stays within the workspace.

        Args:
            workspace: The allowed workspace root.
            path_str: The path string (relative or absolute).

        Returns:
            Resolved Path.

        Raises:
            ValueError: If the resolved path escapes the workspace.
        """
        if not path_str or not path_str.strip():
            raise ValueError("Empty path")

        p = Path(path_str)
        if not p.is_absolute():
            p = (workspace / p).resolve()
        else:
            p = p.resolve()

        workspace_resolved = workspace.resolve()
        try:
            p.relative_to(workspace_resolved)
        except ValueError:
            raise ValueError(
                f"Path '{path_str}' resolves outside the workspace ({workspace_resolved}). "
                f"Access denied."
            )
        return p

    def __repr__(self) -> str:
        return f"<Tool:{self.name} level={self.permission_level}>"
