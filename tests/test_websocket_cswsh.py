import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from nexus_agent.gui.server import app


def test_websocket_cswsh():
    client = TestClient(app)

    # Test 1: No Origin header (allowed)
    with client.websocket_connect("/api/ws/test1") as websocket:
        assert websocket is not None

    # Test 2: Matching Origin header (allowed)
    with client.websocket_connect(
        "/api/ws/test2", headers={"Origin": "http://testserver", "Host": "testserver"}
    ) as websocket:
        assert websocket is not None

    # Test 3: Mismatched Origin header (rejected)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/api/ws/test3", headers={"Origin": "http://malicious.com", "Host": "testserver"}
        ) as websocket:
            websocket.receive_json()
    assert exc_info.value.code == 1008

    # Test 4: null Origin header (rejected)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/api/ws/test4", headers={"Origin": "null", "Host": "testserver"}
        ) as websocket:
            websocket.receive_json()
    assert exc_info.value.code == 1008
