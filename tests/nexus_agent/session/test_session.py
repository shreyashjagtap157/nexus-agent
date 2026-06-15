"""Tests for the session module — SessionManager, SessionStorage, CheckpointManager."""

import tempfile
import unittest
from pathlib import Path

from nexus_agent.session.checkpoint import CheckpointManager
from nexus_agent.session.manager import SessionManager


class TestSessionManager(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmpdir.name) / "sessions"
        self.mgr = SessionManager(
            data_dir=self.data_dir,
            auto_save=False,
            auto_save_interval=0,
        )

    def tearDown(self):
        self.mgr.close()
        self.tmpdir.cleanup()

    def test_create_session(self):
        sid = self.mgr.create_session(
            model="gpt-4o",
            provider="openai",
            workspace=str(self.tmpdir.name),
        )
        self.assertIsNotNone(sid)
        self.assertEqual(self.mgr.active_session_id, sid)

    def test_resume_session_partial_match(self):
        sid = self.mgr.create_session(
            model="claude-3", provider="anthropic", workspace=str(self.tmpdir.name),
        )
        resumed = self.mgr.resume_session(sid[:8])
        self.assertIsNotNone(resumed)

    def test_list_sessions(self):
        self.mgr.create_session(model="m1", provider="p1", workspace=str(self.tmpdir.name))
        self.mgr.create_session(model="m2", provider="p2", workspace=str(self.tmpdir.name))
        sessions = self.mgr.list_sessions(limit=10)
        self.assertGreaterEqual(len(sessions), 2)

    def test_save_message(self):
        self.mgr.create_session(model="m", provider="p", workspace=str(self.tmpdir.name))
        self.mgr.save_message(role="user", content="hello")
        self.mgr.save_message(role="assistant", content="world")
        msgs = self.mgr.get_active_session()
        self.assertIsNotNone(msgs)

    def test_delete_session(self):
        sid = self.mgr.create_session(model="m", provider="p", workspace=str(self.tmpdir.name))
        self.assertTrue(self.mgr.delete_session(sid))
        self.assertIsNone(self.mgr.resume_session(sid))

    def test_rename_session(self):
        self.mgr.create_session(model="m", provider="p", workspace=str(self.tmpdir.name))
        self.assertTrue(self.mgr.rename_session("New Name"))

    def test_count_sessions(self):
        before = self.mgr.count_sessions()
        self.mgr.create_session(model="m", provider="p", workspace=str(self.tmpdir.name))
        self.assertEqual(self.mgr.count_sessions(), before + 1)

    def test_fork_session(self):
        self.mgr.create_session(model="m", provider="p", workspace=str(self.tmpdir.name))
        self.mgr.save_message(role="user", content="original")
        forked = self.mgr.fork_session(new_title="Forked")
        self.assertIsNotNone(forked)

    def test_track_file_change(self):
        self.mgr.create_session(model="m", provider="p", workspace=str(self.tmpdir.name))
        self.mgr.track_file_change("src/main.py", "modified", "old", "new")


class TestCheckpointManager(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmpdir.name) / "checkpoints"
        self.cpm = CheckpointManager(data_dir=self.data_dir)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_create_and_list(self):
        test_file = Path(self.tmpdir.name) / "test.txt"
        test_file.write_text("original content")
        cp = self.cpm.create(files_to_snapshot=[str(test_file)], description="snapshot")
        self.assertIsNotNone(cp)
        entries = self.cpm.list_checkpoints()
        self.assertGreaterEqual(len(entries), 1)

    def test_rollback(self):
        test_file = Path(self.tmpdir.name) / "rollback.txt"
        test_file.write_text("v1")
        cp = self.cpm.create(files_to_snapshot=[str(test_file)], description="v1")
        test_file.write_text("v2")
        result = self.cpm.rollback(cp.id)
        self.assertIn(str(test_file), result)
        self.assertEqual(test_file.read_text(), "v1")

    def test_get_latest(self):
        test_file = Path(self.tmpdir.name) / "f.txt"
        test_file.write_text("data")
        self.cpm.create(files_to_snapshot=[str(test_file)], description="first")
        latest = self.cpm.get_latest()
        self.assertIsNotNone(latest)

    def test_clear(self):
        test_file = Path(self.tmpdir.name) / "f.txt"
        test_file.write_text("data")
        self.cpm.create(files_to_snapshot=[str(test_file)], description="cp")
        self.cpm.clear()
        self.assertEqual(self.cpm.list_checkpoints(), [])
