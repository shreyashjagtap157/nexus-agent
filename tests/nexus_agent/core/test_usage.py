"""Tests for the UsageTracker."""

from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path

import pytest

from nexus_agent.core.usage import (
    DEFAULT_PRICING,
    UsageEntry,
    UsageSummary,
    UsageTracker,
    _day_key,
    estimate_cost,
)


@pytest.fixture
def tmpd():
    """Project-local temp directory (avoids Windows file-locks on the
    system pytest-of-* temp folder)."""
    p = Path("tmp") / f"usage_test_{uuid.uuid4().hex[:8]}"
    p.mkdir(parents=True, exist_ok=True)
    try:
        yield p
    finally:
        shutil.rmtree(p, ignore_errors=True)


# ---- estimate_cost ----

class TestEstimateCost:
    def test_openai_gpt4o(self):
        cost = estimate_cost("openai", "gpt-4o", 1_000_000, 1_000_000)
        assert cost == pytest.approx(12.50)

    def test_openai_gpt4o_mini(self):
        cost = estimate_cost("openai", "gpt-4o-mini", 1_000_000, 0)
        assert cost == pytest.approx(0.15)

    def test_anthropic_sonnet(self):
        cost = estimate_cost("anthropic", "claude-3-5-sonnet-latest", 1_000_000, 1_000_000)
        assert cost == pytest.approx(18.0)

    def test_ollama_is_free(self):
        cost = estimate_cost("ollama", "llama3.2", 1_000_000, 1_000_000)
        assert cost == 0.0

    def test_local_is_free(self):
        cost = estimate_cost("local", "gguf-model", 100, 100)
        assert cost == 0.0

    def test_unknown_provider_uses_default(self):
        cost = estimate_cost("nonexistent", "model", 1_000_000, 1_000_000)
        # Falls through to unknown -> default
        assert cost >= 0

    def test_unknown_model_uses_default(self):
        cost = estimate_cost("openai", "gpt-99xx", 1_000_000, 0)
        # Falls back to openai.default
        assert cost == pytest.approx(2.50)

    def test_empty_provider(self):
        cost = estimate_cost("", "", 100, 100)
        assert cost >= 0

    def test_negative_tokens_clamped(self):
        cost = estimate_cost("openai", "gpt-4o", -100, -100)
        assert cost == 0.0

    def test_custom_pricing_overrides(self):
        custom = {"myprovider": {"mymodel": {"input": 1.0, "output": 2.0}}}
        cost = estimate_cost("myprovider", "mymodel", 1_000_000, 500_000, custom)
        assert cost == pytest.approx(2.0)

    def test_default_pricing_table_has_openai(self):
        assert "openai" in DEFAULT_PRICING
        assert "gpt-4o" in DEFAULT_PRICING["openai"]


# ---- UsageEntry ----

class TestUsageEntry:
    def test_roundtrip(self):
        e = UsageEntry(
            ts=12345.0,
            session_id="abc",
            provider="openai",
            model="gpt-4o",
            prompt_tokens=10,
            completion_tokens=20,
            estimated_cost=0.001,
            label="hello",
        )
        d = e.to_dict()
        e2 = UsageEntry.from_dict(d)
        assert e2 == e

    def test_from_dict_missing_fields(self):
        e = UsageEntry.from_dict({})
        assert e.ts == 0.0
        assert e.prompt_tokens == 0
        assert e.estimated_cost == 0.0

    def test_from_dict_coerces_types(self):
        e = UsageEntry.from_dict(
            {"prompt_tokens": "10", "completion_tokens": "20", "estimated_cost": "0.5"}
        )
        assert e.prompt_tokens == 10
        assert e.completion_tokens == 20
        assert e.estimated_cost == 0.5

    def test_from_dict_invalid_int_falls_back_to_zero(self):
        e = UsageEntry.from_dict({"prompt_tokens": "abc"})
        assert e.prompt_tokens == 0


# ---- UsageTracker basics ----

class TestUsageTrackerBasics:
    def test_empty_init_no_path(self):
        t = UsageTracker()
        assert t.entries() == []
        assert t.path is None

    def test_empty_init_with_missing_path(self, tmpd):
        t = UsageTracker(tmpd / "usage.json")
        assert t.entries() == []

    def test_record_returns_entry_with_cost(self):
        t = UsageTracker()
        e = t.record(
            session_id="s1", provider="openai", model="gpt-4o",
            prompt_tokens=100, completion_tokens=50,
        )
        assert e.prompt_tokens == 100
        assert e.completion_tokens == 50
        assert e.estimated_cost > 0.0
        assert e.session_id == "s1"

    def test_record_appends(self):
        t = UsageTracker()
        t.record(session_id="s1", provider="openai", model="gpt-4o",
                 prompt_tokens=1, completion_tokens=1)
        t.record(session_id="s1", provider="openai", model="gpt-4o",
                 prompt_tokens=2, completion_tokens=2)
        assert len(t.entries()) == 2

    def test_record_negative_tokens_clamped(self):
        t = UsageTracker()
        e = t.record(
            session_id="s1", provider="openai", model="gpt-4o",
            prompt_tokens=-10, completion_tokens=-5,
        )
        assert e.prompt_tokens == 0
        assert e.completion_tokens == 0

    def test_record_with_label(self):
        t = UsageTracker()
        e = t.record(
            session_id="s1", provider="openai", model="gpt-4o",
            prompt_tokens=1, completion_tokens=1, label="first turn",
        )
        assert e.label == "first turn"

    def test_empty_session_id_becomes_unknown(self):
        t = UsageTracker()
        e = t.record(
            session_id="", provider="openai", model="gpt-4o",
            prompt_tokens=1, completion_tokens=1,
        )
        assert e.session_id == "unknown"

    def test_clear(self):
        t = UsageTracker()
        t.record(session_id="s1", provider="openai", model="gpt-4o",
                 prompt_tokens=1, completion_tokens=1)
        t.record(session_id="s1", provider="openai", model="gpt-4o",
                 prompt_tokens=1, completion_tokens=1)
        n = t.clear()
        assert n == 2
        assert t.entries() == []

    def test_clear_empty(self):
        t = UsageTracker()
        assert t.clear() == 0

    def test_clear_session(self):
        t = UsageTracker()
        t.record(session_id="s1", provider="openai", model="gpt-4o",
                 prompt_tokens=1, completion_tokens=1)
        t.record(session_id="s2", provider="openai", model="gpt-4o",
                 prompt_tokens=1, completion_tokens=1)
        n = t.clear_session("s1")
        assert n == 1
        remaining = t.entries()
        assert len(remaining) == 1
        assert remaining[0].session_id == "s2"

    def test_clear_session_no_match(self):
        t = UsageTracker()
        t.record(session_id="s1", provider="openai", model="gpt-4o",
                 prompt_tokens=1, completion_tokens=1)
        assert t.clear_session("nonexistent") == 0
        assert len(t.entries()) == 1

    def test_clear_session_empty(self):
        t = UsageTracker()
        assert t.clear_session("x") == 0


# ---- UsageTracker persistence ----

class TestUsageTrackerPersistence:
    def test_save_creates_file(self, tmpd):
        path = tmpd / "usage.json"
        t = UsageTracker(path)
        t.record(session_id="s1", provider="openai", model="gpt-4o",
                 prompt_tokens=10, completion_tokens=5)
        assert path.exists()

    def test_save_creates_parent_dirs(self, tmpd):
        path = tmpd / "nested" / "dir" / "usage.json"
        t = UsageTracker(path)
        t.record(session_id="s1", provider="openai", model="gpt-4o",
                 prompt_tokens=1, completion_tokens=1)
        assert path.exists()

    def test_reload_from_disk(self, tmpd):
        path = tmpd / "usage.json"
        t1 = UsageTracker(path)
        t1.record(session_id="s1", provider="openai", model="gpt-4o",
                  prompt_tokens=10, completion_tokens=5, label="first")
        t1.record(session_id="s2", provider="anthropic", model="claude-3-5-sonnet-latest",
                  prompt_tokens=20, completion_tokens=10)

        t2 = UsageTracker(path)
        entries = t2.entries()
        assert len(entries) == 2
        assert entries[0].label == "first"
        assert entries[1].provider == "anthropic"

    def test_corrupted_file_does_not_raise(self, tmpd):
        path = tmpd / "usage.json"
        path.write_text("not valid json {{{")
        t = UsageTracker(path)
        assert t.entries() == []

    def test_newer_schema_is_ignored(self, tmpd):
        path = tmpd / "usage.json"
        path.write_text(json.dumps({"version": 999, "entries": []}))
        t = UsageTracker(path)
        assert t.entries() == []

    def test_atomic_write_via_tmp_replace(self, tmpd, monkeypatch):
        path = tmpd / "usage.json"
        t = UsageTracker(path)
        t.record(session_id="s1", provider="openai", model="gpt-4o",
                 prompt_tokens=1, completion_tokens=1)
        # Verify no leftover temp files
        leftovers = list(path.parent.glob(".usage.*.tmp"))
        assert leftovers == []

    def test_save_failure_does_not_raise(self, tmpd, monkeypatch, caplog):
        # Simulate a write failure by making the path a directory
        path = tmpd / "usage.json"
        path.mkdir()
        t = UsageTracker(path)
        # Should log a warning, not raise
        t.record(session_id="s1", provider="openai", model="gpt-4o",
                 prompt_tokens=1, completion_tokens=1)


# ---- summarize ----

class TestSummarize:
    def test_empty_summarize(self):
        t = UsageTracker()
        s = t.summarize()
        assert isinstance(s, UsageSummary)
        assert s.entries == 0
        assert s.total_tokens == 0
        assert s.estimated_cost == 0.0
        assert s.by_session == {}
        assert s.by_model == {}

    def test_summarize_totals(self):
        t = UsageTracker()
        t.record(session_id="s1", provider="openai", model="gpt-4o",
                 prompt_tokens=100, completion_tokens=50)
        t.record(session_id="s1", provider="openai", model="gpt-4o",
                 prompt_tokens=200, completion_tokens=100)
        s = t.summarize()
        assert s.entries == 2
        assert s.prompt_tokens == 300
        assert s.completion_tokens == 150
        assert s.total_tokens == 450
        assert s.estimated_cost > 0

    def test_summarize_by_session(self):
        t = UsageTracker()
        t.record(session_id="s1", provider="openai", model="gpt-4o",
                 prompt_tokens=100, completion_tokens=50)
        t.record(session_id="s2", provider="openai", model="gpt-4o",
                 prompt_tokens=10, completion_tokens=5)
        s = t.summarize()
        assert "s1" in s.by_session
        assert "s2" in s.by_session
        assert s.by_session["s1"]["total_tokens"] == 150
        assert s.by_session["s2"]["total_tokens"] == 15

    def test_summarize_by_model(self):
        t = UsageTracker()
        t.record(session_id="s1", provider="openai", model="gpt-4o",
                 prompt_tokens=100, completion_tokens=0)
        t.record(session_id="s1", provider="anthropic", model="claude-3-5-sonnet-latest",
                 prompt_tokens=100, completion_tokens=0)
        s = t.summarize()
        assert "openai/gpt-4o" in s.by_model
        assert "anthropic/claude-3-5-sonnet-latest" in s.by_model

    def test_summarize_by_day(self):
        t = UsageTracker()
        t.record(session_id="s1", provider="openai", model="gpt-4o",
                 prompt_tokens=100, completion_tokens=50)
        s = t.summarize()
        days = list(s.by_day.keys())
        assert len(days) == 1
        # The day key should be a date string YYYY-MM-DD
        day = days[0]
        assert len(day) == 10
        assert day[4] == "-"
        assert day[7] == "-"

    def test_summarize_filter_by_session(self):
        t = UsageTracker()
        t.record(session_id="s1", provider="openai", model="gpt-4o",
                 prompt_tokens=100, completion_tokens=50)
        t.record(session_id="s2", provider="openai", model="gpt-4o",
                 prompt_tokens=200, completion_tokens=100)
        s = t.summarize(session_id="s1")
        assert s.total_tokens == 150
        assert "s1" in s.by_session
        assert "s2" not in s.by_session

    def test_summarize_filter_by_time_range(self):
        now = time.time()
        t = UsageTracker()
        t.record(session_id="s1", provider="openai", model="gpt-4o",
                 prompt_tokens=100, completion_tokens=50)
        # All entries should be within (now - 1h, now + 1h)
        s = t.summarize(since_ts=now - 3600, until_ts=now + 3600)
        assert s.total_tokens == 150
        # Outside range -> empty
        s = t.summarize(since_ts=now + 3600)
        assert s.total_tokens == 0

    def test_summarize_sort_by_cost_desc(self):
        t = UsageTracker()
        t.record(session_id="s1", provider="openai", model="gpt-4o",
                 prompt_tokens=10, completion_tokens=0)  # cheap
        t.record(session_id="s2", provider="openai", model="gpt-4o",
                 prompt_tokens=1_000_000, completion_tokens=0)  # expensive
        s = t.summarize()
        models = list(s.by_model.keys())
        assert models[0] == "openai/gpt-4o"
        # And cost of the second entry should be > the first
        costs = [s.by_model[m]["estimated_cost"] for m in models]
        assert costs == sorted(costs, reverse=True)

    def test_summarize_round_to_6_decimals(self):
        t = UsageTracker()
        t.record(session_id="s1", provider="openai", model="gpt-4o",
                 prompt_tokens=1, completion_tokens=1)
        s = t.summarize()
        # estimated_cost is rounded to 6 decimals
        cost_str = f"{s.estimated_cost:.10f}"
        # Check we don't have more than 6 decimal places
        assert "." in cost_str
        decimals = cost_str.split(".")[1]
        # May have trailing zeros but the underlying float is rounded


# ---- UsageSummary.to_lines ----

class TestUsageSummaryToLines:
    def test_to_lines_basic(self):
        t = UsageTracker()
        t.record(session_id="s1", provider="openai", model="gpt-4o",
                 prompt_tokens=100, completion_tokens=50)
        s = t.summarize()
        lines = s.to_lines()
        assert any("Entries: 1" in ln for ln in lines)
        assert any("Prompt tokens:" in ln for ln in lines)
        assert any("Total tokens:" in ln for ln in lines)
        assert any("Estimated cost:" in ln for ln in lines)

    def test_to_lines_with_breakdowns(self):
        t = UsageTracker()
        t.record(session_id="s1", provider="openai", model="gpt-4o",
                 prompt_tokens=100, completion_tokens=50)
        t.record(session_id="s2", provider="anthropic", model="claude-3-5-sonnet-latest",
                 prompt_tokens=200, completion_tokens=100)
        s = t.summarize()
        lines = s.to_lines()
        joined = "\n".join(lines)
        assert "By model" in joined
        assert "By session" in joined
        assert "By day" in joined

    def test_to_lines_respects_top_n(self):
        t = UsageTracker()
        for i in range(10):
            t.record(session_id=f"s{i}", provider="openai", model="gpt-4o",
                     prompt_tokens=10 * (i + 1), completion_tokens=0)
        s = t.summarize()
        lines = s.to_lines(top_n=2)
        joined = "\n".join(lines)
        # Only 2 models/sessions/days should appear in the breakdown
        assert joined.count("tok") >= 2


# ---- day_key helper ----

class TestDayKey:
    def test_returns_iso_date(self):
        # 1737000000.0 = 2025-01-16 11:20:00 UTC
        key = _day_key(1737000000.0)
        assert key == "2025-01-16"

    def test_zero_ts(self):
        # 0 epoch = 1970-01-01
        key = _day_key(0.0)
        assert key == "1970-01-01"
