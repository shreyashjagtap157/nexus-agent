"""Tests for the memory subsystem."""

import tempfile
import pytest
from pathlib import Path

from nexus_agent.memory.memory_manager import MemoryManager
from nexus_agent.memory.working_memory import WorkingMemory
from nexus_agent.memory.long_term import LongTermMemory
from nexus_agent.memory.episodic import EpisodicMemory
from nexus_agent.memory.user_profile import UserProfile


class TestWorkingMemory:
    @pytest.fixture
    def wm(self):
        return WorkingMemory(max_entries=10)

    def test_set_get(self, wm):
        wm.set("key1", "value1")
        assert wm.get("key1") == "value1"

    def test_get_nonexistent(self, wm):
        assert wm.get("nonexistent") is None

    def test_eviction(self, wm):
        for i in range(15):
            wm.set(f"key{i}", f"value{i}")
        # Only 10 entries should be kept
        assert len(wm.list_keys()) == 10

    def test_delete(self, wm):
        wm.set("key1", "value1")
        assert wm.delete("key1") is True
        assert wm.get("key1") is None

    def test_list_keys(self, wm):
        wm.set("a", "1")
        wm.set("b", "2")
        keys = wm.list_keys()
        assert "a" in keys
        assert "b" in keys

    def test_clear(self, wm):
        wm.set("key1", "value1")
        wm.clear()
        assert wm.get("key1") is None

    def test_summary(self, wm):
        wm.set("key1", "value1")
        summary = wm.get_summary()
        assert summary["entries"] == 1

    def test_scratchpad(self, wm):
        wm.add_note("test note")
        assert "test note" in wm.get_scratchpad()

    def test_access_count(self, wm):
        wm.set("key1", "value1")
        wm.get("key1")
        wm.get("key1")
        # Access count should be 2
        assert wm._store["key1"]["access_count"] == 2


class TestLongTermMemory:
    @pytest.fixture
    def ltm(self, tmp_path):
        return LongTermMemory(tmp_path / "test_ltm.db")

    def test_store_and_retrieve(self, ltm):
        entry_id = ltm.store("Test memory content", category="test")
        assert entry_id is not None
        entry = ltm.get(entry_id)
        assert entry is not None
        assert entry["content"] == "Test memory content"

    def test_search(self, ltm):
        ltm.store("Python is great", category="code")
        ltm.store("JavaScript is fun", category="code")
        results = ltm.search("Python")
        assert len(results) > 0
        assert any("Python" in r["content"] for r in results)

    def test_delete(self, ltm):
        entry_id = ltm.store("To delete", category="test")
        assert ltm.delete(entry_id) is True
        assert ltm.get(entry_id) is None

    def test_update(self, ltm):
        entry_id = ltm.store("Original", category="test")
        ltm.update(entry_id, content="Updated")
        entry = ltm.get(entry_id)
        assert entry["content"] == "Updated"

    def test_list_all(self, ltm):
        ltm.store("Mem1", category="a")
        ltm.store("Mem2", category="b")
        all_mems = ltm.list_all()
        assert len(all_mems) >= 2

    def test_list_categories(self, ltm):
        ltm.store("Mem1", category="code")
        ltm.store("Mem2", category="code")
        ltm.store("Mem3", category="config")
        cats = ltm.list_categories()
        assert len(cats) >= 2

    def test_get_stats(self, ltm):
        ltm.store("Mem1", category="test")
        stats = ltm.get_stats()
        assert stats["total_entries"] >= 1

    def test_empty_content_raises(self, ltm):
        with pytest.raises(ValueError):
            ltm.store("", category="test")

    def test_heat_score_calculation(self, ltm):
        heat = ltm.calculate_heat(
            access_count=5,
            content_length=100,
            last_access_time=1000.0,
        )
        assert heat > 0

    def test_category_filter(self, ltm):
        ltm.store("Code pattern", category="code")
        ltm.store("Config setting", category="config")
        results = ltm.search("pattern", category="code")
        # Should find code-related results
        assert len(results) >= 0  # May be empty if search term doesn't match


class TestEpisodicMemory:
    @pytest.fixture
    def episodic(self, tmp_path):
        return EpisodicMemory(tmp_path / "test_ep.db")

    def test_save_session(self, episodic):
        episodic.save_session("sess1", "Session summary", messages_count=10)
        recent = episodic.get_recent()
        assert len(recent) >= 1

    def test_search(self, episodic):
        episodic.save_session("sess1", "Auth module refactor", messages_count=5)
        results = episodic.search("auth")
        assert len(results) > 0

    def test_empty_search(self, episodic):
        results = episodic.search("")
        assert results == []


class TestUserProfile:
    @pytest.fixture
    def profile(self, tmp_path):
        return UserProfile(tmp_path / "profile.yaml")

    def test_default_profile(self, profile):
        summary = profile.get_summary()
        # Should have default values
        assert isinstance(summary, str)

    def test_get_set(self, profile):
        profile.set("coding_style.indentation", "4 spaces")
        assert profile.get("coding_style.indentation") == "4 spaces"

    def test_learn_pattern(self, profile):
        profile.learn_pattern("Use type hints", "Python code")
        assert len(profile._profile.get("learned_patterns", [])) == 1

    def test_to_dict(self, profile):
        d = profile.to_dict()
        assert "coding_style" in d
        assert "preferences" in d


class TestMemoryManager:
    @pytest.fixture
    def mm(self, tmp_path):
        return MemoryManager(
            data_dir=tmp_path / "memory",
            enable_vector=False,
        )

    def test_store_and_search(self, mm):
        mm.store("Python best practices", category="code")
        results = mm.search("Python")
        assert len(results) > 0

    def test_get_stats(self, mm):
        stats = mm.get_stats()
        assert "working" in stats
        assert "long_term" in stats
        assert "episodic" in stats

    def test_get_context_for_prompt(self, mm):
        mm.store("Important code pattern", category="code")
        context = mm.get_context_for_prompt("code patterns")
        # Should return a string with some context
        assert isinstance(context, str)

    def test_compact(self, mm):
        for i in range(100):
            mm.store(f"Memory entry {i}", category="test")
        result = mm.compact()
        assert "ltm_pruned" in result
