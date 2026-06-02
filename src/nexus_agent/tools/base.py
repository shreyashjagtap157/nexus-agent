"""
Tool Base Interface.

Defines the abstract Tool class that all agent tools must implement.
Each tool has a name, description, parameter schema, permission level,
and an execute method.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from functools import cached_property
from pathlib import Path
from typing import Any


class ToolError(Exception):
    """Error raised by tool execution."""


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
