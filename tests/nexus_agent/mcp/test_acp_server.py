"""Tests for the ACPServer JSON-RPC interface."""

from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
import io

from nexus_agent.mcp.acp_server import ACPServer

class MockAgent:
    def __init__(self):
        self.session_id = "test-session"
        self.mode = "auto"
        self.effort_level = "medium"

    def run_stream(self, text):
        # Yield a few events then finish
        class Event:
            def __init__(self, type, content=None, status=None):
                self.type = type
                self.content = content
                self.status = status
        
        yield Event("thinking", "Thinking about it...")
        yield Event("content_chunk", "Hello ")
        yield Event("content_chunk", "World!")
        yield Event("done", status="completed")

class TestACPServer(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.workspace = Path("tmp/acp_test")
        self.workspace.mkdir(parents=True, exist_ok=True)
        
        # Agent factory that returns our MockAgent
        async def factory():
            return MockAgent()
        
        self.server = ACPServer(agent_factory=factory, workspace=self.workspace)

    async def test_get_status(self):
        # Mock stdin/stdout
        input_data = '{"jsonrpc": "2.0", "id": 1, "method": "get_status", "params": {}}\n'
        output = io.StringIO()
        
        with patch("sys.stdin", io.StringIO(input_data)), \
             patch("sys.stdout", output):
            
            # We only want to process one request and then stop
            # To avoid the infinite while loop, we can patch sys.stdin.readline to return empty string after first call
            with patch("sys.stdin.readline", side_effect=[input_data, ""]):
                await self.server.run()
        
        res = json.loads(output.getvalue().strip())
        self.assertEqual(res["id"], 1)
        self.assertEqual(res["result"]["session_id"], "test-session")
        self.assertEqual(res["result"]["mode"], "auto")

    async def test_prompt_events(self):
        input_data = '{"jsonrpc": "2.0", "id": 42, "method": "prompt", "params": {"text": "Hello!"}}\n'
        output = io.StringIO()
        
        with patch("sys.stdin", io.StringIO(input_data)), \
             patch("sys.stdout", output):
            with patch("sys.stdin.readline", side_effect=[input_data, ""]):
                await self.server.run()
        
        lines = output.getvalue().strip().split("\n")
        # Expect: 1 thinking event, 2 content chunks, 1 done event, 1 final response
        self.assertEqual(len(lines), 5)
        
        # Check the first event
        first_event = json.loads(lines[0])
        self.assertEqual(first_event["method"], "event")
        self.assertEqual(first_event["params"]["type"], "thinking")
        
        # Check final response
        final_resp = json.loads(lines[-1])
        self.assertEqual(final_resp["id"], 42)
        self.assertEqual(final_resp["result"]["status"], "completed")

    async def test_invalid_json(self):
        input_data = 'not json\n'
        output = io.StringIO()
        
        with patch("sys.stdin", io.StringIO(input_data)), \
             patch("sys.stdout", output):
            with patch("sys.stdin.readline", side_effect=[input_data, ""]):
                await self.server.run()
        
        res = json.loads(output.getvalue().strip())
        self.assertEqual(res["error"]["code"], -32700)

    async def test_unknown_method(self):
        input_data = '{"jsonrpc": "2.0", "id": 1, "method": "foo", "params": {}}\n'
        output = io.StringIO()
        
        with patch("sys.stdin", io.StringIO(input_data)), \
             patch("sys.stdout", output):
            with patch("sys.stdin.readline", side_effect=[input_data, ""]):
                await self.server.run()
        
        res = json.loads(output.getvalue().strip())
        self.assertEqual(res["error"]["code"], -32601)

    async def test_stop_method(self):
        input_data = '{"jsonrpc": "2.0", "id": 1, "method": "stop", "params": {}}\n'
        output = io.StringIO()
        
        with patch("sys.stdin", io.StringIO(input_data)), \
             patch("sys.stdout", output):
            with patch("sys.stdin.readline", side_effect=[input_data, ""]):
                await self.server.run()
        
        res = json.loads(output.getvalue().strip())
        self.assertEqual(res["result"]["status"], "stopping")
        self.assertFalse(self.server._running)
