"""Tests for the MCP module — MCPClient, StdioTransport, MCPServer."""

import json
import tempfile
import threading
import time
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from nexus_agent.mcp.transport import StdioTransport


class TestStdioTransport(unittest.TestCase):
    def setUp(self):
        self.reader = StringIO()
        self.writer = StringIO()
        self.transport = StdioTransport(reader=self.reader, writer=self.writer)

    def test_send_message(self):
        msg = {"jsonrpc": "2.0", "method": "ping"}
        self.transport.send_message(msg)
        output = self.writer.getvalue()
        self.assertIn("ping", output)

    def test_start_and_close(self):
        self.transport.start()
        self.assertTrue(self.transport._running)
        self.transport.close()
        self.assertFalse(self.transport._running)

    def test_register_handler(self):
        handler = MagicMock()
        self.transport.register_handler(handler)
        self.assertEqual(self.transport._handler, handler)


class TestMCPClient(unittest.TestCase):
    @patch("subprocess.Popen")
    def test_client_start_fails_no_command(self, mock_popen):
        from nexus_agent.mcp.client import MCPClient
        client = MCPClient(command="", env={})
        self.assertFalse(client.start(startup_timeout=1))
        client.close()

    @patch("subprocess.Popen")
    def test_client_close_cleanup(self, mock_popen):
        from nexus_agent.mcp.client import MCPClient
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stdout = None
        mock_proc.stderr = None
        mock_popen.return_value = mock_proc
        client = MCPClient(command=["node", "test_server.js"], env={})
        client._process = mock_proc
        client._running = True
        client.close()
        mock_proc.terminate.assert_called_once()


class TestMCPServer(unittest.TestCase):
    def test_server_initialization(self):
        from nexus_agent.mcp.server import MCPServer
        server = MCPServer(tools=[])
        self.assertIsNotNone(server)

    def test_server_handle_initialize(self):
        from nexus_agent.mcp.server import MCPServer
        mock_transport = MagicMock()
        server = MCPServer(tools=[])
        server._transport = mock_transport
        request = {
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "0.1.0"},
        }
        server._handle_request(request)
        mock_transport.send_message.assert_called_once()

    def test_server_handle_tools_list(self):
        from nexus_agent.mcp.server import MCPServer
        mock_transport = MagicMock()
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.description = "A test tool"
        mock_tool.parameters = {"param1": {"type": "string"}}
        server = MCPServer(tools=[mock_tool])
        server._transport = mock_transport
        request = {"id": 2, "method": "tools/list"}
        server._handle_request(request)
        mock_transport.send_message.assert_called_once()
        call_args = mock_transport.send_message.call_args[0][0]
        self.assertIn("result", call_args)
        self.assertIn("tools", call_args["result"])
