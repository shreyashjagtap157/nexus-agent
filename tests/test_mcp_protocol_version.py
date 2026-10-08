import pytest

from nexus_agent.mcp.server import MCPServer


def test_mcp_server_defaults_to_current_legacy_revision():
    server = MCPServer([])
    assert server.protocol_version == "2025-11-25"


def test_mcp_server_rejects_modern_era_until_explicitly_supported():
    with pytest.raises(ValueError):
        MCPServer([], protocol_version="2026-07-28")


def test_mcp_server_accepts_previous_legacy_revision():
    server = MCPServer([], protocol_version="2024-11-05")
    assert server.protocol_version == "2024-11-05"
