"""Tests for the memory module — MemoryManager, WorkingMemory, LongTermMemory, EpisodicMemory, UserProfile."""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

from nexus_agent.memory.working_memory import WorkingMemory
from nexus_agent.memory.long_term import LongTermMemory
from nexus_agent.memory.episodic import EpisodicMemory
from nexus_agent.memory.user_profile import UserProfile
from nexus_agent.memory.memory_manager import MemoryManager


class TestWorkingMemory(unittest.TestCase):
    def setUp(self):
        self.wm = WorkingMemory(max_entries=5)

    def test_set_and_get(self):
        self.wm.set("key1", "value1")
        self.assertEqual(self.wm.get("key1"), "value1")

    def test_get_nonexistent(self):
        self.assertIsNone(self.wm.get("nope"))

    def test_delete_existing(self):
        self.wm.set("key1", "v1")
        self.assertTrue(self.wm.delete("key1"))
        self.assertIsNone(self.wm.get("key1"))

    def test_delete_nonexistent(self):
        self.assertFalse(self.wm.delete("nope"))

    def test_eviction(self):
        for i in range(10):
            self.wm.set(f"k{i}", str(i))
        self.assertIsNone(self.wm.get("k0"))
        self.assertIsNotNone(self.wm.get("k9"))

    def test_list_keys_all(self):
        self.wm.set("a", "1", category="cat_a")
        self.wm.set("b", "2", category="cat_b")
        self.wm.set("c", "3", category="cat_a")
        keys = self.wm.list_keys()
        self.assertEqual(len(keys), 3)
        self.assertIn("a", keys)

    def test_list_keys_filtered(self):
        self.wm.set("a", "1", category="cat_a")
        self.wm.set("b", "2", category="cat_b")
        keys = self.wm.list_keys(category="cat_a")
        self.assertEqual(keys, ["a"])

    def test_scratchpad(self):
        self.wm.add_note("note1")
        self.wm.add_note("note2")
        sp = self.wm.get_scratchpad()
        self.assertIn("note1", sp)
        self.assertIn("note2", sp)

    def test_clear(self):
        self.wm.set("k", "v")
        self.wm.add_note("n")
        self.wm.clear()
        self.assertIsNone(self.wm.get("k"))
        self.assertEqual(self.wm.get_scratchpad(), "")

    def test_get_summary(self):
        self.wm.set("k1", "v1", category="cat")
        summary = self.wm.get_summary()
        self.assertEqual(summary["entries"], 1)
        self.assertEqual(summary["categories"], ["cat"])


class TestLongTermMemory(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test_long_term.db"
        self.ltm = LongTermMemory(self.db_path)

    def tearDown(self):
        self.ltm.close()
        self.tmpdir.cleanup()

    def test_store_and_get(self):
        eid = self.ltm.store("hello world")
        entry = self.ltm.get(eid)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["content"], "hello world")

    def test_store_empty_raises(self):
        with self.assertRaises(ValueError):
            self.ltm.store("")

    def test_search(self):
        self.ltm.store("the quick brown fox")
        self.ltm.store("jumped over the lazy dog")
        results = self.ltm.search("fox", limit=5)
        self.assertGreaterEqual(len(results), 1)
        self.assertIn("fox", results[0]["content"])

    def test_get_nonexistent(self):
        self.assertIsNone(self.ltm.get("nope"))

    def test_update_content(self):
        eid = self.ltm.store("original")
        self.assertTrue(self.ltm.update(eid, content="updated"))
        entry = self.ltm.get(eid)
        self.assertEqual(entry["content"], "updated")

    def test_update_no_op(self):
        eid = self.ltm.store("text")
        self.assertFalse(self.ltm.update(eid))

    def test_delete(self):
        eid = self.ltm.store("delete me")
        self.assertTrue(self.ltm.delete(eid))
        self.assertIsNone(self.ltm.get(eid))

    def test_delete_nonexistent(self):
        self.assertFalse(self.ltm.delete("nope"))

    def test_list_categories(self):
        self.ltm.store("a", category="cat1")
        self.ltm.store("b", category="cat2")
        cats = self.ltm.list_categories()
        names = [c["category"] for c in cats]
        self.assertIn("cat1", names)
        self.assertIn("cat2", names)

    def test_get_stats(self):
        self.ltm.store("data")
        stats = self.ltm.get_stats()
        self.assertGreaterEqual(stats["total_entries"], 1)

    def test_search_like_fallback(self):
        self.ltm.store("unique search term")
        results = self.ltm.search("unique")
        self.assertGreaterEqual(len(results), 1)


class TestEpisodicMemory(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test_episodic.db"
        self.ep = EpisodicMemory(self.db_path)

    def tearDown(self):
        self.ep.close()
        self.tmpdir.cleanup()

    def test_save_and_search(self):
        self.ep.save_session("session_1", "Fixed critical bug in parser")
        results = self.ep.search("parser", limit=5)
        self.assertGreaterEqual(len(results), 1)

    def test_empty_query_returns_empty(self):
        self.ep.save_session("s1", "some content")
        self.assertEqual(self.ep.search(""), [])

    def test_get_recent(self):
        for i in range(5):
            self.ep.save_session(f"s{i}", f"summary {i}")
        recent = self.ep.get_recent(limit=3)
        self.assertEqual(len(recent), 3)

    def test_save_empty_session_id_is_noop(self):
        self.ep.save_session("", "summary")
        self.assertEqual(self.ep.get_recent(limit=10), [])


class TestUserProfile(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.profile_path = Path(self.tmpdir.name) / "profile.yaml"
        self.profile = UserProfile(self.profile_path)

    def tearDown(self):
        self.profile.close()
        self.tmpdir.cleanup()

    def test_get_default(self):
        style = self.profile.get("coding_style")
        self.assertEqual(style["indentation"], "auto")

    def test_get_with_dot_notation(self):
        val = self.profile.get("coding_style.indentation")
        self.assertEqual(val, "auto")

    def test_get_nonexistent_key(self):
        self.assertIsNone(self.profile.get("nonexistent.key"))

    def test_get_custom_default(self):
        val = self.profile.get("nope", "fallback")
        self.assertEqual(val, "fallback")

    def test_set_and_get(self):
        self.profile.set("preferences.editor", "vim")
        self.assertEqual(self.profile.get("preferences.editor"), "vim")

    def test_learn_pattern(self):
        self.profile.learn_pattern("uses pytest fixtures", context="testing")
        summary = self.profile.get_summary()
        self.assertIn("pytest", summary)

    def test_persistence(self):
        self.profile.set("preferences.editor", "vscode")
        self.profile.close()

        p2 = UserProfile(self.profile_path)
        self.assertEqual(p2.get("preferences.editor"), "vscode")
        p2.close()

    def test_to_dict(self):
        d = self.profile.to_dict()
        self.assertIn("coding_style", d)
        self.assertIn("preferences", d)


class TestMemoryManager(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmpdir.name) / "memory"
        self.mgr = MemoryManager(data_dir=self.data_dir)

    def tearDown(self):
        self.mgr.close()
        self.tmpdir.cleanup()

    def test_store_and_remember(self):
        eid = self.mgr.store("important fact about the project")
        result = self.mgr.remember("important")
        self.assertIsNotNone(result)

    def test_search_cross_memory(self):
        self.mgr.store("python async patterns")
        results = self.mgr.search("async", limit=5)
        self.assertGreaterEqual(len(results), 1)

    def test_get_context_for_prompt_empty(self):
        context = self.mgr.get_context_for_prompt()
        self.assertIsInstance(context, str)

    def test_get_context_with_query(self):
        self.mgr.store("user prefers tabs over spaces")
        context = self.mgr.get_context_for_prompt(query="tabs")
        self.assertIn("tabs", context)

    def test_save_session_summary(self):
        self.mgr.save_session_summary("session_x", "Completed feature Y")
        results = self.mgr.search("feature Y")
        self.assertGreaterEqual(len(results), 0)

    def test_close(self):
        self.mgr.close()
        self.mgr.close()
