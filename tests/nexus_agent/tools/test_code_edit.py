"""Tests for the CodeEditTool — search-and-replace + AST validation gate."""

import tempfile
import unittest
from pathlib import Path

from nexus_agent.tools.code_edit import CodeEditTool, InsertLinesTool


class TestCodeEditToolBasic(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmpdir.name)
        self.tool = CodeEditTool(workspace=self.workspace)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_replace_text(self):
        f = self.workspace / "a.py"
        f.write_text("x = 1\ny = 2\n")
        out = self.tool.execute(path="a.py", old_content="x = 1", new_content="x = 100")
        self.assertIn("edited successfully", out)
        self.assertIn("x = 100", f.read_text())

    def test_old_content_not_found(self):
        f = self.workspace / "a.py"
        f.write_text("hello\n")
        out = self.tool.execute(path="a.py", old_content="missing", new_content="replacement")
        self.assertIn("Could not find", out)

    def test_replace_all(self):
        f = self.workspace / "a.py"
        f.write_text("x = 1\nx = 1\nx = 1\n")
        out = self.tool.execute(path="a.py", old_content="x = 1", new_content="x = 2", replace_all=True)
        self.assertIn("edited successfully", out)
        self.assertEqual(f.read_text(), "x = 2\nx = 2\nx = 2\n")

    def test_multiple_occurrences_without_replace_all(self):
        f = self.workspace / "a.py"
        f.write_text("x = 1\nx = 1\n")
        out = self.tool.execute(path="a.py", old_content="x = 1", new_content="x = 2")
        self.assertIn("Warning", out)
        self.assertIn("occurrences", out)

    def test_empty_old_content_rejected(self):
        f = self.workspace / "a.py"
        f.write_text("hello\n")
        out = self.tool.execute(path="a.py", old_content="", new_content="x")
        self.assertIn("cannot be empty", out)

    def test_missing_file(self):
        out = self.tool.execute(path="nope.py", old_content="x", new_content="y")
        self.assertIn("File not found", out)

    def test_path_outside_workspace(self):
        out = self.tool.execute(path="../outside.py", old_content="x", new_content="y")
        self.assertIn("Error", out)


class TestCodeEditASTValidation(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmpdir.name)
        self.tool = CodeEditTool(workspace=self.workspace)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_valid_python_edit_succeeds(self):
        f = self.workspace / "good.py"
        f.write_text("def foo():\n    return 1\n")
        out = self.tool.execute(path="good.py", old_content="return 1", new_content="return 42")
        self.assertIn("edited successfully", out)

    def test_edit_producing_invalid_python_is_rejected(self):
        f = self.workspace / "good.py"
        f.write_text("def foo():\n    return 1\n")
        out = self.tool.execute(path="good.py",
                                 old_content="def foo():\n    return 1",
                                 new_content="def foo(:\n    return 1")
        self.assertIn("invalid Python", out)
        # File should NOT be modified
        self.assertEqual(f.read_text(), "def foo():\n    return 1\n")

    def test_validation_disabled_allows_invalid_python(self):
        f = self.workspace / "good.py"
        f.write_text("def foo():\n    return 1\n")
        out = self.tool.execute(path="good.py",
                                 old_content="def foo():\n    return 1",
                                 new_content="def foo(:\n    return 1",
                                 validate_ast=False)
        self.assertIn("edited successfully", out)

    def test_edit_on_file_with_existing_syntax_error_rejected(self):
        f = self.workspace / "bad.py"
        f.write_text("def foo(:\n    return 1\n")
        out = self.tool.execute(path="bad.py", old_content="return 1", new_content="return 2")
        self.assertIn("Original file has a syntax error", out)

    def test_canonicalize_python(self):
        f = self.workspace / "code.py"
        f.write_text("def foo(  ):  return 1\n")
        out = self.tool.execute(
            path="code.py",
            old_content="def foo(  ):  return 1",
            new_content="def foo(  ):  return 1",
            canonicalize=True,
        )
        self.assertIn("Normalised", out)
        # ast.unparse should produce normalised output
        new_content = f.read_text()
        self.assertNotIn("  ):", new_content)

    def test_non_python_file_skips_ast_validation(self):
        f = self.workspace / "data.json"
        f.write_text('{"a": 1}\n')
        # Even with broken-looking content the edit should succeed because
        # validate_ast only fires for .py/.pyi files.
        out = self.tool.execute(path="data.json", old_content='"a": 1', new_content='"a": 2')
        self.assertIn("edited successfully", out)

    def test_pyi_file_also_validated(self):
        f = self.workspace / "stub.pyi"
        f.write_text("def foo() -> int: ...\n")
        # Make a change that produces a syntax error in stub form
        out = self.tool.execute(
            path="stub.pyi",
            old_content="def foo() -> int: ...",
            new_content="def foo() ->\n    ...",  # missing return annotation
        )
        self.assertIn("invalid Python", out)


class TestInsertLinesTool(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmpdir.name)
        self.tool = InsertLinesTool(workspace=self.workspace)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_insert_at_line(self):
        f = self.workspace / "a.py"
        f.write_text("a\nb\nc\n")
        out = self.tool.execute(path="a.py", line_number=2, content="INSERTED")
        self.assertIn("Inserted", out)
        self.assertEqual(f.read_text(), "a\nINSERTED\nb\nc\n")

    def test_insert_out_of_range(self):
        f = self.workspace / "a.py"
        f.write_text("a\nb\n")
        out = self.tool.execute(path="a.py", line_number=99, content="X")
        self.assertIn("out of range", out)

    def test_insert_at_end_appends(self):
        f = self.workspace / "a.py"
        f.write_text("a\nb\n")
        out = self.tool.execute(path="a.py", line_number=3, content="c")
        self.assertIn("Inserted", out)
        self.assertEqual(f.read_text(), "a\nb\nc\n")

    def test_missing_file(self):
        out = self.tool.execute(path="nope.py", line_number=1, content="x")
        self.assertIn("File not found", out)


if __name__ == "__main__":
    unittest.main()
