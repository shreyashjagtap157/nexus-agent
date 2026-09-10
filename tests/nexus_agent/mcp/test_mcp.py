"""Tests for MCP and ACP modules."""

import pytest

from nexus_agent.mcp.acp_server import ACPServer, ACPResponse


class TestACPResponse:
    def test_response_creation(self):
        resp = ACPResponse(id=1, result={"status": "ok"})
        json_str = resp.to_json()
        assert '"id": 1' in json_str or '"id":1' in json_str

    def test_error_response(self):
        resp = ACPResponse(id=1, error={"code": -32600, "message": "Invalid"})
        json_str = resp.to_json()
        assert "error" in json_str

    def test_notification(self):
        resp = ACPResponse(id=None, result=None)
        json_str = resp.to_json()
        assert '"jsonrpc": "2.0"' in json_str or '"jsonrpc":"2.0"' in json_str


class TestACPProtocol:
    def test_jsonrpc_format(self):
        """Verify ACP follows JSON-RPC 2.0 format."""
        import json
        resp = ACPResponse(id=1, result={"content": "hello"})
        data = json.loads(resp.to_json())
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert "result" in data
