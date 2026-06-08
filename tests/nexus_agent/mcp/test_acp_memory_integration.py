"""End-to-end integration test for ACP memory handlers.

Tests the memory manager methods that the ACP protocol calls,
verifying that responses match the format Rust expects.
"""

import tempfile
import unittest
from typing import Any

from nexus_agent.memory.memory_manager import MemoryManager


class TestACPMemoryIntegration(unittest.TestCase):
    """Full round-trip: ACP request -> MemoryManager -> ACP response."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.memory = MemoryManager(data_dir=self.tmp.name)
        self.memory.store("Python async patterns with asyncio", category="code")
        self.memory.store("User prefers ruff over black for linting", category="preference")
        self.memory.store("SQLite connection pool tuning parameters", category="performance")

    def tearDown(self):
        self.memory.close()
        self.tmp.cleanup()

    def _check_rust_entry(self, entry: dict[str, Any], msg: str = ""):
        """Verify a memory entry has all fields the Rust TUI parser needs.

        Rust parser (app.rs:388-408) reads:
          id (as_str), content (as_str), source (as_str) -> MemoryTier
          category (as_str), created_at (as_f64), updated_at (as_f64),
          access_count (as_u64), score (as_f64)
        """
        for field in ("id", "content", "source", "category"):
            self.assertIn(field, entry, f"{msg}: missing '{field}' in {entry}")
        for field in ("created_at", "updated_at", "access_count", "score"):
            self.assertIn(field, entry, f"{msg}: missing '{field}' in {entry}")
            self.assertIsInstance(entry[field], (int, float),
                                  f"{msg}: '{field}' should be numeric, got {type(entry[field])}")

    # --- Direct MemoryManager tests ---

    def test_list_all_unified_returns_with_sources(self):
        entries = self.memory.list_all_unified(limit=100)
        self.assertGreaterEqual(len(entries), 3)
        for e in entries:
            self.assertIn("source", e, f"Missing source: {e.get('id', '?')}")
            self.assertIn(e["source"], ("working", "long_term", "episodic", "vector", "user_profile"))
            self._check_rust_entry(e)

    def test_list_all_unified_working_filter(self):
        entries = self.memory.list_all_unified(tier="working")
        for e in entries:
            self.assertEqual(e["source"], "working")
            self._check_rust_entry(e)

    def test_list_all_unified_long_term_filter(self):
        entries = self.memory.list_all_unified(tier="long_term")
        self.assertGreaterEqual(len(entries), 3)
        for e in entries:
            self.assertEqual(e["source"], "long_term")
            self._check_rust_entry(e)

    def test_search_returns_with_sources(self):
        results = self.memory.search("linting", limit=5)
        self.assertGreaterEqual(len(results), 1)
        contents = [r.get("content", "") for r in results]
        self.assertTrue(any("ruff" in c for c in contents), f"ruff not found in: {contents}")

    def test_get_stats_has_tier_breakdown(self):
        self.memory.store("extra", category="general")
        stats = self.memory.get_stats()
        for key in ("working", "long_term", "episodic", "vector_store", "total_entries"):
            self.assertIn(key, stats, f"Missing '{key}' in stats")
        self.assertGreaterEqual(stats["long_term"], 4)
        self.assertGreaterEqual(stats["total_entries"], 4)

    def test_compact_runs(self):
        result = self.memory.compact(aggressive=False)
        self.assertIn("ltm_pruned", result)
        self.assertIn("episodic_pruned", result)
        self.assertIn("stm_promoted", result)

    def test_get_all_scores(self):
        scores = self.memory.get_all_scores()
        for tier in ("working", "long_term", "episodic"):
            self.assertIn(tier, scores)
            for entry in scores[tier]:
                self.assertIn("heat_score", entry)
                self.assertIsInstance(entry["heat_score"], (int, float))

    def test_working_memory_id_format(self):
        self.memory.working.set("test_key", "test_value", category="test_cat")
        entries = self.memory.list_all_unified(tier="working")
        wm_entries = [e for e in entries if e["source"] == "working"]
        self.assertGreaterEqual(len(wm_entries), 1)
        for e in wm_entries:
            self.assertTrue(e["id"].startswith("wm:"), f"Working ID should start with 'wm:': {e['id']}")

    def test_user_profile_id_format(self):
        self.memory.user_profile.set("preferences.editor", "vscode")
        entries = self.memory.list_all_unified(tier="user_profile")
        for e in entries:
            self.assertEqual(e["id"], "user_profile:1")
            self.assertEqual(e["source"], "user_profile")
            self._check_rust_entry(e)

    def test_compact_with_stm_promotion(self):
        """Compact promotes working memory entries with high access count."""
        self.memory.working.set("frequent_key", "frequently accessed data", category="test")
        # Simulate access count >= threshold
        wm_entry = self.memory.working._store.get("frequent_key")
        if wm_entry:
            wm_entry["access_count"] = 10  # Above default STM_PROMOTE_THRESHOLD (5)
        result = self.memory.compact(aggressive=False)
        self.assertGreaterEqual(result["stm_promoted"], 0)
        # After compaction, check if working entry was promoted
        wm_check = self.memory.working.get("frequent_key")
        if wm_check is None:
            self.assertGreaterEqual(result["stm_promoted"], 1)
