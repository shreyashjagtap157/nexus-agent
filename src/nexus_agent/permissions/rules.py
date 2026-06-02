"""
Permission Rules — Defines the rule structure for tool access control.

Rules follow the allow/ask/deny pattern from opencode and claude-code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PermissionLevel(str, Enum):
    """Permission levels for tool actions.

    Conceptually aligns with sandbox mode concepts:
      - ALLOW  ~ unrestricted (no sandbox restrictions)
      - ASK    ~ prompt-before-execute (interactive sandbox)
      - DENY   ~ fully blocked (strict sandbox)

    These map 1:1 to opencode's allow/ask/deny permission model.
    """
    ALLOW = "allow"    # Always allowed, no prompt
    ASK = "ask"        # Prompt user for approval
    DENY = "deny"      # Always denied


@dataclass
class PermissionRule:
    """A single permission rule.

    Rules match against tool names and optionally against
    specific argument patterns.
    """
    tool_name: str                          # Tool name or '*' for all
    level: PermissionLevel                  # allow, ask, deny
    description: str = ""                   # Human-readable description
    arg_patterns: dict[str, str] = field(default_factory=dict)  # Argument pattern constraints
    project: str | None = None              # Project-specific rule (None = global)

    def matches(self, tool_name: str, arguments: dict[str, Any] | None = None) -> bool:
        """Check if this rule matches a tool call.

        Args:
            tool_name: Name of the tool being called.
            arguments: Tool call arguments.

        Returns:
            True if this rule applies to the given tool call.
        """
        # Check tool name
        if self.tool_name != "*" and self.tool_name != tool_name:
            return False

        # Check argument patterns (if any)
        if self.arg_patterns and arguments:
            for arg_name, pattern in self.arg_patterns.items():
                arg_value = str(arguments.get(arg_name, ""))
                try:
                    if not re.search(pattern, arg_value):
                        return False
                except re.error:
                    return False

        return True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "tool_name": self.tool_name,
            "level": self.level.value,
            "description": self.description,
            "arg_patterns": self.arg_patterns,
            "project": self.project,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PermissionRule:
        """Deserialize from dict."""
        return cls(
            tool_name=data["tool_name"],
            level=PermissionLevel(data["level"]),
            description=data.get("description", ""),
            arg_patterns=data.get("arg_patterns", {}),
            project=data.get("project"),
        )


# Default permission rules
# NOTE: Rules are evaluated in order; more specific rules should come before
# wildcard "*" (match-all) rules so that specific tools are matched first.
DEFAULT_RULES = [
    PermissionRule("read_file", PermissionLevel.ALLOW, "Reading files is always safe"),
    PermissionRule("search_files", PermissionLevel.ALLOW, "Searching files is always safe"),
    PermissionRule("list_directory", PermissionLevel.ALLOW, "Listing directories is always safe"),
    PermissionRule("web_search", PermissionLevel.ALLOW, "Web search is safe"),
    PermissionRule("lsp_query", PermissionLevel.ALLOW, "LSP queries are read-only"),
    PermissionRule("write_file", PermissionLevel.ASK, "File writes need approval"),
    PermissionRule("edit_file", PermissionLevel.ASK, "File edits need approval"),
    PermissionRule("insert_lines", PermissionLevel.ASK, "Line insertions need approval"),
    PermissionRule("run_command", PermissionLevel.ASK, "Shell commands need approval"),
    PermissionRule("git", PermissionLevel.ASK, "Git operations need approval"),
    PermissionRule("browser", PermissionLevel.ASK, "Browser actions need approval"),
]
