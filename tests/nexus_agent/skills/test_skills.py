"""Tests for the skills module — SkillLoader, SkillRegistry."""

import tempfile
import unittest
from pathlib import Path

from nexus_agent.skills.skill_registry import SkillRegistry


class TestSkillRegistry(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.skills_dir = Path(self.tmpdir.name) / "skills"
        self.skills_dir.mkdir()
        self.registry = SkillRegistry(search_dirs=[self.skills_dir], workspace=Path(self.tmpdir.name))

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_discover_skills_empty(self):
        skills = self.registry.discover_skills()
        self.assertIsInstance(skills, list)

    def test_discover_skill_from_markdown(self):
        skill_file = self.skills_dir / "test_skill.md"
        skill_file.write_text(
            "---\n"
            "name: test_skill\n"
            "description: A test skill\n"
            "parameters:\n"
            "  query:\n"
            "    type: string\n"
            "    description: Search query\n"
            "required_params:\n"
            "  - query\n"
            "permission_level: ask\n"
            "---\n"
            "## Instructions\n"
            "Search for {{ query }} in the codebase.\n",
            encoding="utf-8",
        )
        skills = self.registry.discover_skills()
        self.assertGreaterEqual(len(skills), 1)
        skill_names = [s.name for s in skills]
        self.assertIn("test_skill", skill_names)

    def test_get_skill(self):
        skill_file = self.skills_dir / "my_tool.md"
        skill_file.write_text(
            "---\n"
            "name: my_tool\n"
            "description: Custom tool\n"
            "---\n"
            "Do the thing.\n",
            encoding="utf-8",
        )
        self.registry.discover_skills()
        skill = self.registry.get_skill("my_tool")
        self.assertIsNotNone(skill)
        self.assertEqual(skill.name, "my_tool")

    def test_get_nonexistent_skill(self):
        self.assertIsNone(self.registry.get_skill("does_not_exist"))

    def test_get_as_tools(self):
        skill_file = self.skills_dir / "tool_a.md"
        skill_file.write_text(
            "---\nname: tool_a\ndescription: Tool A\n---\nDo A\n",
            encoding="utf-8",
        )
        self.registry.discover_skills()
        tools = self.registry.get_as_tools()
        self.assertGreaterEqual(len(tools), 1)

    def test_attach_agent_core(self):
        skill_file = self.skills_dir / "core_skill.md"
        skill_file.write_text(
            "---\nname: core_skill\ndescription: Needs core\n---\nDo stuff\n",
            encoding="utf-8",
        )
        self.registry.discover_skills()
        agent_core = object()
        self.registry.attach_agent_core(agent_core)
        skill = self.registry.get_skill("core_skill")
        self.assertIsNotNone(skill)
        self.assertIs(skill.agent_core, agent_core)
