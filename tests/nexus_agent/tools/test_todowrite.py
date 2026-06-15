"""Tests for `tools/todowrite.py` — TodoStore and TodoWriteTool."""

import json
import tempfile
import unittest
from pathlib import Path

from nexus_agent.tools.todowrite import (
    Todo,
    TodoPriority,
    TodoStatus,
    TodoStore,
    TodoWriteTool,
    _coerce_priority,
    _coerce_status,
    _slugify,
    format_todo_list,
)


class TestCoerce(unittest.TestCase):
    """String→enum coercion with aliases."""

    def test_status_aliases(self):
        self.assertEqual(_coerce_status("pending"), TodoStatus.PENDING)
        self.assertEqual(_coerce_status("todo"), TodoStatus.PENDING)
        self.assertEqual(_coerce_status("open"), TodoStatus.PENDING)
        self.assertEqual(_coerce_status("doing"), TodoStatus.IN_PROGRESS)
        self.assertEqual(_coerce_status("wip"), TodoStatus.IN_PROGRESS)
        self.assertEqual(_coerce_status("done"), TodoStatus.COMPLETED)
        self.assertEqual(_coerce_status("finished"), TodoStatus.COMPLETED)
        self.assertEqual(_coerce_status("skipped"), TodoStatus.CANCELLED)
        self.assertEqual(_coerce_status("canceled"), TodoStatus.CANCELLED)
        # Whitespace and case insensitive
        self.assertEqual(_coerce_status("  DONE  "), TodoStatus.COMPLETED)
        # Unknown falls back to pending
        self.assertEqual(_coerce_status("nonsense"), TodoStatus.PENDING)

    def test_status_passthrough(self):
        s = TodoStatus.IN_PROGRESS
        self.assertIs(_coerce_status(s), s)

    def test_status_non_string_defaults(self):
        self.assertEqual(_coerce_status(None), TodoStatus.PENDING)
        self.assertEqual(_coerce_status(42), TodoStatus.PENDING)

    def test_priority_aliases(self):
        self.assertEqual(_coerce_priority("low"), TodoPriority.LOW)
        self.assertEqual(_coerce_priority("med"), TodoPriority.MEDIUM)
        self.assertEqual(_coerce_priority("high"), TodoPriority.HIGH)
        self.assertEqual(_coerce_priority("urgent"), TodoPriority.CRITICAL)
        self.assertEqual(_coerce_priority("blocker"), TodoPriority.CRITICAL)
        self.assertEqual(_coerce_priority("nonsense"), TodoPriority.MEDIUM)
        self.assertEqual(_coerce_priority(None), TodoPriority.MEDIUM)


class TestSlugify(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(_slugify("Fix Login Bug"), "fix-login-bug")

    def test_strips_specials(self):
        self.assertEqual(_slugify("Hello, World!"), "hello-world")

    def test_collapse_dashes(self):
        self.assertEqual(_slugify("a   b   c"), "a-b-c")

    def test_truncates(self):
        long = "a" * 100
        s = _slugify(long)
        self.assertEqual(len(s), 40)

    def test_empty_fallback(self):
        self.assertEqual(_slugify(""), "todo")
        self.assertEqual(_slugify("!!!"), "todo")


class TestTodoDataclass(unittest.TestCase):
    def test_to_dict_uses_enum_values(self):
        t = Todo(id="abc", content="x", status=TodoStatus.IN_PROGRESS, priority=TodoPriority.HIGH)
        d = t.to_dict()
        self.assertEqual(d["status"], "in_progress")
        self.assertEqual(d["priority"], "high")
        self.assertEqual(d["id"], "abc")
        self.assertEqual(d["content"], "x")

    def test_from_dict_roundtrip(self):
        t = Todo(id="abc", content="x", status=TodoStatus.COMPLETED, priority=TodoPriority.CRITICAL)
        d = t.to_dict()
        t2 = Todo.from_dict(d)
        self.assertEqual(t2.id, t.id)
        self.assertEqual(t2.content, t.content)
        self.assertEqual(t2.status, t.status)
        self.assertEqual(t2.priority, t.priority)

    def test_from_dict_handles_bad_data(self):
        # Bad status falls back to pending
        t = Todo.from_dict({"id": "x", "content": "x", "status": "garbage"})
        self.assertEqual(t.status, TodoStatus.PENDING)
        # Missing id gets generated
        t = Todo.from_dict({"content": "x"})
        self.assertTrue(t.id)


class TestTodoStore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.persist = Path(self.tmpdir.name) / "todos.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_add_assigns_id(self):
        s = TodoStore()
        t = s.add("First")
        self.assertTrue(t.id)
        self.assertEqual(t.content, "First")
        self.assertEqual(t.status, TodoStatus.PENDING)
        self.assertEqual(t.priority, TodoPriority.MEDIUM)

    def test_add_with_explicit_id(self):
        s = TodoStore()
        t = s.add("x", todo_id="custom-1")
        self.assertEqual(t.id, "custom-1")

    def test_add_collision_disambiguates(self):
        s = TodoStore()
        t1 = s.add("x", todo_id="dup")
        t2 = s.add("x", todo_id="dup")
        self.assertNotEqual(t1.id, t2.id)
        self.assertTrue(t2.id.startswith("dup-"))

    def test_update_status(self):
        s = TodoStore()
        t = s.add("a")
        updated = s.update(t.id, status="doing")
        self.assertEqual(updated.status, TodoStatus.IN_PROGRESS)

    def test_update_priority(self):
        s = TodoStore()
        t = s.add("a")
        updated = s.update(t.id, priority="critical")
        self.assertEqual(updated.priority, TodoPriority.CRITICAL)

    def test_update_content(self):
        s = TodoStore()
        t = s.add("a")
        updated = s.update(t.id, content="b")
        self.assertEqual(updated.content, "b")

    def test_update_unknown_returns_none(self):
        s = TodoStore()
        self.assertIsNone(s.update("nope", status="done"))

    def test_update_no_changes(self):
        s = TodoStore()
        t = s.add("a")
        updated = s.update(t.id)
        self.assertIsNotNone(updated)

    def test_remove(self):
        s = TodoStore()
        t = s.add("a")
        self.assertTrue(s.remove(t.id))
        self.assertFalse(s.remove(t.id))

    def test_get(self):
        s = TodoStore()
        t = s.add("a")
        self.assertEqual(s.get(t.id).id, t.id)
        self.assertIsNone(s.get("missing"))

    def test_list_sorts_by_priority(self):
        s = TodoStore()
        s.add("low", priority="low")
        s.add("crit", priority="critical")
        s.add("high", priority="high")
        todos = s.list()
        self.assertEqual([t.priority for t in todos], [
            TodoPriority.CRITICAL, TodoPriority.HIGH, TodoPriority.LOW,
        ])

    def test_list_filter_by_status(self):
        s = TodoStore()
        a = s.add("a")
        b = s.add("b")
        s.update(a.id, status="done")
        s.update(b.id, status="in_progress")
        pending = s.list(status="pending")
        self.assertEqual(pending, [])
        completed = s.list(status="completed")
        self.assertEqual([t.id for t in completed], [a.id])

    def test_list_filter_by_priority(self):
        s = TodoStore()
        a = s.add("a", priority="high")
        s.add("b", priority="low")
        high = s.list(priority="high")
        self.assertEqual([t.id for t in high], [a.id])

    def test_clear_completed(self):
        s = TodoStore()
        a = s.add("a")
        b = s.add("b")
        s.update(a.id, status="done")
        s.update(b.id, status="cancelled")
        n = s.clear_completed()
        self.assertEqual(n, 2)
        self.assertEqual(s.counts()["total"], 0)

    def test_clear_completed_keeps_pending(self):
        s = TodoStore()
        a = s.add("a")
        s.add("b")
        s.update(a.id, status="done")
        n = s.clear_completed()
        self.assertEqual(n, 1)
        self.assertEqual(s.counts()["total"], 1)

    def test_clear_all(self):
        s = TodoStore()
        s.add("a")
        s.add("b")
        n = s.clear_all()
        self.assertEqual(n, 2)
        self.assertEqual(s.counts()["total"], 0)

    def test_counts(self):
        s = TodoStore()
        a = s.add("a")
        s.add("b")
        s.update(a.id, status="done")
        c = s.counts()
        self.assertEqual(c["total"], 2)
        self.assertEqual(c["completed"], 1)
        self.assertEqual(c["pending"], 1)

    # ---- persistence ----

    def test_persist_on_add(self):
        s = TodoStore(persist_path=self.persist)
        s.add("persistent")
        self.assertTrue(self.persist.exists())
        data = json.loads(self.persist.read_text(encoding="utf-8"))
        self.assertEqual(data["version"], 1)
        self.assertEqual(len(data["todos"]), 1)
        self.assertEqual(data["todos"][0]["content"], "persistent")

    def test_load_from_disk(self):
        s1 = TodoStore(persist_path=self.persist)
        s1.add("loaded", priority="high")
        s2 = TodoStore(persist_path=self.persist)
        todos = s2.list()
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0].content, "loaded")
        self.assertEqual(todos[0].priority, TodoPriority.HIGH)

    def test_load_corrupt_file_does_not_crash(self):
        self.persist.write_text("not json", encoding="utf-8")
        s = TodoStore(persist_path=self.persist)
        # Should not raise; store is just empty
        self.assertEqual(s.counts()["total"], 0)

    def test_persist_atomic_write(self):
        s = TodoStore(persist_path=self.persist)
        s.add("x")
        # tmp file should not exist after replace
        tmp = self.persist.with_suffix(self.persist.suffix + ".tmp")
        self.assertFalse(tmp.exists())


class TestFormatTodoList(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(format_todo_list([]), "(no todos)")

    def test_one_pending(self):
        t = Todo(id="a", content="do thing", status=TodoStatus.PENDING, priority=TodoPriority.HIGH)
        out = format_todo_list([t])
        self.assertIn("[ ]", out)
        self.assertIn("HIGH", out)
        self.assertIn("[a]", out)
        self.assertIn("do thing", out)

    def test_in_progress_marker(self):
        t = Todo(id="a", content="x", status=TodoStatus.IN_PROGRESS)
        out = format_todo_list([t])
        self.assertIn("[>]", out)

    def test_completed_marker(self):
        t = Todo(id="a", content="x", status=TodoStatus.COMPLETED)
        out = format_todo_list([t])
        self.assertIn("[x]", out)

    def test_cancelled_marker(self):
        t = Todo(id="a", content="x", status=TodoStatus.CANCELLED)
        out = format_todo_list([t])
        self.assertIn("[-]", out)

    def test_notes_indented(self):
        t = Todo(id="a", content="x", notes="line 1\nline 2")
        out = format_todo_list([t])
        self.assertIn("| line 1", out)
        self.assertIn("| line 2", out)


class TestTodoWriteTool(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.persist = Path(self.tmpdir.name) / "todos.json"
        self.tool = TodoWriteTool(persist_path=self.persist)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_metadata(self):
        self.assertEqual(self.tool.name, "todowrite")
        self.assertEqual(self.tool.permission_level, "read-write")
        self.assertIn("action", self.tool.required_params)

    def test_add(self):
        out = self.tool.execute(action="add", content="do it")
        self.assertIn("Added todo", out)
        self.assertIn("do it", out)

    def test_add_without_content_errors(self):
        out = self.tool.execute(action="add")
        self.assertIn("Error", out)

    def test_update(self):
        self.tool.execute(action="add", content="x")
        todos = self.tool.store.list()
        tid = todos[0].id
        out = self.tool.execute(action="update", todo_id=tid, status="done")
        self.assertIn("Updated", out)
        self.assertEqual(self.tool.store.get(tid).status, TodoStatus.COMPLETED)

    def test_update_unknown_id(self):
        out = self.tool.execute(action="update", todo_id="missing", status="done")
        self.assertIn("Error", out)

    def test_remove(self):
        self.tool.execute(action="add", content="x")
        tid = self.tool.store.list()[0].id
        out = self.tool.execute(action="remove", todo_id=tid)
        self.assertIn("Removed", out)
        # second remove fails
        out = self.tool.execute(action="remove", todo_id=tid)
        self.assertIn("Error", out)

    def test_list(self):
        self.tool.execute(action="add", content="a")
        self.tool.execute(action="add", content="b", priority="critical")
        out = self.tool.execute(action="list")
        self.assertIn("Todos", out)
        self.assertIn("a", out)
        self.assertIn("b", out)
        self.assertIn("CRIT", out)

    def test_list_empty(self):
        out = self.tool.execute(action="list")
        self.assertIn("(no todos)", out)

    def test_get(self):
        self.tool.execute(action="add", content="a")
        tid = self.tool.store.list()[0].id
        out = self.tool.execute(action="get", todo_id=tid)
        self.assertIn("a", out)

    def test_get_missing(self):
        out = self.tool.execute(action="get", todo_id="nope")
        self.assertIn("Error", out)

    def test_clear_completed(self):
        self.tool.execute(action="add", content="a")
        self.tool.execute(action="add", content="b")
        tid = self.tool.store.list()[0].id
        self.tool.execute(action="update", todo_id=tid, status="done")
        out = self.tool.execute(action="clear_completed")
        self.assertIn("Cleared 1", out)

    def test_clear_all(self):
        self.tool.execute(action="add", content="a")
        out = self.tool.execute(action="clear_all")
        self.assertIn("Cleared all 1", out)

    def test_unknown_action(self):
        out = self.tool.execute(action="nonsense")
        self.assertIn("Error", out)

    def test_no_action(self):
        out = self.tool.execute(action="")
        self.assertIn("Error", out)


if __name__ == "__main__":
    unittest.main()
