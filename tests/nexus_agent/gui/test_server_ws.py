from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from nexus_agent.gui.server import app

client = TestClient(app)

@patch("nexus_agent.gui.server.state_manager.get")
def test_websocket_cswsh_protection(mock_state_manager_get):
    # Setup mocks
    mock_engine = MagicMock()
    mock_engine.is_loaded = True
    mock_engine.model_name = "test-model"

    mock_session_manager = MagicMock()

    def mock_get(key, default=None):
        if key == "engine":
            return mock_engine
        if key == "session_manager":
            return mock_session_manager
        if key == "active_session_id":
            return "test-session"
        if key == "config":
            return {}
        if key == "workspace":
            return MagicMock()
        return default

    mock_state_manager_get.side_effect = mock_get

    # Same origin
    with client.websocket_connect(
        "/api/ws/test", headers={"Origin": "http://testserver"}
    ) as websocket:
        websocket.send_json({"prompt": "hello", "mode": "auto"})

    # No origin
    with client.websocket_connect("/api/ws/test") as websocket:
        websocket.send_json({"prompt": "hello", "mode": "auto"})

    # Origin mismatch
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/api/ws/test", headers={"Origin": "http://attacker.com"}
        ) as ws:
            ws.receive_json()
    assert exc_info.value.code == 1008

    # "null" origin
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/ws/test", headers={"Origin": "null"}) as ws:
            ws.receive_json()
    assert exc_info.value.code == 1008
