import sys
from unittest.mock import MagicMock

# Mock blessed globally to prevent ImportError on systems without it
sys.modules['blessed'] = MagicMock()

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from nexus_agent.gui.server import app

client = TestClient(app)

def test_websocket_cswsh_protection_valid_origin():
    # Provide matching Origin and Host
    headers = {
        "Origin": "http://127.0.0.1:7860",
        "Host": "127.0.0.1:7860"
    }
    # It should connect successfully (will eventually timeout waiting for json, which is fine, or we can send empty)
    with client.websocket_connect("/api/ws/test_session", headers=headers) as websocket:
        websocket.send_text('{"prompt": "hello", "mode": "auto"}')
        # Expecting an error about no model loaded, but the connection was successful
        data = websocket.receive_json()
        assert data["type"] == "error"
        assert "No model loaded" in data["content"]

def test_websocket_cswsh_protection_invalid_origin():
    # Provide mismatching Origin and Host
    headers = {
        "Origin": "http://evil.com",
        "Host": "127.0.0.1:7860"
    }
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/ws/test_session", headers=headers) as websocket:
            websocket.receive_text()

    assert exc_info.value.code == 1008

def test_websocket_cswsh_protection_ipv6():
    headers = {
        "Origin": "http://[::1]:7860",
        "Host": "[::1]:7860"
    }
    with client.websocket_connect("/api/ws/test_session", headers=headers) as websocket:
        websocket.send_text('{"prompt": "hello", "mode": "auto"}')
        data = websocket.receive_json()
        assert data["type"] == "error"
