"""Tests for the LSPClientTool — covers both real-LSP path and AST fallback."""

from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from nexus_agent.tools.lsp_client import LSPClientTool


class TestLSPClientToolFallback(unittest.TestCase):
    """The tool must work even when no real language server is available."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmpdir.name)
        self.tool = LSPClientTool(workspace=self.workspace)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_diagnostics_python_valid(self):
        py = self.workspace / "good.py"
        py.write_text("x = 1\ny = 2\n")
        out = self.tool.execute(action="diagnostics", file="good.py")
        self.assertIn("Diagnostics OK", out)

    def test_diagnostics_python_syntax_error(self):
        py = self.workspace / "bad.py"
        py.write_text("def foo(\n    pass\n")
        out = self.tool.execute(action="diagnostics", file="bad.py")
        self.assertIn("SYNTAX", out.upper())

    def test_diagnostics_js_balanced(self):
        js = self.workspace / "good.js"
        js.write_text("function foo() { return [1, 2]; }\n")
        out = self.tool.execute(action="diagnostics", file="good.js")
        self.assertIn("OK", out)

    def test_diagnostics_js_unclosed_bracket(self):
        js = self.workspace / "bad.js"
        js.write_text("function foo() { return [1, 2;\n")
        out = self.tool.execute(action="diagnostics", file="bad.js")
        self.assertIn("SYNTAX ERROR", out)

    def test_definition_finds_function(self):
        py = self.workspace / "code.py"
        py.write_text("def helper():\n    return 1\n\nx = helper()\n")
        out = self.tool.execute(action="definition", file="code.py", line=4, character=5)
        self.assertIn("helper", out)
        self.assertIn("line 1", out)

    def test_hover_python_docstring(self):
        py = self.workspace / "code.py"
        py.write_text(textwrap.dedent(
            """
            def greet(name):
                '''Say hi to the given name.'''
                return f"hi {name}"

            x = greet("world")
            """
        ).lstrip())
        # The def is on line 1, so point at it.
        out = self.tool.execute(action="hover", file="code.py", line=1, character=5)
        self.assertIn("Say hi", out)

    def test_missing_file(self):
        out = self.tool.execute(action="diagnostics", file="nope.py")
        self.assertIn("not found", out.lower())

    def test_path_outside_workspace_rejected(self):
        # Using a relative escape
        out = self.tool.execute(action="diagnostics", file="../outside.py")
        self.assertIn("Error", out)


class TestLSPClientToolDispatchesToLSP(unittest.TestCase):
    """When a real LSP client is reachable, queries are forwarded to it."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmpdir.name)
        self.py = self.workspace / "foo.py"
        self.py.write_text("x = 1\n")

        # Fake client
        self.fake_client = MagicMock()
        self.fake_client._guess_language_id.return_value = "python"
        self.fake_client.did_open = MagicMock()
        self.fake_client.request = MagicMock(return_value=[])

        # Inject a pool whose get() returns our fake
        self.tool = LSPClientTool(workspace=self.workspace)
        pool = MagicMock()
        pool.get.return_value = self.fake_client
        self.tool._pool = pool

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_definition_dispatches_to_lsp(self):
        # Simulate a real LSP server returning a location
        self.fake_client.request.return_value = [
            {"uri": "file:///foo.py", "range": {"start": {"line": 0, "character": 0}}}
        ]
        out = self.tool.execute(action="definition", file="foo.py", line=1, character=0)
        self.assertIn("Definition", out)
        self.fake_client.request.assert_called_once()

    def test_hover_dispatches_to_lsp(self):
        self.fake_client.request.return_value = {
            "contents": {"kind": "markdown", "value": "**int** — type of x"}
        }
        out = self.tool.execute(action="hover", file="foo.py", line=1, character=0)
        self.assertIn("int", out)

    def test_diagnostics_dispatches_to_lsp(self):
        self.fake_client.request.return_value = {
            "items": [
                {"range": {"start": {"line": 0, "character": 0}},
                 "severity": 1,
                 "message": "name 'x' is unused",
                 "source": "pyflakes"}
            ]
        }
        out = self.tool.execute(action="diagnostics", file="foo.py")
        self.assertIn("pyflakes", out)
        self.assertIn("unused", out)

    def test_references_dispatches_to_lsp(self):
        self.fake_client.request.return_value = [
            {"uri": "file:///foo.py", "range": {"start": {"line": 1, "character": 0}}}
        ]
        out = self.tool.execute(action="references", file="foo.py", line=1, character=0)
        self.assertIn("Reference", out)

    def test_document_symbols_renders(self):
        self.fake_client.request.return_value = [
            {"name": "foo", "kind": 12, "location": {"range": {"start": {"line": 0, "character": 0}}}},
            {"name": "Bar", "kind": 5, "location": {"range": {"start": {"line": 5, "character": 0}}}},
        ]
        out = self.tool.execute(action="document_symbols", file="foo.py")
        self.assertIn("foo", out)
        self.assertIn("Bar", out)

    def test_completion_renders(self):
        self.fake_client.request.return_value = {
            "items": [{"label": "append", "detail": "list.append()"},
                      {"label": "extend", "detail": "list.extend()"}]
        }
        out = self.tool.execute(action="completion", file="foo.py", line=1, character=0)
        self.assertIn("append", out)
        self.assertIn("extend", out)

    def test_rename_requires_new_name(self):
        out = self.tool.execute(action="rename", file="foo.py", line=1, character=0)
        self.assertIn("new_name", out)

    def test_rename_with_no_edits(self):
        self.fake_client.request.return_value = None
        out = self.tool.execute(action="rename", file="foo.py", line=1, character=0, new_name="bar")
        self.assertIn("No rename edits", out)

    def test_rename_with_edits(self):
        self.fake_client.request.return_value = {
            "changes": {"file:///foo.py": [{"range": {"start": {"line": 0, "character": 4}}, "newText": "bar"}]}
        }
        out = self.tool.execute(action="rename", file="foo.py", line=1, character=0, new_name="bar")
        self.assertIn("1 location", out)


if __name__ == "__main__":
    unittest.main()
