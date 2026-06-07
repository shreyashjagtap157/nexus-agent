"""Tests for `tools/memory.py` and the new `MemoryManager` self-edit methods."""

import tempfile
import unittest
from pathlib import Path

from nexus_agent.memory.long_term import LongTermMemory
from nexus_agent.memory.memory_manager import MemoryManager
from nexus_agent.tools.memory import MemoryTool, _coerce_limit


class TestCoerceLimit(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(_coerce_limit("10"), 10)

    def test_invalid_uses_default(self):
        self.assertEqual(_coerce_limit("garbage"), 10)

    def test_negative_clamps_to_zero(self):
        self.assertEqual(_coerce_limit(-5), 0)

    def test_above_max_clamps(self):
        self.assertEqual(_coerce_limit(999999, default=10), 1000)


class TestLongTermListAll(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "lt.db"
        self.lt = LongTermMemory(self.db)

    def tearDown(self):
        self.lt.close()
        self.tmp.cleanup()

    def test_list_all_empty(self):
        self.assertEqual(self.lt.list_all(), [])

    def test_list_all_returns_newest_first(self):
        a = self.lt.store("first")
        b = self.lt.store("second")
        c = self.lt.store("third")
        items = self.lt.list_all()
        # Newest first
        self.assertEqual([i["id"] for i in items], [c, b, a])

    def test_list_all_with_limit_offset(self):
        ids = [self.lt.store(f"item {i}") for i in range(5)]
        items = self.lt.list_all(limit=2, offset=1)
        # Newest first → [4, 3, 2, 1, 0], offset 1, limit 2 → [3, 2]
        self.assertEqual([i["id"] for i in items], [ids[3], ids[2]])

    def test_list_all_filter_by_category(self):
        self.lt.store("a", category="x")
        self.lt.store("b", category="y")
        self.lt.store("c", category="x")
        x_items = self.lt.list_all(category="x")
        self.assertEqual(len(x_items), 2)
        self.assertTrue(all(i["category"] == "x" for i in x_items))


class TestMemoryManagerSelfEdit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mm = MemoryManager(data_dir=self.tmp.name)

    def tearDown(self):
        self.mm.close()
        self.tmp.cleanup()

    def test_update_existing(self):
        eid = self.mm.store("v1", category="c1")
        self.assertTrue(self.mm.update(eid, content="v2"))
        self.assertEqual(self.mm.get(eid)["content"], "v2")

    def test_update_category(self):
        eid = self.mm.store("x", category="a")
        self.mm.update(eid, category="b")
        self.assertEqual(self.mm.get(eid)["category"], "b")

    def test_update_no_args_returns_false(self):
        eid = self.mm.store("x")
        self.assertFalse(self.mm.update(eid))

    def test_update_unknown_returns_false(self):
        self.assertFalse(self.mm.update("nope", content="y"))

    def test_forget_existing(self):
        eid = self.mm.store("x")
        self.assertTrue(self.mm.forget(eid))
        self.assertIsNone(self.mm.get(eid))

    def test_forget_unknown(self):
        self.assertFalse(self.mm.forget("nope"))

    def test_get_existing(self):
        eid = self.mm.store("hello")
        m = self.mm.get(eid)
        self.assertEqual(m["content"], "hello")

    def test_get_unknown(self):
        self.assertIsNone(self.mm.get("nope"))

    def test_list_all_default(self):
        self.mm.store("a")
        self.mm.store("b")
        items = self.mm.list_all()
        self.assertEqual(len(items), 2)

    def test_list_all_with_category_filter(self):
        self.mm.store("a", category="x")
        self.mm.store("b", category="y")
        x = self.mm.list_all(category="x")
        self.assertEqual(len(x), 1)
        self.assertEqual(x[0]["category"], "x")

    def test_get_stats(self):
        self.mm.store("a", category="x")
        self.mm.store("b", category="x")
        self.mm.store("c", category="y")
        s = self.mm.get_stats()
        self.assertEqual(s["total_entries"], 3)
        self.assertEqual(s["categories"], 2)


class TestMemoryTool(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mm = MemoryManager(data_dir=self.tmp.name)
        self.tool = MemoryTool(memory_manager=self.mm)

    def tearDown(self):
        self.mm.close()
        self.tmp.cleanup()

    def test_metadata(self):
        self.assertEqual(self.tool.name, "memory")
        self.assertEqual(self.tool.permission_level, "read-write")
        self.assertIn("action", self.tool.required_params)

    def test_unbound_returns_error(self):
        t = MemoryTool()  # no manager
        out = t.execute(action="list")
        self.assertIn("not configured", out)

    def test_list_empty(self):
        out = self.tool.execute(action="list")
        self.assertIn("no memories", out)

    def test_list_with_entries(self):
        self.mm.store("alpha", category="x")
        self.mm.store("beta", category="y")
        out = self.tool.execute(action="list")
        self.assertIn("alpha", out)
        self.assertIn("beta", out)
        self.assertIn("2 memories", out)

    def test_list_filter_category(self):
        self.mm.store("alpha-marker", category="x")
        self.mm.store("beta-marker", category="y")
        out = self.tool.execute(action="list", category="x")
        self.assertIn("alpha-marker", out)
        self.assertNotIn("beta-marker", out)
        self.assertIn("category 'x'", out)

    def test_get(self):
        eid = self.mm.store("hello world")
        out = self.tool.execute(action="get", entry_id=eid)
        self.assertIn("hello world", out)
        self.assertIn(eid, out)

    def test_get_missing(self):
        out = self.tool.execute(action="get", entry_id="nope")
        self.assertIn("Error", out)

    def test_get_no_id(self):
        out = self.tool.execute(action="get")
        self.assertIn("Error", out)

    def test_store(self):
        out = self.tool.execute(action="store", content="remember this")
        self.assertIn("Stored", out)
        # Verify it's actually stored
        items = self.mm.list_all()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["content"], "remember this")

    def test_store_with_category(self):
        out = self.tool.execute(
            action="store", content="x", category="code_pattern"
        )
        self.assertIn("code_pattern", out)

    def test_store_empty_content(self):
        out = self.tool.execute(action="store", content="")
        self.assertIn("Error", out)
        out = self.tool.execute(action="store", content="   ")
        self.assertIn("Error", out)

    def test_update_content(self):
        eid = self.mm.store("v1")
        out = self.tool.execute(
            action="update", entry_id=eid, content="v2"
        )
        self.assertIn("Updated", out)
        self.assertEqual(self.mm.get(eid)["content"], "v2")

    def test_update_category(self):
        eid = self.mm.store("x", category="a")
        self.tool.execute(action="update", entry_id=eid, category="b")
        self.assertEqual(self.mm.get(eid)["category"], "b")

    def test_update_no_args(self):
        eid = self.mm.store("x")
        out = self.tool.execute(action="update", entry_id=eid)
        self.assertIn("Error", out)

    def test_update_no_id(self):
        out = self.tool.execute(action="update", content="x")
        self.assertIn("Error", out)

    def test_update_unknown_id(self):
        out = self.tool.execute(action="update", entry_id="nope", content="x")
        self.assertIn("Error", out)

    def test_update_empty_content(self):
        eid = self.mm.store("x")
        out = self.tool.execute(
            action="update", entry_id=eid, content=""
        )
        self.assertIn("Error", out)

    def test_forget(self):
        eid = self.mm.store("x")
        out = self.tool.execute(action="forget", entry_id=eid)
        self.assertIn("Forgot", out)
        self.assertIsNone(self.mm.get(eid))

    def test_forget_unknown(self):
        out = self.tool.execute(action="forget", entry_id="nope")
        self.assertIn("Error", out)

    def test_forget_no_id(self):
        out = self.tool.execute(action="forget")
        self.assertIn("Error", out)

    def test_stats(self):
        self.mm.store("a", category="x")
        self.mm.store("b", category="y")
        out = self.tool.execute(action="stats")
        self.assertIn("Total memories: 2", out)
        self.assertIn("Categories: 2", out)
        self.assertIn("x=", out)
        self.assertIn("y=", out)

    def test_unknown_action(self):
        out = self.tool.execute(action="nonsense")
        self.assertIn("Error", out)

    def test_no_action(self):
        out = self.tool.execute(action="")
        self.assertIn("Error", out)

    def test_set_memory_late_init(self):
        t = MemoryTool()
        self.assertIn("not configured", t.execute(action="list"))
        t.set_memory(self.mm)
        out = t.execute(action="list")
        self.assertIn("no memories", out)

    def test_limit_clamps(self):
        for i in range(20):
            self.mm.store(f"item {i}")
        out = self.tool.execute(action="list", limit=5)
        # The header says "5 memories"
        self.assertIn("5 memories", out)

    def test_repr(self):
        r = repr(self.tool)
        self.assertIn("Tool:memory", r)
        # unbound version
        r2 = repr(MemoryTool())
        self.assertIn("unbound", r2)


if __name__ == "__main__":
    unittest.main()
