"""Integration tests for /memory vector CLI commands.

Tests the AgentCommandsMixin handlers both directly (``_run_vector()``)
and through the command dispatcher chain (``_cmd()`` / ``_cmd_memory()``).

Test classes:
- ``TestVectorCommands`` — Direct handler tests via ``_cmd_memory_vector()``
  (8 cross-scope isolation tests: filter, list, query, delete, clear,
  rebuild, migrate, categories)
- ``TestVectorCommandsViaDispatcher`` — Full dispatch path via ``_cmd_memory()``
  (10 cross-scope isolation tests: filter, stats, list, clear, delete, query,
  rebuild, migrate, categories, download)

Each cross-scope test seeds both stores (2 global, 3 project) and verifies
scope isolation through direct count assertions after project-scoped
operations.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from nexus_agent.memory.memory_manager import MemoryManager
from nexus_agent.cli.commands.agent_mixin import AgentCommandsMixin


class _MockApp(AgentCommandsMixin):
    """Minimal app-like object that satisfies the mixin's attribute needs."""

    def __init__(self, memory: MemoryManager, project_memory: MemoryManager):
        self._memory = memory
        self._project_memory = project_memory
        self._vector_use_project = False

        # Mock renderer and console
        self.r = MagicMock()
        self.console = MagicMock()

        # Track messages for assertions
        self.messages: list[str] = []
        self.errors: list[str] = []

        def _system_msg(msg: str) -> None:
            self.messages.append(msg)

        def _error(msg: str) -> None:
            self.errors.append(msg)

        self.r.system_message = _system_msg
        self.r.error = _error


class TestVectorCommands(unittest.TestCase):
    """Integration tests for /memory vector CLI commands.

    Tests exercise the handlers directly via ``_run_vector()`` which
    simulates ``_cmd_memory_vector()`` dispatch.

    Cross-scope isolation tests (seed both stores, verify scope isolation):
    - ``test_filter_cross_scope_isolation`` — filter with all 4 ``--project``
      flag placements (default, before, after, short ``-p``)
    - ``test_list_cross_scope_isolation`` — list default, ``--project list``,
      and ``list --project``
    - ``test_query_cross_scope_isolation`` — query default,
      ``--project query <text>``, and ``query --project <text>``
    - ``test_delete_cross_scope_isolation`` — delete with ``--project``
      before and after subcommand, verifying store isolation
    - ``test_clear_cross_scope_isolation`` — ``--project clear`` clears only
      project store; default ``clear`` clears only global
    - ``test_rebuild_cross_scope_isolation`` — rebuild default vs
      ``--project`` scope, non-destructive
    - ``test_migrate_cross_scope_isolation`` — ``--project`` migrate
      populates only project vector; default only global
    - ``test_categories_cross_scope_isolation`` — categories default
      vs ``--project`` scope via console.print scope labels

    Each test seeds both stores (2 global entries, 3 project entries),
    verifies isolation through direct count assertions after each
    project-scoped operation, and confirms counts remain unchanged.
    """

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmpdir.name) / "memory"
        self.project_data_dir = Path(self.tmpdir.name) / "project_memory"

        self.memory = MemoryManager(data_dir=self.data_dir)
        self.project_memory = MemoryManager(data_dir=self.project_data_dir)

        self.app = _MockApp(self.memory, self.project_memory)

    def tearDown(self):
        self.memory.close()
        self.project_memory.close()
        self.tmpdir.cleanup()

    # ── Helpers ──────────────────────────────────────────────────────

    def _seed(self, texts: list[tuple[str, str]], target: MemoryManager | None = None):
        """Store entries in long-term memory and migrate to vector store."""
        mgr = target or self.memory
        for content, category in texts:
            mgr.long_term.store(content, category=category)
        self._migrate(mgr)

    def _migrate(self, target: MemoryManager | None = None):
        """Replicate /memory vector migrate logic."""
        mgr = target or self.memory
        vs = mgr.vector
        if vs is None:
            return
        stats = mgr.long_term.get_stats()
        total = stats.get("total_entries", 0)
        offset = 0
        PAGE_SIZE = 50
        while offset < total:
            entries = mgr.long_term.list_all(limit=PAGE_SIZE, offset=offset)
            if not entries:
                break
            for entry in entries:
                eid = entry.get("id", "")
                content = entry.get("content", "")
                category = entry.get("category", "general")
                if not content or not content.strip():
                    continue
                if vs.get(eid):
                    continue
                vs.store(eid, content, category=category)
            offset += PAGE_SIZE

    def _run_vector(self, args: str):
        """Simulate what happens when /memory vector <args> is typed."""
        self.app._cmd_memory_vector(args)

    # ── stats ────────────────────────────────────────────────────────

    def test_stats_empty(self):
        self._run_vector("stats")
        # Stats renders a Rich Table — verify it ran without error
        self.assertTrue(
            self.app.console.print.called,
            "Expected stats to print output",
        )
        self.assertFalse(self.app.errors)

    def test_stats_with_entries(self):
        self._seed([("python async patterns", "code")])
        self._run_vector("stats")
        self.assertTrue(
            self.app.console.print.called,
            "Expected stats to print entries table",
        )
        self.assertFalse(self.app.errors)

    def test_stats_project_scope(self):
        self._seed([("project config", "config")], target=self.project_memory)
        self._run_vector("--project stats")
        self.assertTrue(
            self.app.console.print.called,
            "Expected stats to print output",
        )
        self.assertFalse(self.app.errors)

    # ── query ────────────────────────────────────────────────────────

    def test_query_no_args(self):
        self._run_vector("query")
        self.assertTrue(
            any("usage" in m.lower() for m in self.app.messages),
            f"Expected usage message: {self.app.messages}",
        )

    def test_query_empty_store(self):
        self._run_vector("query async python")
        self.assertTrue(
            any("semantic matches" in m.lower() for m in self.app.messages) or
            any("not available" in m.lower() for m in self.app.messages),
            f"Expected no-matches message: {self.app.messages}",
        )

    def test_query_returns_results(self):
        self._seed([
            ("python async await programming", "code"),
            ("javascript event loop callback", "code"),
        ])
        self.app.messages.clear()
        self._run_vector("query python async")
        # Should find at least one result (printed via console, not system_message)
        self.assertTrue(
            any("python" in str(call) for call in self.app.console.print.call_args_list),
            "Expected query results to be printed to console",
        )

    def test_query_project_scope(self):
        self._seed([("project data", "config")], target=self.project_memory)
        self._run_vector("--project query project")
        self.assertTrue(
            any("project" in str(call).lower() for call in self.app.console.print.call_args_list),
            "Expected project label in query output",
        )

    def test_query_project_flag_after_subcommand(self):
        """query --project <text> should target project scope."""
        self._seed([("proj content", "config")], target=self.project_memory)
        self._run_vector("query --project proj")
        self.assertTrue(
            any("project" in str(call).lower() for call in self.app.console.print.call_args_list),
            "Expected project label with 'query --project'",
        )
        self.assertFalse(self.app.errors)

    def test_query_project_short_form_after_subcommand(self):
        """query -p <text> should target project scope."""
        self._seed([("proj content", "config")], target=self.project_memory)
        self._run_vector("query -p proj")
        self.assertTrue(
            any("project" in str(call).lower() for call in self.app.console.print.call_args_list),
            "Expected project label with 'query -p'",
        )
        self.assertFalse(self.app.errors)

    def test_query_project_flag_after_without_text(self):
        """query --project without text should show usage."""
        self._run_vector("query --project")
        self.assertTrue(
            any("usage" in m.lower() for m in self.app.messages),
            f"Expected usage message: {self.app.messages}",
        )

    # ── list ─────────────────────────────────────────────────────────

    def test_list_empty(self):
        self._run_vector("list")
        self.assertTrue(
            any("empty" in m.lower() for m in self.app.messages),
            f"Expected empty message: {self.app.messages}",
        )

    def test_list_with_entries(self):
        self._seed([("entry one", "cat_a"), ("entry two", "cat_b")])
        self._run_vector("list")
        self.assertTrue(
            any("2" in str(call) for call in self.app.console.print.call_args_list),
            "Expected count 2 in list output",
        )

    def test_list_with_custom_count(self):
        self._seed([(f"entry {i}", "test") for i in range(5)])
        self._run_vector("list 3")
        self.assertTrue(
            any("3" in str(call) for call in self.app.console.print.call_args_list),
            "Expected '3' indicating showing 3 entries",
        )

    def test_list_project_scope(self):
        self._seed([("project item", "config")], target=self.project_memory)
        self._run_vector("--project list")
        self.assertTrue(
            any("project" in str(call).lower() for call in self.app.console.print.call_args_list),
            "Expected project label in list output",
        )

    def test_list_project_flag_after_subcommand(self):
        """list --project should target project scope."""
        self._seed([("proj item", "config")], target=self.project_memory)
        self._run_vector("list --project")
        self.assertTrue(
            any("project" in str(call).lower() for call in self.app.console.print.call_args_list),
            "Expected project label with 'list --project'",
        )

    def test_list_project_flag_after_with_count(self):
        """list --project N should target project scope and limit to N."""
        self._seed(
            [(f"proj item {i}", "config") for i in range(5)],
            target=self.project_memory,
        )
        self._run_vector("list --project 3")
        # Should show count 5 total but limit 3
        output = [str(c).lower() for c in self.app.console.print.call_args_list]
        self.assertTrue(
            any("project" in c for c in output),
            "Expected project label with 'list --project N'",
        )
        self.assertTrue(
            any("3" in c for c in output),
            f"Expected '3' indicating showing 3 entries, got: {output[:3]}",
        )

    def test_list_project_short_form_after_subcommand(self):
        """list -p should target project scope."""
        self._seed([("proj item", "config")], target=self.project_memory)
        self._run_vector("list -p")
        self.assertTrue(
            any("project" in str(call).lower() for call in self.app.console.print.call_args_list),
            "Expected project label with 'list -p'",
        )

    # ── filter ───────────────────────────────────────────────────────

    def test_filter_no_category(self):
        self._run_vector("filter")
        self.assertTrue(
            any("usage" in m.lower() for m in self.app.messages),
            f"Expected usage message: {self.app.messages}",
        )

    def test_filter_nonexistent_category(self):
        self._seed([("something", "code")])
        self._run_vector("filter nonsense")
        self.assertTrue(
            any("no entries" in m.lower() for m in self.app.messages),
            f"Expected 'no entries' message: {self.app.messages}",
        )

    def test_filter_matches(self):
        self._seed([
            ("python async", "code"),
            ("cooking pasta", "recipe"),
            ("javascript callback", "code"),
        ])
        self._run_vector("filter code")
        self.assertTrue(
            any("code" in str(call).lower() for call in self.app.console.print.call_args_list),
            "Expected code category in filter output",
        )

    def test_filter_case_insensitive(self):
        """Store entries with mixed-case categories, query with different case variants.

        Verifies the ``COLLATE NOCASE`` in ``list_all()`` works end-to-end
        through the CLI handler for: lowercase, UPPERCASE, and MixedCase queries.
        """
        # Store entries with diverse casing in categories
        self._seed([
            ("entry with pascal case", "CodeStyle"),
            ("entry with uppercase", "MYCAT"),
            ("entry with lowercase", "devops"),
            ("entry in another cat", "misc"),
        ])

        vs = self.memory.vector

        # 1. Query with lowercase→pascal match
        self.app.messages.clear()
        self.app.console.reset_mock()
        self._run_vector("filter codestyle")
        no_entries = [m for m in self.app.messages if "no entries" in m.lower()]
        self.assertEqual(
            len(no_entries), 0,
            f"Expected match for 'codestyle' (stored as 'CodeStyle'), got: {self.app.messages}",
        )
        # Direct store access confirms exactly 1 entry matched
        matched = vs.list_all(category="codestyle")
        self.assertEqual(len(matched), 1)

        # 2. Query with lowercase→uppercase match
        self.app.messages.clear()
        self.app.console.reset_mock()
        self._run_vector("filter mycat")
        no_entries = [m for m in self.app.messages if "no entries" in m.lower()]
        self.assertEqual(
            len(no_entries), 0,
            f"Expected match for 'mycat' (stored as 'MYCAT'), got: {self.app.messages}",
        )
        matched = vs.list_all(category="mycat")
        self.assertEqual(len(matched), 1)

        # 3. Query with UPPERCASE→lowercase match
        self._run_vector("filter DEVOPS")
        no_entries = [m for m in self.app.messages if "no entries" in m.lower()]
        self.assertEqual(len(no_entries), 0)
        matched = vs.list_all(category="DEVOPS")
        self.assertEqual(len(matched), 1)

        # 4. Query with MixedCase→pascal match
        self._run_vector("filter CodeStyle")
        no_entries = [m for m in self.app.messages if "no entries" in m.lower()]
        self.assertEqual(len(no_entries), 0)
        matched = vs.list_all(category="CodeStyle")
        self.assertEqual(len(matched), 1)

        # 5. Cross-category: entries from 'misc' should NOT match any of the above
        matched_misc = vs.list_all(category="misc")
        self.assertEqual(len(matched_misc), 1)
        # And querying a non-existent category should give "no entries"
        self._run_vector("filter nonexistent_xyz")
        self.assertTrue(
            any("no entries" in m.lower() for m in self.app.messages),
            f"Expected 'no entries' for nonexistent category: {self.app.messages}",
        )

    def test_filter_project_scope(self):
        """--project before subcommand: ``--project filter <category>``"""
        self._seed([("proj item", "config")], target=self.project_memory)
        self._run_vector("--project filter config")
        self.assertTrue(
            any("project" in str(call).lower() for call in self.app.console.print.call_args_list),
            "Expected project label in filter output",
        )

    def test_filter_project_flag_after_subcommand(self):
        """--project after subcommand: ``filter --project <category>``"""
        self._seed([("proj item", "config")], target=self.project_memory)
        self._run_vector("filter --project config")
        self.assertTrue(
            any("project" in str(call).lower() for call in self.app.console.print.call_args_list),
            "Expected project label in filter output with --project after subcommand",
        )
        # Verify global store is unaffected
        self.assertEqual(self.memory.vector.count(), 0)

    def test_filter_project_short_form_after_subcommand(self):
        """Short -p after subcommand: ``filter -p <category>``"""
        self._seed([("proj item", "config")], target=self.project_memory)
        self._run_vector("filter -p config")
        self.assertTrue(
            any("project" in str(call).lower() for call in self.app.console.print.call_args_list),
            "Expected project label with -p after subcommand",
        )
        self.assertEqual(self.memory.vector.count(), 0)

    def test_filter_project_flag_without_category(self):
        """filter --project without a category should show usage."""
        self._run_vector("filter --project")
        self.assertTrue(
            any("usage" in m.lower() for m in self.app.messages),
            f"Expected usage message when --project used without category: {self.app.messages}",
        )

    def test_filter_cross_scope_isolation(self):
        """Seed both global and project stores with the same category,
        then ``filter --project`` should return only project entries.

        Tests all four flag placements:
        - default (global) scope: ``filter <cat>``
        - ``--project`` before subcommand: ``--project filter <cat>``
        - ``--project`` after subcommand: ``filter --project <cat>``
        - short ``-p`` before subcommand: ``-p filter <cat>``
        """
        # Seed global store with 2 entries in "config" category
        self._seed([
            ("global config alpha", "config"),
            ("global config beta", "config"),
        ])
        # Seed project store with 3 entries in the same category
        self._seed([
            ("project config gamma", "config"),
            ("project config delta", "config"),
            ("project config epsilon", "config"),
        ], target=self.project_memory)

        # Sanity check: each store has the right count
        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)

        def _assert_filter_calls(calls, expected_count, scope_label):
            """Assert that filter output contains the expected count and scope label."""
            lowered = [str(c).lower() for c in calls]
            self.assertTrue(
                any(str(expected_count) in c for c in lowered),
                f"Expected '{expected_count}' entries, got: {lowered[:3]}",
            )
            self.assertTrue(
                any(scope_label in c for c in lowered),
                f"Expected '{scope_label}' scope label, got: {lowered[:3]}",
            )

        # 1. Default (global) scope → should see 2 global entries
        self.app.messages.clear()
        self.app.console.reset_mock()
        self._run_vector("filter config")
        _assert_filter_calls(self.app.console.print.call_args_list, 2, "global")

        # 2. Project scope with --project before subcommand: --project filter <cat>
        self.app.console.reset_mock()
        self._run_vector("--project filter config")
        _assert_filter_calls(self.app.console.print.call_args_list, 3, "project")
        self.assertEqual(self.memory.vector.count(), 2, "Global store untouched by --project filter")

        # 3. Project scope with --project after subcommand: filter --project <cat>
        self.app.console.reset_mock()
        self._run_vector("filter --project config")
        _assert_filter_calls(self.app.console.print.call_args_list, 3, "project")
        self.assertEqual(self.memory.vector.count(), 2, "Global store untouched by filter --project")

        # 4. Project scope with short -p before subcommand: -p filter <cat>
        self.app.console.reset_mock()
        self._run_vector("-p filter config")
        _assert_filter_calls(self.app.console.print.call_args_list, 3, "project")
        self.assertEqual(self.memory.vector.count(), 2, "Global store untouched by -p filter")

        # All stores intact after all operations
        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)
        self.assertFalse(self.app.errors)

    # ── migrate ──────────────────────────────────────────────────────

    def test_migrate_empty(self):
        self._run_vector("migrate")
        self.assertTrue(
            any("no" in m.lower() for m in self.app.messages),
            f"Expected 'no entries' message: {self.app.messages}",
        )

    def test_migrate_populates_vector_store(self):
        self.memory.long_term.store("test memory", category="general")
        self.assertEqual(self.memory.vector.count(), 0)
        self._run_vector("migrate")
        self.assertEqual(self.memory.vector.count(), 1)

    def test_migrate_idempotent(self):
        self.memory.long_term.store("data", category="test")
        self._run_vector("migrate")
        self.assertEqual(self.memory.vector.count(), 1)
        self._run_vector("migrate")
        self.assertEqual(self.memory.vector.count(), 1)

    def test_migrate_project_scope(self):
        self.project_memory.long_term.store("project data", category="config")
        self.assertEqual(self.project_memory.vector.count(), 0)
        self._run_vector("--project migrate")
        self.assertEqual(self.project_memory.vector.count(), 1)
        # Global should still be empty
        self.assertEqual(self.memory.vector.count(), 0)

    def test_migrate_cross_scope_isolation(self):
        """Cross-scope isolation: migrate with both stores.

        Stores entries in FTS5 only, then verifies:
        - ``--project migrate`` populates only the project vector
        - default ``migrate`` populates only the global vector

        Verifies the two scopes are fully isolated during migration.
        """
        # Store entries in FTS5 without migrating to vector
        self.memory.long_term.store("global migrate a", category="test")
        self.memory.long_term.store("global migrate b", category="test")
        self.project_memory.long_term.store("project migrate c", category="test")
        self.project_memory.long_term.store("project migrate d", category="test")
        self.project_memory.long_term.store("project migrate e", category="test")

        self.assertEqual(self.memory.vector.count(), 0)
        self.assertEqual(self.project_memory.vector.count(), 0)

        # 1. Migrate project scope → only project vector populated
        self.app.messages.clear()
        self._run_vector("--project migrate")
        self.assertEqual(
            self.project_memory.vector.count(), 3,
            "Expected 3 project entries migrated",
        )
        self.assertEqual(
            self.memory.vector.count(), 0,
            "Global vector store untouched by --project migrate",
        )
        self.assertTrue(
            any("migration complete" in m.lower() and "project" in m.lower() for m in self.app.messages),
            f"Expected 'migration complete' and 'project' in message: {self.app.messages}",
        )
        self.assertFalse(self.app.errors)

        # 2. Migrate global scope → global vector populated
        self.app.messages.clear()
        self._run_vector("migrate")
        self.assertEqual(
            self.memory.vector.count(), 2,
            "Expected 2 global entries migrated",
        )
        self.assertEqual(
            self.project_memory.vector.count(), 3,
            "Project vector store unaffected by global migrate",
        )
        self.assertTrue(
            any("migration complete" in m.lower() and "global" in m.lower() for m in self.app.messages),
            f"Expected 'migration complete' and 'global' in message: {self.app.messages}",
        )
        self.assertFalse(self.app.errors)

    # ── delete ───────────────────────────────────────────────────────

    def test_delete_no_id(self):
        self._run_vector("delete")
        self.assertTrue(
            any("usage" in m.lower() for m in self.app.messages),
            f"Expected usage message: {self.app.messages}",
        )

    def test_delete_nonexistent(self):
        self._run_vector("delete nonexistent_id_xyz")
        self.assertTrue(
            any("not available" in m.lower() for m in self.app.messages) or
            any("vector entry found" in m.lower() for m in self.app.messages),
            f"Expected not-found or not-available message: {self.app.messages}",
        )

    def test_delete_existing(self):
        eid = self.memory.long_term.store("delete me", category="test")
        self._migrate()
        self.assertEqual(self.memory.vector.count(), 1)
        self._run_vector(f"delete {eid}")
        self.assertEqual(self.memory.vector.count(), 0)

    def test_delete_project_scope(self):
        eid = self.project_memory.long_term.store("project entry", category="config")
        self._migrate(target=self.project_memory)
        self.assertEqual(self.project_memory.vector.count(), 1)
        self._run_vector(f"--project delete {eid}")
        self.assertEqual(self.project_memory.vector.count(), 0)

    def test_delete_project_flag_after_subcommand(self):
        """delete --project <id> should target project scope."""
        eid = self.project_memory.long_term.store("project entry", category="config")
        self._migrate(target=self.project_memory)
        self.assertEqual(self.project_memory.vector.count(), 1)
        self.assertEqual(self.memory.vector.count(), 0)
        self._run_vector(f"delete --project {eid}")
        self.assertEqual(self.project_memory.vector.count(), 0)
        self.assertFalse(self.app.errors)

    def test_delete_project_short_form_after_subcommand(self):
        """delete -p <id> should target project scope."""
        eid = self.project_memory.long_term.store("project entry", category="config")
        self._migrate(target=self.project_memory)
        self.assertEqual(self.project_memory.vector.count(), 1)
        self._run_vector(f"delete -p {eid}")
        self.assertEqual(self.project_memory.vector.count(), 0)
        self.assertFalse(self.app.errors)

    def test_delete_project_flag_after_without_id(self):
        """delete --project without an ID should show usage."""
        self._run_vector("delete --project")
        self.assertTrue(
            any("usage" in m.lower() for m in self.app.messages),
            f"Expected usage message: {self.app.messages}",
        )

    # ── clear ────────────────────────────────────────────────────────

    def test_clear_empty(self):
        self._run_vector("clear")
        self.assertTrue(
            any("empty" in m.lower() for m in self.app.messages) or
            any("not available" in m.lower() for m in self.app.messages),
            f"Expected empty message: {self.app.messages}",
        )

    def test_clear_removes_all(self):
        self._seed([
            ("entry one", "cat_a"),
            ("entry two", "cat_b"),
        ])
        self.assertEqual(self.memory.vector.count(), 2)
        self._run_vector("clear")
        self.assertEqual(self.memory.vector.count(), 0)

    def test_clear_fts5_untouched(self):
        eid = self.memory.long_term.store("fts5 data", category="test")
        self._migrate()
        self._run_vector("clear")
        self.assertEqual(self.memory.vector.count(), 0)
        # FTS5 should still have the entry
        entry = self.memory.long_term.get(eid)
        self.assertIsNotNone(entry)

    def test_clear_project_scope(self):
        self._seed([("global data", "test")])
        self._seed([("project data", "config")], target=self.project_memory)
        self._run_vector("--project clear")
        # Project store should be cleared
        self.assertEqual(self.project_memory.vector.count(), 0)
        # Global store should remain intact
        self.assertEqual(self.memory.vector.count(), 1)

    def test_list_cross_scope_isolation(self):
        """Cross-scope isolation: list with both stores seeded.

        Tests all three flag placements:
        - default (global) scope: ``list``
        - ``--project`` before subcommand: ``--project list``
        - ``--project`` after subcommand: ``list --project``

        Each project-scoped variant verifies the global store count
        remains unchanged.
        """
        # Seed global with 2 entries, project with 3 entries
        self._seed([
            ("global list a", "test"),
            ("global list b", "test"),
        ])
        self._seed([
            ("project list c", "test"),
            ("project list d", "test"),
            ("project list e", "test"),
        ], target=self.project_memory)

        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)

        # 1. Default (global) scope → shows global entries
        self.app.messages.clear()
        self.app.console.reset_mock()
        self._run_vector("list")
        calls = [str(c).lower() for c in self.app.console.print.call_args_list]
        self.assertTrue(
            any("global" in c for c in calls),
            "Expected 'global' scope label in default list output",
        )
        self.assertTrue(
            any("2" in c for c in calls),
            "Expected '2' total entries in global list output",
        )
        self.assertFalse(self.app.errors)

        # 2. Project scope with --project before subcommand: --project list
        self.app.console.reset_mock()
        self._run_vector("--project list")
        calls = [str(c).lower() for c in self.app.console.print.call_args_list]
        self.assertTrue(
            any("project" in c for c in calls),
            "Expected 'project' scope label with '--project list'",
        )
        self.assertTrue(
            any("3" in c for c in calls),
            "Expected '3' total entries in --project list output",
        )
        self.assertEqual(self.memory.vector.count(), 2, "Global store untouched by --project list")
        self.assertFalse(self.app.errors)

        # 3. Project scope with --project after subcommand: list --project
        self.app.console.reset_mock()
        self._run_vector("list --project")
        calls = [str(c).lower() for c in self.app.console.print.call_args_list]
        self.assertTrue(
            any("project" in c for c in calls),
            "Expected 'project' scope label with 'list --project'",
        )
        self.assertTrue(
            any("3" in c for c in calls),
            "Expected '3' total entries in list --project output",
        )
        self.assertEqual(self.memory.vector.count(), 2, "Global store untouched by list --project")
        self.assertFalse(self.app.errors)

        # All stores intact after all operations
        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)

    def test_query_cross_scope_isolation(self):
        """Cross-scope isolation: query with both stores seeded.

        Tests all three flag placements:
        - default (global) scope: ``query <text>``
        - ``--project`` before subcommand: ``--project query <text>``
        - ``--project`` after subcommand: ``query --project <text>``

        Each project-scoped variant verifies the global store count
        remains unchanged.
        """
        # Seed global with 2 entries, project with 3 entries in distinct categories
        self._seed([
            ("python async await programming patterns", "code"),
            ("python decorators and context managers", "code"),
        ])
        self._seed([
            ("project configuration and deployment", "config"),
            ("project env variables and secrets", "config"),
            ("project docker compose setup", "config"),
        ], target=self.project_memory)

        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)

        # 1. Default (global) scope → should show global results with global label
        self.app.messages.clear()
        self.app.console.reset_mock()
        self._run_vector("query python")
        calls = [str(c).lower() for c in self.app.console.print.call_args_list]
        self.assertTrue(
            any("global" in c for c in calls),
            "Expected 'global' scope label in default query output",
        )
        self.assertTrue(
            any("python" in c for c in calls),
            "Expected 'python' match in default query results",
        )
        self.assertFalse(self.app.errors)

        # 2. Project scope with --project before subcommand: --project query <text>
        self.app.console.reset_mock()
        self._run_vector("--project query project")
        calls = [str(c).lower() for c in self.app.console.print.call_args_list]
        self.assertTrue(
            any("project" in c for c in calls),
            "Expected 'project' scope label with '--project query'",
        )
        self.assertTrue(
            any("project" in c for c in calls),
            "Expected project-related results in --project query output",
        )
        self.assertEqual(self.memory.vector.count(), 2, "Global store untouched by --project query")
        self.assertFalse(self.app.errors)

        # 3. Project scope with --project after subcommand: query --project <text>
        self.app.console.reset_mock()
        self._run_vector("query --project project")
        calls = [str(c).lower() for c in self.app.console.print.call_args_list]
        self.assertTrue(
            any("project" in c for c in calls),
            "Expected 'project' scope label with 'query --project'",
        )
        self.assertTrue(
            any("project" in c for c in calls),
            "Expected project-related results in query --project output",
        )
        self.assertEqual(self.memory.vector.count(), 2, "Global store untouched by query --project")
        self.assertFalse(self.app.errors)

        # All stores intact
        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)

    def test_delete_cross_scope_isolation(self):
        """Cross-scope isolation: delete with both stores seeded.

        Tests both ``--project`` flag placements:
        - ``--project`` before subcommand: ``--project delete <id>``
        - ``--project`` after subcommand: ``delete --project <id>``

        Each project-scoped delete verifies the global store count
        remains unchanged.
        """
        # Seed global with 2 entries, project with 3 entries
        self._seed([
            ("global delete a", "test"),
            ("global delete b", "test"),
        ])
        project_ids: list[str] = []
        for content, cat in [
            ("project delete c", "test"),
            ("project delete d", "test"),
            ("project delete e", "test"),
        ]:
            eid = self.project_memory.long_term.store(content, category=cat)
            project_ids.append(eid)
        self._migrate(target=self.project_memory)

        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)

        # 1. Project scope with --project before subcommand: --project delete <id>
        target_id = project_ids[0]
        self.app.messages.clear()
        self._run_vector(f"--project delete {target_id}")
        self.assertEqual(
            self.project_memory.vector.count(), 2,
            "Expected one project entry deleted via --project delete",
        )
        self.assertEqual(
            self.memory.vector.count(), 2,
            "Global store untouched by --project delete",
        )
        self.assertTrue(
            any("deleted" in m.lower() and "project" in m.lower() for m in self.app.messages),
            f"Expected 'deleted' and 'project' in message: {self.app.messages}",
        )
        self.assertFalse(self.app.errors)

        # 2. Project scope with --project after subcommand: delete --project <id>
        target_id = project_ids[1]
        self.app.messages.clear()
        self._run_vector(f"delete --project {target_id}")
        self.assertEqual(
            self.project_memory.vector.count(), 1,
            "Expected two project entries deleted via delete --project",
        )
        self.assertEqual(
            self.memory.vector.count(), 2,
            "Global store still untouched by delete --project",
        )
        self.assertTrue(
            any("deleted" in m.lower() and "project" in m.lower() for m in self.app.messages),
            f"Expected 'deleted' and 'project' in message: {self.app.messages}",
        )
        self.assertFalse(self.app.errors)

        # Global store unchanged throughout
        self.assertEqual(self.memory.vector.count(), 2)

    def test_clear_cross_scope_isolation(self):
        """Cross-scope isolation: clear with both stores seeded.

        Tests:
        - ``--project`` before subcommand: ``--project clear`` clears
          only the project store
        - default ``clear`` clears only the global store

        Verifies the two scopes are fully isolated.
        """
        # Seed global with 2 entries, project with 3 entries
        self._seed([
            ("global clear a", "test"),
            ("global clear b", "test"),
        ])
        self._seed([
            ("project clear c", "test"),
            ("project clear d", "test"),
            ("project clear e", "test"),
        ], target=self.project_memory)

        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)

        # 1. Clear project scope only: --project clear
        self.app.messages.clear()
        self._run_vector("--project clear")
        self.assertEqual(
            self.project_memory.vector.count(), 0,
            "Project store should be cleared",
        )
        self.assertEqual(
            self.memory.vector.count(), 2,
            "Global store untouched by --project clear",
        )
        self.assertTrue(
            any("cleared" in m.lower() and "project" in m.lower() for m in self.app.messages),
            f"Expected 'cleared' and 'project' in message: {self.app.messages}",
        )
        self.assertFalse(self.app.errors)

        # 2. Clear global scope: clear (default)
        self.app.messages.clear()
        self._run_vector("clear")
        self.assertEqual(
            self.memory.vector.count(), 0,
            "Global store should be cleared",
        )
        self.assertEqual(
            self.project_memory.vector.count(), 0,
            "Project store already cleared",
        )
        self.assertTrue(
            any("cleared" in m.lower() and "global" in m.lower() for m in self.app.messages),
            f"Expected 'cleared' and 'global' in message: {self.app.messages}",
        )
        self.assertFalse(self.app.errors)

    # ── rebuild ──────────────────────────────────────────────────────

    def test_rebuild_empty(self):
        self._run_vector("rebuild")
        self.assertTrue(
            any("empty" in m.lower() for m in self.app.messages),
            f"Expected empty message: {self.app.messages}",
        )

    def test_rebuild_with_entries(self):
        self._seed([("content a", "cat_a"), ("content b", "cat_b")])
        self.assertEqual(self.memory.vector.count(), 2)
        self._run_vector("rebuild")
        self.assertEqual(self.memory.vector.count(), 2)

    def test_rebuild_project_scope(self):
        self._seed([("project data", "config")], target=self.project_memory)
        self.assertEqual(self.project_memory.vector.count(), 1)
        self._run_vector("--project rebuild")
        self.assertEqual(self.project_memory.vector.count(), 1)

    def test_rebuild_cross_scope_isolation(self):
        """Cross-scope isolation: rebuild with both stores seeded.

        Tests:
        - default (global) scope: ``rebuild``
        - ``--project`` before subcommand: ``--project rebuild``

        Both non-destructive — counts unchanged.
        """
        # Seed global with 2 entries, project with 3 entries
        self._seed([
            ("global rebuild a", "test"),
            ("global rebuild b", "test"),
        ])
        self._seed([
            ("project rebuild c", "test"),
            ("project rebuild d", "test"),
            ("project rebuild e", "test"),
        ], target=self.project_memory)

        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)

        # 1. Default (global) scope
        self.app.messages.clear()
        self._run_vector("rebuild")
        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)
        self.assertTrue(
            any("rebuilt" in m.lower() and "global" in m.lower() for m in self.app.messages),
            f"Expected 'rebuilt' and 'global' in message: {self.app.messages}",
        )
        self.assertFalse(self.app.errors)

        # 2. Project scope via --project before subcommand
        self.app.messages.clear()
        self._run_vector("--project rebuild")
        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)
        self.assertTrue(
            any("rebuilt" in m.lower() and "project" in m.lower() for m in self.app.messages),
            f"Expected 'rebuilt' and 'project' in message: {self.app.messages}",
        )
        self.assertFalse(self.app.errors)

    # ── categories ────────────────────────────────────────────────────

    def test_categories_empty(self):
        self._run_vector("categories")
        self.assertTrue(
            any("empty" in m.lower() for m in self.app.messages),
            f"Expected empty message: {self.app.messages}",
        )

    def test_categories_with_entries(self):
        self._seed([
            ("python async", "code"),
            ("javascript cb", "code"),
            ("cooking pasta", "recipe"),
            ("docker compose", "devops"),
        ])
        self._run_vector("categories")
        # Should render categories table
        self.assertTrue(
            self.app.console.print.called,
            "Expected categories to print output",
        )
        self.assertFalse(self.app.errors)
        # Verify counts via direct store access
        cats = self.memory.vector.categories()
        cat_map = {c["category"]: c["count"] for c in cats}
        self.assertEqual(cat_map.get("code"), 2)
        self.assertEqual(cat_map.get("recipe"), 1)
        self.assertEqual(cat_map.get("devops"), 1)

    def test_categories_project_scope(self):
        self._seed([("proj data", "config")], target=self.project_memory)
        self._run_vector("--project categories")
        self.assertTrue(
            self.app.console.print.called,
            "Expected categories to print output for project scope",
        )
        self.assertFalse(self.app.errors)

    def test_categories_cross_scope_isolation(self):
        """Cross-scope isolation: categories with both stores seeded.

        Tests:
        - default (global) scope: ``categories``
        - ``--project`` before subcommand: ``--project categories``

        Each verifies the correct scope label in console output.
        Counts unchanged after all operations.
        """
        # Seed global with 2 entries, project with 3 entries
        self._seed([
            ("global cat a", "code"),
            ("global cat b", "config"),
        ])
        self._seed([
            ("project cat c", "config"),
            ("project cat d", "devops"),
            ("project cat e", "test"),
        ], target=self.project_memory)

        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)

        # 1. Default (global) scope
        self.app.console.reset_mock()
        self._run_vector("categories")
        calls = [str(c).lower() for c in self.app.console.print.call_args_list]
        self.assertTrue(
            any("global" in c for c in calls),
            "Expected 'global' scope label in default categories output",
        )
        self.assertFalse(self.app.errors)

        # 2. Project scope via --project before subcommand
        self.app.console.reset_mock()
        self._run_vector("--project categories")
        calls = [str(c).lower() for c in self.app.console.print.call_args_list]
        self.assertTrue(
            any("project" in c for c in calls),
            "Expected 'project' scope label in --project categories output",
        )
        self.assertFalse(self.app.errors)

        # Counts unchanged — both stores fully intact
        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)

    # ── routing edge cases ───────────────────────────────────────────

    def test_unknown_subcommand(self):
        self._run_vector("nonexistent")
        self.assertTrue(
            any("usage" in m.lower() for m in self.app.messages),
            f"Expected usage message for unknown subcommand: {self.app.messages}",
        )

    def test_no_subcommand(self):
        self._run_vector("")
        self.assertTrue(
            any("usage" in m.lower() for m in self.app.messages),
            f"Expected usage message for no subcommand: {self.app.messages}",
        )

    def test_project_flag_without_subcommand(self):
        self._run_vector("--project")
        self.assertTrue(
            any("usage" in m.lower() for m in self.app.messages),
            f"Expected usage message: {self.app.messages}",
        )

    def test_project_flag_short_form(self):
        self._seed([("data", "test")], target=self.project_memory)
        self._run_vector("-p stats")
        # Stats renders a Rich Table — verify it ran without error
        self.assertTrue(
            self.app.console.print.called,
            "Expected stats to print output",
        )
        self.assertFalse(self.app.errors)

    def test_global_is_default(self):
        self._seed([("global entry", "test")])
        self._run_vector("list")
        # Default scope is global, should show global entries
        self.assertTrue(
            any("global" in str(call).lower() for call in self.app.console.print.call_args_list),
            "Expected global scope label in default list output",
        )


class TestVectorCommandsViaDispatcher(unittest.TestCase):
    """Integration tests that route through the command dispatcher chain.

    Tests exercise the full dispatch path:
    ``_cmd_memory("vector ...")`` → ``_cmd_memory_vector(...)`` → handler

    This validates the routing logic in ``_cmd_memory()`` that parses
    the ``"vector"`` prefix before dispatching to the vector sub-handler.

    Dispatcher cross-scope isolation tests:
    - ``test_dispatcher_filter_cross_scope_isolation`` — filter with all 4
      ``--project`` flag placements (default, before, after, short ``-p``)
    - ``test_dispatcher_stats_cross_scope_isolation`` — stats default vs
      ``--project`` scope via internal flag verification
    - ``test_dispatcher_list_cross_scope_isolation`` — list default,
      ``list --project``, and ``--project list``
    - ``test_dispatcher_clear_cross_scope_isolation`` — ``--project clear``
      clears only project store; default ``clear`` clears only global
    - ``test_dispatcher_delete_cross_scope_isolation`` — delete with
      ``--project`` before and after subcommand, verifying store isolation
    - ``test_dispatcher_query_cross_scope_isolation`` — query default,
      ``query --project <text>``, and ``--project query <text>``
    - ``test_dispatcher_rebuild_cross_scope_isolation`` — rebuild default
      vs ``--project`` scope, non-destructive (counts unchanged)
    - ``test_dispatcher_migrate_cross_scope_isolation`` — ``--project``
      migrate populates only project vector; default only global
    - ``test_dispatcher_categories_cross_scope_isolation`` — categories
      default vs ``--project`` scope via console.print scope labels
    - ``test_dispatcher_download_cross_scope_isolation`` — download
      default vs ``--project`` scope via ``_vector_use_project`` flag

    Each test seeds both stores (2 global entries, 3 project entries),
    verifies isolation through direct count assertions after each
    project-scoped operation, and confirms counts remain unchanged.
    """

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmpdir.name) / "memory"
        self.project_data_dir = Path(self.tmpdir.name) / "project_memory"

        self.memory = MemoryManager(data_dir=self.data_dir)
        self.project_memory = MemoryManager(data_dir=self.project_data_dir)

        self.app = _MockApp(self.memory, self.project_memory)

    def tearDown(self):
        self.memory.close()
        self.project_memory.close()
        self.tmpdir.cleanup()

    # ── Helpers ──────────────────────────────────────────────────────

    def _seed(self, texts: list[tuple[str, str]], target: MemoryManager | None = None):
        mgr = target or self.memory
        for content, category in texts:
            mgr.long_term.store(content, category=category)
        self._migrate(mgr)

    def _migrate(self, target: MemoryManager | None = None):
        mgr = target or self.memory
        vs = mgr.vector
        if vs is None:
            return
        stats = mgr.long_term.get_stats()
        total = stats.get("total_entries", 0)
        offset = 0
        PAGE_SIZE = 50
        while offset < total:
            entries = mgr.long_term.list_all(limit=PAGE_SIZE, offset=offset)
            if not entries:
                break
            for entry in entries:
                eid = entry.get("id", "")
                content = entry.get("content", "")
                category = entry.get("category", "general")
                if not content or not content.strip():
                    continue
                if vs.get(eid):
                    continue
                vs.store(eid, content, category=category)
            offset += PAGE_SIZE

    def _cmd(self, full_command: str):
        """Simulate the command dispatcher chain.

        This goes through ``_cmd_memory()`` which parses the "vector"
        prefix and dispatches to ``_cmd_memory_vector()`` — testing
        the routing that ``_handle_slash_command("/memory vector ...")``
        would trigger.
        """
        # Simulate what _handle_slash_command does: split "/memory vector stats"
        # into cmd="/memory", args="vector stats" and call _cmd_memory("vector stats")
        parts = full_command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "/memory":
            self.app._cmd_memory(args)
        else:
            self.app.r.error(f"Unknown command: {cmd}")

    # ── Dispatcher routing tests ─────────────────────────────────────

    def test_dispatcher_routes_vector_to_vector_handler(self):
        """_cmd_memory should detect 'vector' prefix and dispatch."""
        self._seed([("test data", "general")])
        self._cmd("/memory vector stats")
        self.assertTrue(
            self.app.console.print.called,
            "Expected /memory vector stats to render output",
        )
        self.assertFalse(self.app.errors)

    def test_dispatcher_vector_query(self):
        """Full chain: /memory vector query <text>

        Exercises: _handle_slash_command -> _cmd_memory("vector query ...")
        -> _cmd_memory_vector("query ...") -> _cmd_memory_vector_query(...)
        """
        self._seed([
            ("python async await programming", "code"),
            ("javascript event loop", "code"),
        ])
        self._cmd("/memory vector query python async")
        self.assertTrue(
            any("python" in str(call) for call in self.app.console.print.call_args_list),
            "Expected query results to contain matched content",
        )

    def test_dispatcher_vector_migrate(self):
        """Full chain: /memory vector migrate

        Exercises: _handle_slash_command -> _cmd_memory("vector migrate")
        -> _cmd_memory_vector("migrate") -> _cmd_memory_vector_migrate()
        """
        self.memory.long_term.store("migrate test data", category="test")
        self.assertEqual(self.memory.vector.count(), 0)
        self._cmd("/memory vector migrate")
        self.assertEqual(self.memory.vector.count(), 1)

    def test_dispatcher_vector_delete(self):
        """Full chain: /memory vector delete <id>"""
        eid = self.memory.long_term.store("delete via dispatcher", category="test")
        self._migrate()
        self.assertEqual(self.memory.vector.count(), 1)
        self._cmd(f"/memory vector delete {eid}")
        self.assertEqual(self.memory.vector.count(), 0)

    def test_dispatcher_vector_clear(self):
        """Full chain: /memory vector clear"""
        self._seed([("entry one", "a"), ("entry two", "b")])
        self.assertEqual(self.memory.vector.count(), 2)
        self._cmd("/memory vector clear")
        self.assertEqual(self.memory.vector.count(), 0)

    def test_dispatcher_vector_rebuild(self):
        """Full chain: /memory vector rebuild"""
        self._seed([("rebuild test", "test")])
        self.assertEqual(self.memory.vector.count(), 1)
        self._cmd("/memory vector rebuild")
        self.assertEqual(self.memory.vector.count(), 1)

    def test_dispatcher_vector_list(self):
        """Full chain: /memory vector list"""
        self._seed([("list entry", "test")])
        self._cmd("/memory vector list")
        self.assertTrue(
            self.app.console.print.called,
            "Expected /memory vector list to produce output",
        )
        self.assertFalse(self.app.errors)

    def test_dispatcher_vector_filter(self):
        """Full chain: /memory vector filter <category>"""
        self._seed([("filter target", "devops"), ("other", "misc")])
        self._cmd("/memory vector filter devops")
        # Should NOT say "no entries"
        no_entries = [m for m in self.app.messages if "no entries" in m.lower()]
        self.assertEqual(len(no_entries), 0)

    def test_dispatcher_vector_with_project_flag(self):
        """Full chain: /memory vector --project stats"""
        self._seed([("project scope", "config")], target=self.project_memory)
        self._cmd("/memory vector --project stats")
        self.assertTrue(
            self.app.console.print.called,
            "Expected --project stats to produce output",
        )
        self.assertFalse(self.app.errors)

    def test_dispatcher_vector_filter_with_project_flag_after(self):
        """Full chain: /memory vector filter --project <category>

        Exercises the ``--project`` flag *after* the subcommand:
        ``_cmd_memory("vector filter --project config")``
        → ``_cmd_memory_vector("filter --project config")``
        → ``_cmd_memory_vector_filter("--project config")``
        """
        self._seed([("proj target", "config")], target=self.project_memory)
        self._cmd("/memory vector filter --project config")
        # Should produce console output with "project" scope label
        self.assertTrue(
            any("project" in str(call).lower() for call in self.app.console.print.call_args_list),
            "Expected project label in filter output through dispatcher",
        )
        # Global store should remain empty
        self.assertEqual(self.memory.vector.count(), 0)

    def test_dispatcher_vector_filter_short_project_after(self):
        """Full chain: /memory vector filter -p <category>

        Short-form ``-p`` flag after the subcommand.
        """
        self._seed([("proj target", "config")], target=self.project_memory)
        self._cmd("/memory vector filter -p config")
        self.assertTrue(
            any("project" in str(call).lower() for call in self.app.console.print.call_args_list),
            "Expected project label with -p flag through dispatcher",
        )
        self.assertEqual(self.memory.vector.count(), 0)

    def test_dispatcher_filter_cross_scope_isolation(self):
        """Full chain cross-scope isolation: /memory vector filter --project <category>

        Seeds both global and project stores with the same category, then
        verifies that ``--project`` routing through the dispatcher correctly
        isolates scopes for: default (global), ``filter --project <cat>``,
        ``--project filter <cat>``, and ``filter -p <cat>``.

        Exercises: _cmd_memory -> _cmd_memory_vector -> _cmd_memory_vector_filter
        """
        # Seed global store with 2 entries in "config" category
        self._seed([
            ("global config alpha", "config"),
            ("global config beta", "config"),
        ])
        # Seed project store with 3 entries in the same category
        self._seed([
            ("project config gamma", "config"),
            ("project config delta", "config"),
            ("project config epsilon", "config"),
        ], target=self.project_memory)

        # Sanity check: each store has the right count
        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)

        # 1. Default (global) scope through dispatcher
        self.app.messages.clear()
        self.app.console.reset_mock()
        self._cmd("/memory vector filter config")
        global_calls = [str(c) for c in self.app.console.print.call_args_list]
        self.assertTrue(
            any("2" in c for c in global_calls),
            f"Expected '2' for global filter entries through dispatcher, got: {global_calls[:3]}",
        )
        self.assertFalse(self.app.errors)

        # 2. Project scope with --project after subcommand: filter --project config
        self.app.console.reset_mock()
        self._cmd("/memory vector filter --project config")
        project_calls = [str(c) for c in self.app.console.print.call_args_list]
        self.assertTrue(
            any("3" in c for c in project_calls),
            f"Expected '3' for project filter entries through dispatcher, got: {project_calls[:3]}",
        )
        self.assertTrue(
            any("project" in c.lower() for c in project_calls),
            "Expected 'project' scope label through dispatcher",
        )
        # Global store should be unaffected
        self.assertEqual(self.memory.vector.count(), 2)
        self.assertFalse(self.app.errors)

        # 3. Project scope with --project before subcommand: --project filter config
        self.app.console.reset_mock()
        self._cmd("/memory vector --project filter config")
        project_calls = [str(c) for c in self.app.console.print.call_args_list]
        self.assertTrue(
            any("3" in c for c in project_calls),
            f"Expected '3' for --project filter config through dispatcher, got: {project_calls[:3]}",
        )
        self.assertTrue(
            any("project" in c.lower() for c in project_calls),
            "Expected 'project' scope label with --project before subcommand",
        )
        # Global store should still be unaffected
        self.assertEqual(self.memory.vector.count(), 2)
        self.assertFalse(self.app.errors)

        # 4. Project scope with short -p after subcommand: filter -p config
        self.app.console.reset_mock()
        self._cmd("/memory vector filter -p config")
        project_calls = [str(c) for c in self.app.console.print.call_args_list]
        self.assertTrue(
            any("3" in c for c in project_calls),
            f"Expected '3' for filter -p config through dispatcher, got: {project_calls[:3]}",
        )
        self.assertTrue(
            any("project" in c.lower() for c in project_calls),
            "Expected 'project' scope label with filter -p through dispatcher",
        )
        # Global store should remain intact after all operations
        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)
        self.assertFalse(self.app.errors)

    # ── Dispatcher cross-scope isolation tests ─────────────────────

    def test_dispatcher_stats_cross_scope_isolation(self):
        """Cross-scope isolation: /memory vector [--project] stats

        Seeds both stores and verifies that ``stats`` renders the global
        store and ``--project stats`` renders the project store via the
        dispatcher chain. Uses the ``_vector_use_project`` flag (which
        controls which store ``_get_vector_store()`` resolves) to verify
        scope routing, since stats outputs a Rich ``Table`` whose rendered
        text is not captured by the MagicMock ``console.print``.
        """
        # Seed global with 2 entries, project with 3 entries
        self._seed([
            ("global stat a", "code"),
            ("global stat b", "config"),
        ])
        self._seed([
            ("project stat c", "config"),
            ("project stat d", "config"),
            ("project stat e", "devops"),
        ], target=self.project_memory)

        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)

        # 1. Default scope → global stats (flag is False)
        self.app.console.reset_mock()
        self._cmd("/memory vector stats")
        self.assertTrue(
            self.app.console.print.called,
            "Expected stats to render output",
        )
        self.assertFalse(self.app._vector_use_project)
        self.assertFalse(self.app.errors)

        # 2. Project scope via --project before subcommand
        self.app.console.reset_mock()
        self._cmd("/memory vector --project stats")
        self.assertTrue(
            self.app.console.print.called,
            "Expected --project stats to render output",
        )
        self.assertTrue(self.app._vector_use_project)
        self.assertFalse(self.app.errors)

        # Counts unchanged — both stores fully intact
        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)

    def test_dispatcher_list_cross_scope_isolation(self):
        """Cross-scope isolation: /memory vector [--project] list

        Seeds both stores and verifies that ``list`` shows global entries,
        ``list --project`` shows project entries, and ``--project list``
        also shows project entries — all through the dispatcher chain.
        """
        # Seed global with 2 entries, project with 3 entries in same category
        self._seed([
            ("global list a", "test"),
            ("global list b", "test"),
        ])
        self._seed([
            ("project list c", "test"),
            ("project list d", "test"),
            ("project list e", "test"),
        ], target=self.project_memory)

        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)

        # 1. Default (global) scope
        self.app.messages.clear()
        self.app.console.reset_mock()
        self._cmd("/memory vector list")
        global_calls = [str(c).lower() for c in self.app.console.print.call_args_list]
        self.assertTrue(
            any("global" in c for c in global_calls),
            "Expected 'global' scope label in default list output",
        )
        self.assertTrue(
            any("2" in c for c in global_calls),
            "Expected '2' total entries in global list output",
        )
        self.assertFalse(self.app.errors)

        # 2. Project scope: list --project (flag after subcommand)
        self.app.console.reset_mock()
        self._cmd("/memory vector list --project")
        project_calls = [str(c).lower() for c in self.app.console.print.call_args_list]
        self.assertTrue(
            any("project" in c for c in project_calls),
            "Expected 'project' scope label with 'list --project'",
        )
        self.assertTrue(
            any("3" in c for c in project_calls),
            "Expected '3' total entries in project list output",
        )
        self.assertFalse(self.app.errors)

        # 3. Project scope: --project list (flag before subcommand)
        self.app.console.reset_mock()
        self._cmd("/memory vector --project list")
        project_calls = [str(c).lower() for c in self.app.console.print.call_args_list]
        self.assertTrue(
            any("project" in c for c in project_calls),
            "Expected 'project' scope label with '--project list'",
        )
        self.assertTrue(
            any("3" in c for c in project_calls),
            "Expected '3' total entries in --project list output",
        )
        self.assertFalse(self.app.errors)

        # Counts unchanged
        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)

    def test_dispatcher_clear_cross_scope_isolation(self):
        """Cross-scope isolation: /memory vector [--project] clear

        Seeds both stores and verifies that ``clear`` targets only the
        global scope by default and ``--project clear`` targets only
        the project scope — all through the dispatcher chain.
        """
        # Seed global with 2 entries, project with 3 entries
        self._seed([
            ("global clear a", "test"),
            ("global clear b", "test"),
        ])
        self._seed([
            ("project clear c", "test"),
            ("project clear d", "test"),
            ("project clear e", "test"),
        ], target=self.project_memory)

        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)

        # Clear only project scope via --project clear
        self.app.messages.clear()
        self._cmd("/memory vector --project clear")
        self.assertEqual(
            self.project_memory.vector.count(), 0,
            "Expected project store to be cleared",
        )
        self.assertEqual(
            self.memory.vector.count(), 2,
            "Expected global store to be untouched after --project clear",
        )
        self.assertTrue(
            any("cleared" in m.lower() and "project" in m.lower() for m in self.app.messages),
            f"Expected 'cleared' and 'project' in message: {self.app.messages}",
        )
        self.assertFalse(self.app.errors)

        # Clear global scope via default clear
        self.app.messages.clear()
        self._cmd("/memory vector clear")
        self.assertEqual(
            self.memory.vector.count(), 0,
            "Expected global store to be cleared",
        )
        self.assertTrue(
            any("cleared" in m.lower() and "global" in m.lower() for m in self.app.messages),
            f"Expected 'cleared' and 'global' in message: {self.app.messages}",
        )
        self.assertFalse(self.app.errors)

    def test_dispatcher_delete_cross_scope_isolation(self):
        """Cross-scope isolation: /memory vector [--project] delete <id>

        Seeds both stores and verifies that ``delete --project <id>``
        removes only the targeted entry from the project store without
        affecting the global store, and vice versa — through the
        dispatcher chain.
        """
        # Seed global with 2 entries, project with 3 entries
        self._seed([
            ("global delete a", "test"),
            ("global delete b", "test"),
        ])
        project_ids: list[str] = []
        for content, cat in [
            ("project delete c", "test"),
            ("project delete d", "test"),
            ("project delete e", "test"),
        ]:
            eid = self.project_memory.long_term.store(content, category=cat)
            project_ids.append(eid)
        self._migrate(target=self.project_memory)

        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)

        # Delete a project entry using delete --project <id> (after subcommand)
        target_id = project_ids[0]
        self.app.messages.clear()
        self._cmd(f"/memory vector delete --project {target_id}")
        self.assertEqual(
            self.project_memory.vector.count(), 2,
            "Expected one project entry deleted",
        )
        self.assertEqual(
            self.memory.vector.count(), 2,
            "Expected global store unaffected by project delete",
        )
        self.assertTrue(
            any("deleted vector entry" in m.lower() and "project" in m.lower() for m in self.app.messages),
            f"Expected 'deleted' and 'project' in message: {self.app.messages}",
        )
        self.assertFalse(self.app.errors)

        # Delete a second project entry using --project delete <id> (before subcommand)
        target_id = project_ids[1]
        self.app.messages.clear()
        self._cmd(f"/memory vector --project delete {target_id}")
        self.assertEqual(
            self.project_memory.vector.count(), 1,
            "Expected two project entries deleted",
        )
        self.assertEqual(
            self.memory.vector.count(), 2,
            "Expected global store still unaffected",
        )
        self.assertFalse(self.app.errors)

    def test_dispatcher_query_cross_scope_isolation(self):
        """Cross-scope isolation: /memory vector [--project] query <text>

        Seeds both stores with distinct content and verifies that
        ``query`` searches the global store and ``query --project``
        searches the project store through the dispatcher chain.
        """
        # Seed global with entries about one topic, project with another
        self._seed([
            ("python async await programming patterns", "code"),
            ("python decorators and context managers", "code"),
        ])
        self._seed([
            ("project configuration and deployment", "config"),
            ("project env variables and secrets management", "config"),
            ("project docker compose setup", "config"),
        ], target=self.project_memory)

        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)

        # 1. Default (global) scope — should find global results
        self.app.messages.clear()
        self.app.console.reset_mock()
        self._cmd("/memory vector query python")
        global_calls = [str(c).lower() for c in self.app.console.print.call_args_list]
        # Should find results (printed via console) with "global" scope label
        self.assertTrue(
            any("global" in c for c in global_calls),
            "Expected 'global' scope label in default query output",
        )
        self.assertFalse(self.app.errors)

        # 2. Project scope with --project after subcommand: query --project <text>
        self.app.console.reset_mock()
        self._cmd("/memory vector query --project project")
        project_calls = [str(c).lower() for c in self.app.console.print.call_args_list]
        self.assertTrue(
            any("project" in c for c in project_calls),
            "Expected 'project' scope label with 'query --project'",
        )
        self.assertFalse(self.app.errors)

        # 3. Project scope with --project before subcommand: --project query <text>
        self.app.console.reset_mock()
        self._cmd("/memory vector --project query project")
        project_calls = [str(c).lower() for c in self.app.console.print.call_args_list]
        self.assertTrue(
            any("project" in c for c in project_calls),
            "Expected 'project' scope label with '--project query'",
        )
        self.assertFalse(self.app.errors)

        # Counts unchanged
        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)

    def test_dispatcher_rebuild_cross_scope_isolation(self):
        """Cross-scope isolation: /memory vector [--project] rebuild

        Seeds both stores and verifies that ``rebuild`` recomputes
        embeddings for the global store and ``--project rebuild``
        recomputes for the project store through the dispatcher
        chain — both non-destructive (counts unchanged).
        """
        # Seed global with 2 entries, project with 3 entries
        self._seed([
            ("global rebuild a", "test"),
            ("global rebuild b", "test"),
        ])
        self._seed([
            ("project rebuild c", "test"),
            ("project rebuild d", "test"),
            ("project rebuild e", "test"),
        ], target=self.project_memory)

        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)

        # 1. Default (global) scope
        self.app.messages.clear()
        self._cmd("/memory vector rebuild")
        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)
        self.assertTrue(
            any("rebuilt" in m.lower() and "global" in m.lower() for m in self.app.messages),
            f"Expected 'rebuilt' and 'global' in message: {self.app.messages}",
        )
        self.assertFalse(self.app.errors)

        # 2. Project scope via --project before subcommand
        self.app.messages.clear()
        self._cmd("/memory vector --project rebuild")
        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)
        self.assertTrue(
            any("rebuilt" in m.lower() and "project" in m.lower() for m in self.app.messages),
            f"Expected 'rebuilt' and 'project' in message: {self.app.messages}",
        )
        self.assertFalse(self.app.errors)

    def test_dispatcher_migrate_cross_scope_isolation(self):
        """Cross-scope isolation: /memory vector [--project] migrate

        Stores entries in FTS5 (without vector migration), then
        verifies that ``--project migrate`` populates only the
        project vector store and default ``migrate`` populates
        only the global vector store through the dispatcher chain.
        """
        # Store entries in FTS5 without migrating to vector
        self.memory.long_term.store("global migrate a", category="test")
        self.memory.long_term.store("global migrate b", category="test")
        self.project_memory.long_term.store("project migrate c", category="test")
        self.project_memory.long_term.store("project migrate d", category="test")
        self.project_memory.long_term.store("project migrate e", category="test")

        self.assertEqual(self.memory.vector.count(), 0)
        self.assertEqual(self.project_memory.vector.count(), 0)

        # 1. Migrate project scope → only project vector populated
        self.app.messages.clear()
        self._cmd("/memory vector --project migrate")
        self.assertEqual(
            self.project_memory.vector.count(), 3,
            "Expected 3 project entries migrated",
        )
        self.assertEqual(
            self.memory.vector.count(), 0,
            "Global vector store should be untouched by --project migrate",
        )
        self.assertTrue(
            any("migration complete" in m.lower() and "project" in m.lower() for m in self.app.messages),
            f"Expected 'migration complete' and 'project' in message: {self.app.messages}",
        )
        self.assertFalse(self.app.errors)

        # 2. Migrate global scope → global vector populated
        self.app.messages.clear()
        self._cmd("/memory vector migrate")
        self.assertEqual(
            self.memory.vector.count(), 2,
            "Expected 2 global entries migrated",
        )
        self.assertEqual(
            self.project_memory.vector.count(), 3,
            "Project vector store should be unaffected by global migrate",
        )
        self.assertTrue(
            any("migration complete" in m.lower() and "global" in m.lower() for m in self.app.messages),
            f"Expected 'migration complete' and 'global' in message: {self.app.messages}",
        )
        self.assertFalse(self.app.errors)

    def test_dispatcher_categories_cross_scope_isolation(self):
        """Cross-scope isolation: /memory vector [--project] categories

        Seeds both stores and verifies that ``categories`` renders
        the global store categories and ``--project categories``
        renders the project store categories through the dispatcher
        chain. Uses ``console.print.called`` for scope verification
        since categories outputs a Rich ``Table``.
        """
        # Seed global with 2 entries, project with 3 entries
        self._seed([
            ("global cat a", "code"),
            ("global cat b", "config"),
        ])
        self._seed([
            ("project cat c", "config"),
            ("project cat d", "devops"),
            ("project cat e", "test"),
        ], target=self.project_memory)

        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)

        # 1. Default (global) scope
        self.app.console.reset_mock()
        self._cmd("/memory vector categories")
        calls = [str(c).lower() for c in self.app.console.print.call_args_list]
        self.assertTrue(
            any("global" in c for c in calls),
            "Expected 'global' scope label in default categories output",
        )
        self.assertFalse(self.app.errors)

        # 2. Project scope via --project before subcommand
        self.app.console.reset_mock()
        self._cmd("/memory vector --project categories")
        calls = [str(c).lower() for c in self.app.console.print.call_args_list]
        self.assertTrue(
            any("project" in c for c in calls),
            "Expected 'project' scope label in --project categories output",
        )
        self.assertFalse(self.app.errors)

        # Counts unchanged — both stores fully intact
        self.assertEqual(self.memory.vector.count(), 2)
        self.assertEqual(self.project_memory.vector.count(), 3)

    def test_dispatcher_download_cross_scope_isolation(self):
        """Cross-scope isolation: /memory vector [--project] download

        Seeds both stores and verifies that ``download`` targets the
        global scope by default and ``--project download`` targets the
        project store through the dispatcher chain.

        Uses the ``_vector_use_project`` flag (which controls which
        store ``_get_vector_store()`` resolves) to verify scope
        routing. The actual download handler is temporarily replaced
        with a no-op since it requires a real ONNX engine and network
        access unavailable in test environments.
        """
        # Temporarily replace the download handler to prevent network calls
        original_download = self.app._cmd_memory_vector_download

        def _mock_download():
            pass

        self.app._cmd_memory_vector_download = _mock_download

        try:
            # Seed global with 2 entries, project with 3 entries
            self._seed([
                ("global dl a", "code"),
                ("global dl b", "config"),
            ])
            self._seed([
                ("project dl c", "config"),
                ("project dl d", "config"),
                ("project dl e", "devops"),
            ], target=self.project_memory)

            self.assertEqual(self.memory.vector.count(), 2)
            self.assertEqual(self.project_memory.vector.count(), 3)

            # 1. Default scope → global download (flag is False)
            self._cmd("/memory vector download")
            self.assertFalse(
                self.app._vector_use_project,
                "Expected _vector_use_project to be False after default download",
            )
            self.assertFalse(self.app.errors)

            # 2. Project scope via --project before subcommand
            self.app.messages.clear()
            self.app.errors.clear()
            self._cmd("/memory vector --project download")
            self.assertTrue(
                self.app._vector_use_project,
                "Expected _vector_use_project to be True after --project download",
            )
            self.assertFalse(self.app.errors)

            # Counts unchanged — both stores fully intact
            self.assertEqual(self.memory.vector.count(), 2)
            self.assertEqual(self.project_memory.vector.count(), 3)
        finally:
            self.app._cmd_memory_vector_download = original_download

    def test_dispatcher_memory_help_shows_vector(self):
        """/memory with no args shows help including vector section."""
        self._cmd("/memory")
        # Should mention vector in the help output
        self.assertTrue(
            any("vector" in str(call).lower() for call in self.app.console.print.call_args_list),
            "Expected /memory help to mention vector subsystem",
        )
