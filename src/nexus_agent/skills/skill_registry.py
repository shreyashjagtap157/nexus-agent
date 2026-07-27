"""
Skill Registry — Scans, registers, and manages agent skills.

Provides the central directory that discovers .md skill configurations
from global, project, and package directories.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from nexus_agent.skills.skill_loader import Skill, load_skill_from_markdown

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Discovers and registers Markdown skills across configured directories."""

    def __init__(self, search_dirs: list[str] | None = None, workspace: Path | None = None):
        """Initialize the Skill Registry.

        Args:
            search_dirs: Directories to scan for skill .md files.
            workspace: Current working workspace.
        """
        self._workspace = workspace or Path.cwd()
        self._skills: dict[str, Skill] = {}
        self._lock = threading.Lock()

        # Build search directory list
        self._search_paths: list[Path] = []
        if search_dirs:
            for d in search_dirs:
                self._search_paths.append(Path(d).expanduser().resolve())

        # Always include the package built-in skills directory as fallback
        builtin_dir = Path(__file__).parent / "builtin"
        if builtin_dir not in self._search_paths:
            self._search_paths.append(builtin_dir)

    @property
    def skills(self) -> dict[str, Skill]:
        """Get dict of registered skills mapping name to Skill."""
        with self._lock:
            return dict(self._skills)

    def discover_skills(self) -> list[Skill]:
        """Scan all search paths and load valid .md skills.

        Returns:
            List of successfully loaded Skill objects.
        """
        with self._lock:
            self._skills.clear()

        for path in self._search_paths:
            if not path.exists():
                logger.debug(f"Skill search directory does not exist: {path}")
                continue

            logger.info(f"Scanning for agent skills in: {path}")

            # Find all .md files in the search path
            for skill_file in path.glob("*.md"):
                skill = load_skill_from_markdown(skill_file, workspace=self._workspace)
                if skill:
                    with self._lock:
                        if skill.name in self._skills:
                            logger.warning(f"Overwriting duplicate skill name '{skill.name}' from {skill_file}")
                        self._skills[skill.name] = skill
                    logger.info(f"Successfully registered skill: {skill.name} ({skill_file.name})")

        with self._lock:
            return list(self._skills.values())

    def get_skill(self, name: str) -> Skill | None:
        """Retrieve a registered skill by name."""
        with self._lock:
            return self._skills.get(name)

    def attach_agent_core(self, agent_core: Any) -> None:
        """Bind the parent AgentLoop to all loaded skills to allow sub-agent spawning.

        Args:
            agent_core: Parent AgentLoop instance.
        """
        with self._lock:
            for skill in self._skills.values():
                skill.agent_core = agent_core

    def get_as_tools(self) -> list[Skill]:
        """Expose all discovered skills as standard executable toolbelt list."""
        with self._lock:
            return list(self._skills.values())
