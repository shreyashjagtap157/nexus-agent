"""Tests for the AST-based code intelligence tools (import graph, call graph, rename)."""

import tempfile
import textwrap
import unittest
from pathlib import Path

from nexus_agent.tools.code_intel import (
    CallGraphTool,
    ImportGraphTool,
    RenameTool,
)


class TestImportGraphTool(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmpdir.name)
        self.tool = ImportGraphTool(workspace=self.workspace)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_build_empty_workspace(self):
        out = self.tool.execute(action="build")
        self.assertIn("No imports detected", out)

    def test_build_with_imports(self):
        (self.workspace / "a.py").write_text("import os\nimport sys\n")
        (self.workspace / "b.py").write_text("from os import path\nimport a\n")
        out = self.tool.execute(action="build")
        self.assertIn("imports", out)
        self.assertIn("os", out)

    def test_find_dependents(self):
        (self.workspace / "a.py").write_text("import os\n")
        (self.workspace / "b.py").write_text("import a\n")
        out = self.tool.execute(action="find_dependents", target="a")
        self.assertIn("b", out)

    def test_find_dependents_with_target_required(self):
        out = self.tool.execute(action="find_dependents", target="")
        self.assertIn("required", out)

    def test_find_dependents_no_match(self):
        (self.workspace / "a.py").write_text("import os\n")
        out = self.tool.execute(action="find_dependents", target="nonexistent")
        self.assertIn("No modules", out)

    def test_unknown_action(self):
        out = self.tool.execute(action="garbage")
        self.assertIn("Unknown", out)

    def test_excludes_pycache(self):
        import os
        cache = self.workspace / "__pycache__"
        cache.mkdir()
        (cache / "x.py").write_text("import os\n")
        (self.workspace / "a.py").write_text("import sys\n")
        out = self.tool.execute(action="build")
        # The pycache file should not appear in the graph
        self.assertNotIn("__pycache__.x", out)


class TestCallGraphTool(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmpdir.name)
        self.tool = CallGraphTool(workspace=self.workspace)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_build_call_graph(self):
        f = self.workspace / "code.py"
        f.write_text(textwrap.dedent("""
            def foo():
                bar()

            def bar():
                pass

            def baz():
                foo()
                bar()
        """).strip())
        out = self.tool.execute(file_path="code.py")
        self.assertIn("foo", out)
        self.assertIn("bar", out)
        self.assertIn("baz", out)

    def test_trace_function(self):
        f = self.workspace / "code.py"
        f.write_text(textwrap.dedent("""
            def caller():
                helper()

            def other():
                helper()

            def helper():
                pass
        """).strip())
        out = self.tool.execute(file_path="code.py", trace_function="helper")
        self.assertIn("caller", out)
        self.assertIn("other", out)

    def test_trace_no_callers(self):
        f = self.workspace / "code.py"
        f.write_text("def helper(): pass\n")
        out = self.tool.execute(file_path="code.py", trace_function="helper")
        self.assertIn("No function calls", out)

    def test_missing_file(self):
        out = self.tool.execute(file_path="nope.py")
        self.assertIn("does not exist", out)

    def test_syntax_error(self):
        f = self.workspace / "bad.py"
        f.write_text("def foo(:\n")
        out = self.tool.execute(file_path="bad.py")
        self.assertIn("AST Parsing Error", out)

    def test_path_outside_workspace(self):
        out = self.tool.execute(file_path="../outside.py")
        self.assertIn("Error", out)


class TestRenameTool(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmpdir.name)
        self.tool = RenameTool(workspace=self.workspace)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_rename_variable(self):
        f = self.workspace / "code.py"
        f.write_text("x = 1\ny = x + x\n")
        out = self.tool.execute(file_path="code.py", old_symbol="x", new_symbol="z")
        self.assertIn("renamed", out)
        new = f.read_text()
        self.assertNotIn("x = 1", new.splitlines()[0])
        self.assertIn("z = 1", new)

    def test_rename_function(self):
        f = self.workspace / "code.py"
        f.write_text(textwrap.dedent("""
            def foo():
                return 1
            x = foo()
        """).strip())
        out = self.tool.execute(file_path="code.py", old_symbol="foo", new_symbol="bar")
        self.assertIn("renamed", out)
        self.assertIn("def bar", f.read_text())
        self.assertNotIn("def foo", f.read_text())

    def test_rename_no_match(self):
        f = self.workspace / "code.py"
        f.write_text("x = 1\n")
        out = self.tool.execute(file_path="code.py", old_symbol="nope", new_symbol="z")
        self.assertIn("No occurrences", out)

    def test_rename_creates_backup(self):
        f = self.workspace / "code.py"
        f.write_text("x = 1\n")
        self.tool.execute(file_path="code.py", old_symbol="x", new_symbol="z")
        bak = f.with_suffix(".py.bak")
        self.assertTrue(bak.exists())

    def test_rename_missing_file(self):
        out = self.tool.execute(file_path="nope.py", old_symbol="x", new_symbol="y")
        self.assertIn("does not exist", out)

    def test_rename_syntax_error(self):
        f = self.workspace / "bad.py"
        f.write_text("def foo(:\n    pass\n")
        out = self.tool.execute(file_path="bad.py", old_symbol="foo", new_symbol="bar")
        self.assertIn("AST error", out)

    def test_rename_does_not_affect_other_identifiers(self):
        f = self.workspace / "code.py"
        f.write_text("x = 1\nxx = 2\nxxx = 3\n")
        self.tool.execute(file_path="code.py", old_symbol="x", new_symbol="X")
        new = f.read_text()
        # Whole-word replacement should not touch xx or xxx
        self.assertIn("xx = 2", new)
        self.assertIn("xxx = 3", new)


if __name__ == "__main__":
    unittest.main()
