"""
Skill Loader — Loads modular capabilities from Markdown files.

Parses .md files with YAML frontmatter to extract metadata and registers
them as executable agent tools that spawn specialized sub-agents.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import yaml

from nexus_agent.tools.base import Tool

logger = logging.getLogger(__name__)


@runtime_checkable
class SubAgentFactory(Protocol):
    """Protocol for creating sub-agents from skill execution.

    Decouples Skill from AgentLoop to avoid circular imports
    and allow alternative sub-agent implementations.
    """

    def create_sub_agent(self, config: dict) -> Any: ...


class Skill(Tool):
    """An executable agent skill loaded from a Markdown file.

    Inherits from Tool to register directly in the agent's toolbelt. When called,
    it spawns a specialized sub-agent initialized with the skill's system prompt.
    """

    def __init__(self, name: str, description: str, parameters: dict[str, Any],
                 instructions: str, permission_level: str = "read-write",
                 workspace: Path | None = None,
                 agent_core: Any | None = None,
                 sub_agent_factory: SubAgentFactory | None = None):
        """Initialize the Skill.

        Args:
            name: Skill identifier.
            description: Description of the skill capability.
            parameters: JSON schema of arguments expected.
            instructions: Core markdown body representing the system prompt.
            permission_level: Security level (read-only/read-write/dangerous).
            workspace: Target workspace path.
            agent_core: Parent agent core reference (set post-init if not provided).
            sub_agent_factory: Factory for creating sub-agents (decouples from AgentLoop).
        """
        self._name = name
        self._description = description
        self._parameters = parameters
        self._instructions = instructions
        self._permission_level = permission_level
        self._workspace = workspace or Path.cwd()
        self.agent_core = agent_core
        self._sub_agent_factory = sub_agent_factory

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters

    @property
    def permission_level(self) -> str:
        return self._permission_level

    def execute(self, **kwargs: Any) -> str:
        """Execute the skill by spawning a specialized execution sub-agent.

        Args:
            kwargs: Arguments matching the skill parameter schema.

        Returns:
            The formatted result of the sub-agent execution.
        """
        # Validate parameters
        errors = self.validate_params(**kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        logger.info(f"Executing skill '{self._name}' with args: {kwargs}")

        prompt = self._build_prompt(kwargs)
        config = self._build_config()

        logger.info(f"Spawning sub-agent for skill '{self._name}'")

        if self._sub_agent_factory is not None:
            return self._execute_via_factory(config)

        if not self.agent_core:
            return self._render_template(kwargs)

        if getattr(self.agent_core, "provider", None):
            return self._execute_via_agent_core(config, prompt)

        return self._render_template(kwargs)

    def _build_prompt(self, kwargs: dict[str, Any]) -> str:
        """Build the execution prompt from skill arguments."""
        arg_summary = "\n".join(f"- {k}: {v}" for k, v in kwargs.items())
        return (
            f"You are executing the specialized skill '{self._name}'.\n"
            f"Objective / Input Arguments:\n{arg_summary}\n\n"
            "Please fulfill this skill objective completely based on your specialized instructions."
        )

    def _build_config(self) -> dict[str, Any]:
        """Build the sub-agent configuration."""
        return dict(
            provider=getattr(self.agent_core, "provider", None) if self.agent_core else None,
            tools=getattr(self.agent_core, "tools", []) if self.agent_core else [],
            mode="build" if self._permission_level != "read-only" else "plan",
            workspace=self._workspace,
            max_iterations=15,
            temperature=0.1,
            instructions=self._instructions,
        )

    def _execute_via_factory(self, config: dict[str, Any]) -> str:
        """Execute using the sub-agent factory."""
        try:
            result = self._sub_agent_factory.create_sub_agent(config)
            return result or "Skill executed successfully but returned empty result."
        except (ImportError, ValueError, RuntimeError) as e:
            logger.error(f"Skill sub-agent factory execution failed: {e}")
            return f"Error executing skill sub-agent: {e}"

    def _execute_via_agent_core(self, config: dict[str, Any], prompt: str) -> str:
        """Execute using the agent_core's provider to create direct AgentLoop."""
        from nexus_agent.core.agent import AgentLoop, AgentLoopConfig, AgentMode

        sub_cfg = AgentLoopConfig(
            mode=AgentMode.BUILD if self._permission_level != "read-only" else AgentMode.PLAN,
            workspace=self._workspace,
            max_iterations=config["max_iterations"],
            temperature=config["temperature"],
            system_prompt_extra=f"\nSPECIALIZED SKILL INSTRUCTIONS:\n{self._instructions}",
        )
        sub_agent = AgentLoop(
            provider=self.agent_core.provider,
            tools=self.agent_core.tools,
            config=sub_cfg,
        )

        full_response = ""
        try:
            for event in sub_agent.run(prompt):
                if event.type in ("content", "content_chunk"):
                    full_response += event.data
                elif event.type == "content_complete":
                    full_response = event.data
            return full_response or "Skill executed successfully but returned empty result."
        except (ValueError, RuntimeError, OSError) as e:
            logger.error(f"Skill sub-agent execution failed: {e}")
            return f"Error executing skill sub-agent: {e}"

    def _render_template(self, kwargs: dict[str, Any]) -> str:
        """Render a template response when no agent is available."""
        return (
            f"[SKILL TEMPLATE EXECUTED] Skill: {self._name}\n"
            f"Arguments provided: {kwargs}\n"
            f"Skill Instructions:\n{self._instructions}"
        )


def load_skill_from_markdown(file_path: Path, workspace: Path | None = None) -> Skill | None:
    """Parse a Markdown file containing YAML frontmatter into an executable Skill.

    Args:
        file_path: Path to the skill .md file.
        workspace: Path to the working workspace.

    Returns:
        Skill instance, or None if parsing fails.
    """
    try:
        content = file_path.read_text(encoding="utf-8")

        # Look for YAML frontmatter between ---
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if not match:
            logger.warning(f"No YAML frontmatter found in skill: {file_path.name}")
            return None

        frontmatter_str = match.group(1)
        instructions = match.group(2).strip()

        metadata = yaml.safe_load(frontmatter_str)
        if not metadata or not isinstance(metadata, dict):
            logger.warning(f"Invalid YAML frontmatter in skill: {file_path.name}")
            return None

        name = metadata.get("name", file_path.stem)
        description = metadata.get("description", f"Executes {name} skill.")
        parameters = metadata.get("parameters", {})
        permission_level = metadata.get("permission_level", "read-write")

        return Skill(
            name=name,
            description=description,
            parameters=parameters,
            instructions=instructions,
            permission_level=permission_level,
            workspace=workspace,
        )
    except (OSError, UnicodeDecodeError, ValueError) as e:
        logger.error(f"Error loading skill file {file_path}: {e}")
        return None
