"""Tests for `skills/skill_loader.py` — `render_template()` and templated skills."""

import tempfile
import unittest
from pathlib import Path

from nexus_agent.skills.skill_loader import (
    Skill,
    TemplateError,
    _apply_filter,
    load_skill_from_markdown,
    render_template,
)


class TestRenderTemplate(unittest.TestCase):
    """`render_template()` substitution engine."""

    def test_no_template_returns_empty(self):
        self.assertEqual(render_template("", {}), "")
        self.assertEqual(render_template(None, {}), "")

    def test_no_placeholders_returns_input(self):
        self.assertEqual(
            render_template("hello world", {"x": 1}),
            "hello world",
        )

    def test_simple_substitution(self):
        out = render_template("Hello {{name}}!", {"name": "World"})
        self.assertEqual(out, "Hello World!")

    def test_missing_variable_raises(self):
        with self.assertRaises(TemplateError) as ctx:
            render_template("Hello {{name}}", {})
        self.assertIn("name", str(ctx.exception))

    def test_multiple_substitutions(self):
        out = render_template("{{a}} and {{b}}", {"a": 1, "b": 2})
        self.assertEqual(out, "1 and 2")

    def test_repeated_substitution(self):
        out = render_template("{{x}}-{{x}}-{{x}}", {"x": "A"})
        self.assertEqual(out, "A-A-A")

    def test_whitespace_tolerant(self):
        out = render_template("{{  x  }}", {"x": "v"})
        self.assertEqual(out, "v")

    def test_none_value_renders_as_empty(self):
        out = render_template("a{{x}}b", {"x": None})
        self.assertEqual(out, "ab")

    def test_numeric_value_rendered_as_str(self):
        out = render_template("{{n}}", {"n": 42})
        self.assertEqual(out, "42")

    def test_dict_value_rendered_as_str(self):
        out = render_template("{{d}}", {"d": {"k": "v"}})
        self.assertIn("v", out)


class TestApplyFilter(unittest.TestCase):
    """Filter pipeline."""

    def test_upper(self):
        self.assertEqual(_apply_filter("hello", "upper"), "HELLO")

    def test_lower(self):
        self.assertEqual(_apply_filter("HELLO", "lower"), "hello")

    def test_trim(self):
        self.assertEqual(_apply_filter("  hi  ", "trim"), "hi")

    def test_json(self):
        self.assertEqual(_apply_filter({"a": 1}, "json"), '{"a": 1}')

    def test_repr(self):
        self.assertIn("'hello'", _apply_filter("hello", "repr"))

    def test_default_used_for_none(self):
        self.assertEqual(_apply_filter(None, 'default:"x"'), "x")

    def test_default_used_for_empty_string(self):
        self.assertEqual(_apply_filter("", 'default:"x"'), "x")

    def test_default_unused_for_value(self):
        self.assertEqual(_apply_filter("v", 'default:"x"'), "v")

    def test_default_strips_double_quotes(self):
        self.assertEqual(_apply_filter(None, 'default:"hello"'), "hello")

    def test_default_strips_single_quotes(self):
        self.assertEqual(_apply_filter(None, "default:'hello'"), "hello")

    def test_truncate_with_int(self):
        out = _apply_filter("a" * 100, "truncate:10")
        self.assertTrue(out.endswith("…"))
        self.assertLessEqual(len(out), 10)

    def test_truncate_short_unchanged(self):
        self.assertEqual(_apply_filter("hi", "truncate:10"), "hi")

    def test_truncate_bad_int_defaults_80(self):
        out = _apply_filter("a" * 100, "truncate:bad")
        self.assertEqual(len(out), 80)

    def test_indent(self):
        out = _apply_filter("a\nb", "indent:4")
        self.assertEqual(out, "    a\n    b")

    def test_unknown_filter_returns_value(self):
        self.assertEqual(_apply_filter("v", "nosuchfilter"), "v")

    def test_empty_filter_returns_value(self):
        self.assertEqual(_apply_filter("v", ""), "v")

    def test_quoted_default(self):
        # A name with no colon: treat as a no-op filter name
        self.assertEqual(_apply_filter("v", "default"), "v")


class TestRenderTemplateFilters(unittest.TestCase):
    """Filters chained through `{{ var|filter|filter }}`."""

    def test_upper_filter(self):
        out = render_template("{{name|upper}}", {"name": "alice"})
        self.assertEqual(out, "ALICE")

    def test_truncate_filter(self):
        out = render_template("{{x|truncate:5}}", {"x": "abcdefgh"})
        self.assertTrue(out.endswith("…"))
        self.assertLessEqual(len(out), 5)

    def test_chained_filters(self):
        out = render_template("{{x|upper|truncate:3}}", {"x": "abcdef"})
        self.assertEqual(out, "AB…")

    def test_default_filter_used(self):
        out = render_template("{{x|default:\"fallback\"}}", {"x": None})
        self.assertEqual(out, "fallback")

    def test_json_filter(self):
        out = render_template("{{x|json}}", {"x": {"k": 1}})
        self.assertEqual(out, '{"k": 1}')

    def test_filter_with_no_value_passes_through(self):
        out = render_template("{{x|upper}}", {"x": None})
        self.assertEqual(out, "")


class TestSkillTemplateIntegration(unittest.TestCase):
    """End-to-end: Skill uses render_template() in its execution path."""

    def test_skill_with_template_renders(self):
        sk = Skill(
            name="greet",
            description="Greets the user",
            parameters={"name": {"type": "string"}},
            instructions="Hello, {{name|upper}}!",
        )
        out = sk._render_template({"name": "alice"})
        self.assertIn("ALICE", out)
        self.assertIn("Rendered Instructions", out)

    def test_skill_with_no_template_falls_back(self):
        sk = Skill(
            name="x",
            description="x",
            parameters={},
            instructions="static instructions",
        )
        out = sk._render_template({"x": 1})
        self.assertIn("static instructions", out)
        self.assertIn("Skill Instructions", out)

    def test_skill_template_error_in_render(self):
        sk = Skill(
            name="x",
            description="x",
            parameters={},
            instructions="Hello, {{missing}}",
        )
        out = sk._render_template({})
        self.assertIn("Error", out)
        self.assertIn("missing", out)

    def test_skill_build_prompt_with_template(self):
        sk = Skill(
            name="summarize",
            description="Summarizes",
            parameters={"text": {"type": "string"}},
            instructions="Summarize: {{text|truncate:20}}",
        )
        prompt = sk._build_prompt({"text": "a" * 50})
        self.assertIn("Summarize", prompt)
        self.assertIn("…", prompt)

    def test_skill_build_prompt_fallback(self):
        sk = Skill(
            name="plain",
            description="Plain",
            parameters={"a": {"type": "string"}},
            instructions="no template here",
        )
        prompt = sk._build_prompt({"a": "x"})
        self.assertIn("Objective", prompt)
        self.assertIn("- a: x", prompt)

    def test_skill_build_prompt_template_error(self):
        sk = Skill(
            name="broken",
            description="Broken",
            parameters={},
            instructions="uses {{undefined}}",
        )
        prompt = sk._build_prompt({})
        self.assertIn("Error rendering", prompt)


class TestLoadSkillWithTemplate(unittest.TestCase):
    """`load_skill_from_markdown` works with templated instructions."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "skill.md"

    def tearDown(self):
        self.tmp.cleanup()

    def test_loads_templated_skill(self):
        self.path.write_text(
            "---\n"
            "name: greet\n"
            "description: Greeter\n"
            "parameters:\n"
            "  name:\n"
            "    type: string\n"
            "permission_level: read-only\n"
            "---\n"
            "Hello, {{name}}! Welcome to {{project|default:\"NexusAgent\"}}.\n",
            encoding="utf-8",
        )
        sk = load_skill_from_markdown(self.path)
        self.assertIsNotNone(sk)
        out = sk._render_template({"name": "Alice", "project": ""})
        self.assertIn("Alice", out)
        self.assertIn("NexusAgent", out)  # default fired

    def test_loads_plain_skill(self):
        self.path.write_text(
            "---\n"
            "name: hello\n"
            "description: Says hello\n"
            "parameters: {}\n"
            "permission_level: read-only\n"
            "---\n"
            "Say hello to the world.\n",
            encoding="utf-8",
        )
        sk = load_skill_from_markdown(self.path)
        self.assertIsNotNone(sk)
        out = sk._render_template({})
        self.assertIn("Say hello", out)


if __name__ == "__main__":
    unittest.main()
