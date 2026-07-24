import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from nexus_agent.gui.server import app


def test_websocket_cswsh_protection():
    client = TestClient(app)

    # Missing Origin (should be allowed, normal client)
    with client.websocket_connect("/api/ws/test-session") as ws:
        pass

    # Valid Origin (matching Host)
    with client.websocket_connect(
        "/api/ws/test-session", headers={"Origin": "http://testserver", "Host": "testserver"}
    ) as ws:
        pass

    # Valid Origin (with port)
    with client.websocket_connect(
        "/api/ws/test-session",
        headers={"Origin": "http://testserver:8000", "Host": "testserver:8000"},
    ) as ws:
        pass

    # Invalid Origin (CSWSH attempt)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/api/ws/test-session", headers={"Origin": "http://evil.com", "Host": "testserver"}
        ) as ws:
            ws.receive_text()
