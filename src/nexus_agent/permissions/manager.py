"""
Permission Manager — Evaluates tool permissions against rules.

Provides the permission evaluation engine that the agent loop
uses to decide whether to allow, prompt, or deny tool calls.
Supports global rules, per-project overrides, and runtime grants.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Protocol

from nexus_agent.permissions.rules import (
    DEFAULT_RULES,
    PermissionLevel,
    PermissionRule,
)

logger = logging.getLogger(__name__)


class PermissionApprover(Protocol):
    """Protocol for permission approval callbacks.

    Called when a tool requires ASK-level permission.
    Returns True to approve, False to deny.
    """

    def __call__(self, tool_name: str, description: str, arguments: dict[str, Any]) -> bool: ...


class PermissionManager:
    """Evaluates tool call permissions against configured rules.

    Rules are evaluated in order:
    1. Runtime grants (temporary per-session approvals)
    2. Project-specific rules
    3. Global rules
    4. Default rules (built-in)
    5. Fallback (configurable, default: ASK)

    Inspired by opencode's granular permission model and
    claude-code's permission modes.
    """

    def __init__(
        self,
        rules: list[PermissionRule] | None = None,
        default_level: PermissionLevel = PermissionLevel.ASK,
        approval_callback: PermissionApprover | None = None,
        project: str | None = None,
    ):
        """Initialize permission manager.

        Args:
            rules: Custom permission rules (appended to defaults).
            default_level: Fallback permission level when no rule matches.
            approval_callback: Function(tool_name, description, args) → bool
                              Called when permission level is ASK.
            project: Current project identifier for project-specific rules.
        """
        self._rules: list[PermissionRule] = list(DEFAULT_RULES)
        if rules:
            self._rules.extend(rules)

        self._default_level = default_level
        self._approval_callback = approval_callback
        self._project = project

        # Runtime grants: tool calls approved during this session
        self._session_grants: set[str] = set()
        # Runtime denials
        self._session_denials: set[str] = set()
        # "Always allow" grants for specific tools in this session
        self._always_allow: set[str] = set()

    def evaluate(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> PermissionLevel:
        """Evaluate the permission level for a tool call.

        Args:
            tool_name: Name of the tool.
            arguments: Tool call arguments.

        Returns:
            PermissionLevel (ALLOW, ASK, or DENY).
        """
        # Check session-level always-allow
        if tool_name in self._always_allow:
            return PermissionLevel.ALLOW

        # Check session denials
        call_key = self._make_call_key(tool_name, arguments)
        if call_key in self._session_denials:
            return PermissionLevel.DENY

        # Check session grants
        if call_key in self._session_grants:
            return PermissionLevel.ALLOW

        # Check rules (project-specific first, then global)
        for rule in self._rules:
            if rule.project and rule.project != self._project:
                continue  # Skip rules for other projects

            if rule.matches(tool_name, arguments):
                return rule.level

        # Fallback
        return self._default_level

    def check_and_approve(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        description: str = "",
    ) -> bool:
        """Check permission and prompt for approval if needed.

        This is the main method called by the agent loop.

        Args:
            tool_name: Tool name.
            arguments: Tool arguments.
            description: Human-readable description of what the tool will do.

        Returns:
            True if the tool call is approved, False if denied.
        """
        level = self.evaluate(tool_name, arguments)

        if level == PermissionLevel.ALLOW:
            logger.debug(f"Permission ALLOW: {tool_name}")
            return True

        if level == PermissionLevel.DENY:
            logger.info(f"Permission DENY: {tool_name}")
            return False

        # ASK — prompt user
        if self._approval_callback:
            approved = self._approval_callback(
                tool_name,
                description or f"Execute tool: {tool_name}",
                arguments or {},
            )

            call_key = self._make_call_key(tool_name, arguments)
            if approved:
                self._session_grants.add(call_key)
                logger.info(f"Permission GRANTED by user: {tool_name}")
            else:
                self._session_denials.add(call_key)
                logger.info(f"Permission DENIED by user: {tool_name}")

            return approved

        # No callback — default deny for ASK
        logger.warning(f"Permission ASK but no callback: {tool_name} → deny")
        return False

    def grant_always(self, tool_name: str) -> None:
        """Grant always-allow for a tool in this session."""
        self._always_allow.add(tool_name)
        logger.info(f"Always-allow granted for: {tool_name}")

    def revoke_always(self, tool_name: str) -> None:
        """Revoke always-allow for a tool."""
        self._always_allow.discard(tool_name)

    def add_rule(self, rule: PermissionRule) -> None:
        """Add a new permission rule."""
        self._rules.insert(0, rule)  # Higher priority

    def remove_rule(self, tool_name: str) -> int:
        """Remove all rules for a tool. Returns count removed."""
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.tool_name != tool_name]
        return before - len(self._rules)

    def get_rules(self) -> list[dict[str, Any]]:
        """Get all rules as serializable dicts."""
        return [r.to_dict() for r in self._rules]

    def load_from_config(self, config: dict[str, Any]) -> None:
        """Load permission settings from config dict.

        Expected format (from config/default.yaml):
        ```yaml
        permissions:
          mode: ask
          tools:
            file_read: allow
            file_write: ask
            shell_execute: ask
        ```
        """
        perm_config = config.get("permissions", {})

        # Set default mode
        mode = perm_config.get("mode", "ask")
        try:
            self._default_level = PermissionLevel(mode)
        except ValueError:
            logger.warning(f"Invalid permission mode '{mode}', falling back to ASK")
            self._default_level = PermissionLevel.ASK

        # Load tool-specific permissions
        tools = perm_config.get("tools", {})
        for tool_name, level_str in tools.items():
            try:
                level = PermissionLevel(level_str)
                self.add_rule(PermissionRule(
                    tool_name=tool_name,
                    level=level,
                    description=f"From config: {tool_name}={level_str}",
                ))
            except ValueError:
                logger.warning(f"Invalid permission level '{level_str}' for tool '{tool_name}'")

    def clear_session_state(self) -> None:
        """Clear session-specific grants and denials."""
        self._session_grants.clear()
        self._session_denials.clear()
        self._always_allow.clear()

    @staticmethod
    def _make_call_key(tool_name: str, arguments: dict[str, Any] | None) -> str:
        """Create a key for caching grant/denial decisions."""
        if not arguments:
            return tool_name
        key_parts = [tool_name]
        try:
            serialized = json.dumps(arguments, sort_keys=True, default=str)
        except (TypeError, ValueError):
            serialized = str(arguments)
        arg_hash = hashlib.sha256(serialized.encode()).hexdigest()[:16]
        key_parts.append(arg_hash)
        return "|".join(key_parts)
