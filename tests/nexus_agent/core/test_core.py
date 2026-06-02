"""Tests for core module — config, sqlite_store, context (remaining untested files)."""

import json
import tempfile
import unittest
from pathlib import Path

from nexus_agent.core.config import load_config, save_config
from nexus_agent.core.sqlite_store import SQLiteStore


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.config_dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_load_config_defaults(self):
        config = load_config(workspace=self.config_dir, data_dir=self.config_dir)
        self.assertIsInstance(config, dict)
        self.assertIn("agent", config)

    def test_save_and_load_config(self):
        config_path = self.config_dir / "config.json"
        conf = {"agent": {"mode": "plan"}, "theme": "dark"}
        save_config(conf, config_path=str(config_path))
        loaded = load_config(config_path=str(config_path), workspace=self.config_dir, data_dir=self.config_dir)
        self.assertEqual(loaded.get("agent", {}).get("mode"), "plan")
        self.assertEqual(loaded.get("theme"), "dark")

    def test_load_config_with_config_path(self):
        custom_path = self.config_dir / "custom_config.json"
        custom_path.write_text(json.dumps({"custom": True}), encoding="utf-8")
        config = load_config(
            config_path=str(custom_path),
            workspace=self.config_dir,
            data_dir=self.config_dir,
        )
        self.assertTrue(config.get("custom"))


class TestSQLiteStore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test.db"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_init_and_close(self):
        class TestStore(SQLiteStore):
            SCHEMA_SQL = "CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY, value TEXT);"
        store = TestStore(self.db_path)
        conn = store._get_conn()
        cursor = conn.execute("SELECT COUNT(*) FROM test")
        self.assertEqual(cursor.fetchone()[0], 0)
        store.close()

    def test_context_manager(self):
        class TestStore(SQLiteStore):
            SCHEMA_SQL = ""
        with TestStore(self.db_path) as store:
            conn = store._get_conn()
            self.assertIsNotNone(conn)

    def test_thread_safety_lock(self):
        class TestStore(SQLiteStore):
            SCHEMA_SQL = ""
        store = TestStore(self.db_path)
        self.assertTrue(hasattr(store, "_lock"))
        store.close()
