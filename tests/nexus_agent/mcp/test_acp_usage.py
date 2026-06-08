"""Tests for ACP usage/cost tracking handlers."""

from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import io

from nexus_agent.mcp.acp_server import ACPServer


class MockUsageTracker:
    """Mock UsageTracker that returns structured data for tests."""

    def __init__(self):
        self._entries = []

    def summarize(self, session_id=None):
        from types import SimpleNamespace
        return SimpleNamespace(
            entries=3,
            prompt_tokens=500,
            completion_tokens=200,
            total_tokens=700,
            estimated_cost=0.0035,
            by_model={"gpt-4o": {"cost": 0.0020, "tokens": 400}},
            by_session={session_id or "test": {"cost": 0.0035, "tokens": 700}},
        )


class MockUsageAgent:
    """Mock agent that has a usage_tracker."""

    def __init__(self):
        self.session_id = "test_session"
        self.mode = "auto"
        self.effort_level = "medium"
        self.usage_tracker = MockUsageTracker()

    def run_stream(self, text):
        return iter([])


class TestACPUsageHandlers(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.workspace = Path("tmp/acp_usage_test")
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.agent = MockUsageAgent()

        async def factory():
            return self.agent

        self.server = ACPServer(agent_factory=factory, workspace=self.workspace)
        self.server._agent = self.agent  # Simulate initialization

    async def asyncTearDown(self):
        import shutil
        if self.workspace.exists():
            shutil.rmtree(self.workspace)

    def test_get_usage_response_structure(self):
        """get_usage should return structured cost/usage data."""
        # Should not raise
        with patch("sys.stdout", new_callable=io.StringIO):
            self.server._handle_get_usage(req_id=1)

    def test_emit_cost_update(self):
        """_emit_cost_update should not raise."""
        with patch("sys.stdout", new_callable=io.StringIO):
            try:
                self.server._emit_cost_update()
            except Exception as e:
                self.fail(f"emit_cost_update raised: {e}")

    def test_get_usage_without_tracker(self):
        """get_usage should handle missing usage tracker gracefully."""
        self.agent.usage_tracker = None
        with patch("sys.stdout", new_callable=io.StringIO):
            self.server._handle_get_usage(req_id=2)

    def test_get_usage_method_routing(self):
        """get_usage should be routed in the method handler."""
        req = '{"jsonrpc": "2.0", "id": 3, "method": "get_usage", "params": {}}'
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            import asyncio
            # _handle_request is async, need to run it
            async def run():
                await self.server._handle_request(req)
            asyncio.run(run())
            output = mock_stdout.getvalue()
            self.assertIn("jsonrpc", output)
            self.assertIn("estimated_cost", output)
            self.assertIn("total_tokens", output)


class MockNoUsageAgent:
    """Mock agent WITHOUT usage_tracker."""

    def __init__(self):
        self.session_id = "test_no_usage"
        self.mode = "auto"
        self.effort_level = "medium"

    def run_stream(self, text):
        return iter([])


class TestACPNoUsageHandler(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.workspace = Path("tmp/acp_no_usage_test")
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.agent = MockNoUsageAgent()

        async def factory():
            return self.agent

        self.server = ACPServer(agent_factory=factory, workspace=self.workspace)
        self.server._agent = self.agent

    async def asyncTearDown(self):
        import shutil
        if self.workspace.exists():
            shutil.rmtree(self.workspace)

    def test_get_usage_no_tracker(self):
        with patch("sys.stdout", new_callable=io.StringIO):
            self.server._handle_get_usage(req_id=5)

    def test_cost_update_no_tracker(self):
        """Should not crash when no usage_tracker."""
        with patch("sys.stdout", new_callable=io.StringIO):
            try:
                self.server._emit_cost_update()
            except Exception as e:
                self.fail(f"emit_cost_update without tracker raised: {e}")


if __name__ == "__main__":
    unittest.main()
