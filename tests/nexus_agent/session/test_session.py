"""Tests for session management."""

import pytest
from pathlib import Path

from nexus_agent.session.manager import SessionManager
from nexus_agent.session.storage import SessionStorage
from nexus_agent.session.checkpoint import CheckpointManager


class TestSessionStorage:
    @pytest.fixture
    def storage(self, tmp_path):
        return SessionStorage(tmp_path / "test_sessions.db")

    def test_create_session(self, storage):
        storage.create_session("test123", model="test-model", provider="test")
        session = storage.get_session("test123")
        assert session is not None
        assert session["id"] == "test123"

    def test_list_sessions(self, storage):
        storage.create_session("s1", model="m1")
        storage.create_session("s2", model="m2")
        sessions = storage.list_sessions()
        assert len(sessions) >= 2

    def test_save_message(self, storage):
        storage.create_session("test123")
        msg_id = storage.save_message(
            "test123", role="user", content="Hello"
        )
        assert msg_id is not None

    def test_get_messages(self, storage):
        storage.create_session("test123")
        storage.save_message("test123", role="user", content="Hello")
        storage.save_message("test123", role="assistant", content="Hi")
        messages = storage.get_messages("test123")
        assert len(messages) == 2

    def test_delete_session(self, storage):
        storage.create_session("test123")
        assert storage.delete_session("test123") is True
        assert storage.get_session("test123") is None

    def test_count_sessions(self, storage):
        storage.create_session("s1")
        storage.create_session("s2")
        count = storage.count_sessions()
        assert count >= 2

    def test_update_title(self, storage):
        storage.create_session("test123", title="Original")
        storage.update_session_title("test123", "Updated")
        session = storage.get_session("test123")
        assert session["title"] == "Updated"

    def test_touch_session(self, storage):
        storage.create_session("test123")
        storage.touch_session("test123")
        session = storage.get_session("test123")
        assert session["updated_at"] > 0


class TestSessionManager:
    @pytest.fixture
    def sm(self, tmp_path):
        return SessionManager(
            data_dir=tmp_path / "sessions",
            auto_save=False,
        )

    def test_create_session(self, sm):
        sid = sm.create_session(model="test", provider="test")
        assert sid is not None
        assert len(sid) == 12

    def test_resume_session(self, sm):
        sid = sm.create_session(model="test", provider="test")
        resumed = sm.resume_session(sid)
        assert resumed is not None
        assert resumed["id"] == sid

    def test_resume_nonexistent(self, sm):
        result = sm.resume_session("nonexistent")
        assert result is None

    def test_save_message(self, sm):
        sid = sm.create_session(model="test", provider="test")
        sm.save_message("user", content="Hello")
        messages = sm.get_messages()
        assert len(messages) >= 1

    def test_list_sessions(self, sm):
        sm.create_session(model="m1")
        sm.create_session(model="m2")
        sessions = sm.list_sessions()
        assert len(sessions) >= 2

    def test_delete_session(self, sm):
        sid = sm.create_session(model="test", provider="test")
        assert sm.delete_session(sid) is True

    def test_count_sessions(self, sm):
        sm.create_session(model="m1")
        count = sm.count_sessions()
        assert count >= 1

    def test_fork_session(self, sm):
        sid = sm.create_session(model="test", provider="test")
        sm.save_message("user", content="Hello")
        new_id = sm.fork_session("Forked")
        assert new_id is not None
        assert new_id != sid

    def test_rename_session(self, sm):
        sid = sm.create_session(model="test", provider="test")
        assert sm.rename_session("New Name") is True
        info = sm.get_session_info()
        assert info["title"] == "New Name"

    def test_export_session(self, sm):
        sid = sm.create_session(model="test", provider="test")
        sm.save_message("user", content="Hello")
        exported = sm.export_session(sid)
        assert "session" in exported
        assert "messages" in exported

    def test_get_session_info(self, sm):
        sm.create_session(model="test", provider="test")
        info = sm.get_session_info()
        assert "active_session_id" in info
        assert "total_sessions" in info

    def test_auto_title(self, sm):
        sm.create_session(model="test", provider="test")
        sm.auto_title("This is a test message")
        info = sm.get_session_info()
        assert info["title"] == "This is a test message"

    def test_get_messages_count(self, sm):
        sm.create_session(model="test", provider="test")
        sm.save_message("user", content="Hello")
        sm.save_message("assistant", content="Hi")
        count = sm.get_messages_count()
        assert count == 2


class TestCheckpointManager:
    @pytest.fixture
    def cm(self, tmp_path):
        return CheckpointManager(data_dir=tmp_path / "checkpoints")

    def test_create_checkpoint(self, cm):
        cp = cm.create(
            files_to_snapshot=[],
            description="Test checkpoint",
        )
        assert cp is not None
        assert cp.id.startswith("cp_")

    def test_list_checkpoints(self, cm):
        cm.create(files_to_snapshot=[], description="Test")
        checkpoints = cm.list_checkpoints()
        assert len(checkpoints) >= 1

    def test_get_checkpoint(self, cm):
        cp = cm.create(files_to_snapshot=[], description="Test")
        found = cm.get(cp.id)
        assert found is not None

    def test_get_nonexistent(self, cm):
        assert cm.get("nonexistent") is None

    def test_clear_checkpoints(self, cm):
        cm.create(files_to_snapshot=[], description="Test")
        cm.clear()
        assert len(cm.list_checkpoints()) == 0
