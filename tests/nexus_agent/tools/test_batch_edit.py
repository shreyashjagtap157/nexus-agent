"""Tests for the BatchEditTool — atomic multi-file search-and-replace."""

import tempfile
import unittest
from pathlib import Path

from nexus_agent.tools.batch_edit import BatchEditTool


class TestBatchEditTool(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmpdir.name)
        self.tool = BatchEditTool(workspace=self.workspace)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_single_file_edit(self):
        f = self.workspace / "a.py"
        f.write_text("x = 1\n")
        out = self.tool.execute(edits=[
            {"path": "a.py", "target_content": "x = 1", "replacement_content": "x = 99"}
        ])
        self.assertIn("succeeded", out)
        self.assertEqual(f.read_text(), "x = 99\n")

    def test_multi_file_atomic(self):
        a = self.workspace / "a.py"
        b = self.workspace / "b.py"
        a.write_text("a = 1\n")
        b.write_text("b = 1\n")
        out = self.tool.execute(edits=[
            {"path": "a.py", "target_content": "a = 1", "replacement_content": "a = 2"},
            {"path": "b.py", "target_content": "b = 1", "replacement_content": "b = 2"},
        ])
        self.assertIn("succeeded", out)
        self.assertEqual(a.read_text(), "a = 2\n")
        self.assertEqual(b.read_text(), "b = 2\n")

    def test_rollback_on_failure(self):
        a = self.workspace / "a.py"
        a.write_text("a = 1\n")
        with self.assertRaises(RuntimeError) as ctx:
            self.tool.execute(edits=[
                {"path": "a.py", "target_content": "a = 1", "replacement_content": "a = 2"},
                {"path": "missing.py", "target_content": "x", "replacement_content": "y"},
            ])
        self.assertIn("Batch edit failed", str(ctx.exception))
        # File should have been rolled back
        self.assertEqual(a.read_text(), "a = 1\n")

    def test_empty_edits(self):
        out = self.tool.execute(edits=[])
        self.assertIn("No edits", out)

    def test_missing_field_in_edit(self):
        out = self.tool.execute(edits=[
            {"path": "a.py", "target_content": "x", "replacement_content": "y"},
            {"path": "b.py", "target_content": "x"},  # missing replacement_content
        ])
        self.assertIn("Error", out)

    def test_edit_not_dict(self):
        out = self.tool.execute(edits=["not a dict"])
        self.assertIn("Error", out)

    def test_search_block_not_found(self):
        f = self.workspace / "a.py"
        f.write_text("hello\n")
        with self.assertRaises(RuntimeError):
            self.tool.execute(edits=[
                {"path": "a.py", "target_content": "missing text", "replacement_content": "X"}
            ])

    def test_ambiguous_match_rejected(self):
        f = self.workspace / "a.py"
        f.write_text("x = 1\nx = 1\nx = 1\n")
        with self.assertRaises(RuntimeError):
            self.tool.execute(edits=[
                {"path": "a.py", "target_content": "x = 1", "replacement_content": "x = 2"}
            ])

    def test_path_outside_workspace(self):
        with self.assertRaises(RuntimeError):
            self.tool.execute(edits=[
                {"path": "../escape.py", "target_content": "x", "replacement_content": "y"}
            ])


if __name__ == "__main__":
    unittest.main()
