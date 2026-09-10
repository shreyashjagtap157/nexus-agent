"""Tests for the skill system."""

import pytest
from pathlib import Path

from nexus_agent.skills.skill_loader import Skill, load_skill_from_markdown, render_template, TemplateError
from nexus_agent.skills.skill_registry import SkillRegistry


class TestSkillLoader:
    @pytest.fixture
    def sample_skill(self, tmp_path):
        skill_content = """---
name: test_skill
description: A test skill
parameters:
  code:
    type: string
    description: The code to review
permission_level: read-only
---
You are a code review expert. Review the following code:

{{ code }}

Provide detailed feedback.
"""
        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text(skill_content)
        return skill_file

    def test_load_skill(self, sample_skill):
        skill = load_skill_from_markdown(sample_skill)
        assert skill is not None
        assert skill.name == "test_skill"
        assert "test skill" in skill.description.lower()

    def test_skill_as_tool(self, sample_skill):
        skill = load_skill_from_markdown(sample_skill)
        assert skill.permission_level == "read-only"
        assert "code" in skill.parameters

    def test_invalid_file(self, tmp_path):
        invalid = tmp_path / "invalid.md"
        invalid.write_text("Just some text without frontmatter")
        result = load_skill_from_markdown(invalid)
        assert result is None

    def test_missing_frontmatter(self, tmp_path):
        missing = tmp_path / "missing.md"
        missing.write_text("No frontmatter here")
        result = load_skill_from_markdown(missing)
        assert result is None


class TestTemplateRendering:
    def test_simple_render(self):
        template = "Hello {{ name }}!"
        result = render_template(template, {"name": "World"})
        assert result == "Hello World!"

    def test_render_with_filter(self):
        template = "Upper: {{ name|upper }}"
        result = render_template(template, {"name": "hello"})
        assert result == "Upper: HELLO"

    def test_render_default_filter(self):
        template = "Value: {{ name|default:\"fallback\" }}"
        result = render_template(template, {"name": ""})
        assert result == 'Value: fallback'

    def test_missing_variable_raises(self):
        template = "Hello {{ missing }}!"
        with pytest.raises(TemplateError):
            render_template(template, {})

    def test_truncate_filter(self):
        template = "{{ text|truncate:6 }}"
        result = render_template(template, {"text": "hello world"})
        assert result == "hello…"

    def test_json_filter(self):
        template = "{{ data|json }}"
        result = render_template(template, {"data": {"key": "value"}})
        assert "key" in result

    def test_chained_filters(self):
        template = "{{ name|lower|trim }}"
        result = render_template(template, {"name": "  HELLO  "})
        assert result == "hello"


class TestSkillRegistry:
    @pytest.fixture
    def registry(self, tmp_path):
        return SkillRegistry(
            search_dirs=[str(tmp_path / "skills")],
            workspace=tmp_path,
        )

    def test_discover_empty(self, registry):
        skills = registry.discover_skills()
        # May return dict or list depending on implementation
        assert isinstance(skills, (dict, list))
