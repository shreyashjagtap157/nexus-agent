"""Tests for /cost and /usage slash commands on the CLI dispatcher."""

from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path

from nexus_agent.cli.renderer import TokenUsage
from nexus_agent.core.usage import UsageTracker


class FakeDispatcher:
    """Minimal stand-in for the dispatcher's state needed by /cost."""

    def __init__(self, tmpd: Path):
        self._tmpd = tmpd
        self.usage_tracker = UsageTracker(path=tmpd / "usage.json")
        self._tokens = TokenUsage()
        self._messages: list[str] = []
        self.r = self

    def _session_label(self) -> str:
        return "test-session"

    def system_message(self, msg: str) -> None:
        self._messages.append(msg)


def _bind_cost_handler(dispatcher):
    """Bind `_cmd_cost` to the FakeDispatcher (mirror of the real one)."""
    from nexus_agent.cli.command_dispatcher import CommandDispatcherMixin
    dispatcher._cmd_cost = CommandDispatcherMixin._cmd_cost.__get__(dispatcher)


class TestCostHandler(unittest.TestCase):
    def setUp(self):
        self.tmpd = Path("tmp") / f"cost_test_{uuid.uuid4().hex[:8]}"
        self.tmpd.mkdir(parents=True, exist_ok=True)
        self.d = FakeDispatcher(self.tmpd)
        _bind_cost_handler(self.d)

    def tearDown(self):
        shutil.rmtree(self.tmpd, ignore_errors=True)

    def test_no_args_shows_current_cost(self):
        self.d._tokens.total_input = 1000
        self.d._tokens.total_output = 500
        self.d._cmd_cost("")
        self.assertTrue(any("Current session: $" in m for m in self.d._messages))

    def test_no_tracker(self):
        d = FakeDispatcher(self.tmpd)
        d.usage_tracker = None
        _bind_cost_handler(d)
        d._cmd_cost("")
        self.assertTrue(any("no usage tracker" in m for m in d._messages))

    def test_help(self):
        self.d._cmd_cost("help")
        joined = "\n".join(self.d._messages)
        self.assertIn("/cost [today|week|all|session|model", joined)

    def test_today_empty(self):
        self.d._cmd_cost("today")
        joined = "\n".join(self.d._messages)
        self.assertIn("Total tokens:", joined)

    def test_today_with_data(self):
        self.d.usage_tracker.record(
            session_id="s1", provider="openai", model="gpt-4o",
            prompt_tokens=100, completion_tokens=50,
        )
        self.d._cmd_cost("today")
        joined = "\n".join(self.d._messages)
        self.assertIn("Current session:", joined)
        self.assertIn("openai/gpt-4o", joined)

    def test_week(self):
        self.d.usage_tracker.record(
            session_id="s1", provider="openai", model="gpt-4o",
            prompt_tokens=10, completion_tokens=5,
        )
        self.d._cmd_cost("week")
        self.assertTrue(any("openai/gpt-4o" in m for m in self.d._messages))

    def test_all(self):
        self.d.usage_tracker.record(
            session_id="s1", provider="openai", model="gpt-4o",
            prompt_tokens=10, completion_tokens=5,
        )
        self.d._cmd_cost("all")
        self.assertTrue(any("openai/gpt-4o" in m for m in self.d._messages))

    def test_session_breakdown(self):
        self.d.usage_tracker.record(
            session_id="s1", provider="openai", model="gpt-4o",
            prompt_tokens=10, completion_tokens=5,
        )
        self.d.usage_tracker.record(
            session_id="s2", provider="openai", model="gpt-4o",
            prompt_tokens=20, completion_tokens=10,
        )
        self.d._cmd_cost("session")
        joined = "\n".join(self.d._messages)
        self.assertIn("s1", joined)
        self.assertIn("s2", joined)

    def test_session_empty(self):
        self.d._cmd_cost("session")
        joined = "\n".join(self.d._messages)
        self.assertIn("No historical usage", joined)

    def test_model_breakdown(self):
        self.d.usage_tracker.record(
            session_id="s1", provider="openai", model="gpt-4o",
            prompt_tokens=10, completion_tokens=5,
        )
        self.d.usage_tracker.record(
            session_id="s1", provider="anthropic", model="claude-3-5-sonnet-latest",
            prompt_tokens=20, completion_tokens=10,
        )
        self.d._cmd_cost("model")
        joined = "\n".join(self.d._messages)
        self.assertIn("openai/gpt-4o", joined)
        self.assertIn("anthropic/claude-3-5-sonnet-latest", joined)

    def test_model_empty(self):
        self.d._cmd_cost("model")
        joined = "\n".join(self.d._messages)
        self.assertIn("No historical usage", joined)

    def test_days_invalid(self):
        self.d._cmd_cost("days=abc")
        self.assertTrue(any("Invalid days" in m for m in self.d._messages))

    def test_days_valid(self):
        self.d.usage_tracker.record(
            session_id="s1", provider="openai", model="gpt-4o",
            prompt_tokens=10, completion_tokens=5,
        )
        self.d._cmd_cost("days=1")
        joined = "\n".join(self.d._messages)
        self.assertIn("openai/gpt-4o", joined)

    def test_unknown_subcommand_falls_through(self):
        # An unknown subcommand should still print the current cost line
        self.d._cmd_cost("garbage")
        self.assertTrue(any("Cost: $" in m for m in self.d._messages))


class TestUsageHandler(unittest.TestCase):
    def setUp(self):
        self.tmpd = Path("tmp") / f"usage_test_{uuid.uuid4().hex[:8]}"
        self.tmpd.mkdir(parents=True, exist_ok=True)
        self.d = FakeDispatcher(self.tmpd)
        from nexus_agent.cli.command_dispatcher import CommandDispatcherMixin
        self.d._cmd_usage = CommandDispatcherMixin._cmd_usage.__get__(self.d)

    def tearDown(self):
        shutil.rmtree(self.tmpd, ignore_errors=True)

    def test_returns_useful_message(self):
        self.d._cmd_usage("")
        joined = "\n".join(self.d._messages)
        self.assertIn("/cost", joined)
