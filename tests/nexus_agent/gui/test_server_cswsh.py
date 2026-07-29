import pytest
from fastapi.testclient import TestClient
from nexus_agent.gui.server import app
from starlette.websockets import WebSocketDisconnect

client = TestClient(app)

def test_cswsh_protection():
    # Valid origin matching host
    with client.websocket_connect("/api/ws/test_session", headers={"Origin": "http://127.0.0.1:8000", "Host": "127.0.0.1:8000"}) as ws:
        pass # Connection should succeed

    # Valid origin matching host (IPv6)
    with client.websocket_connect("/api/ws/test_session", headers={"Origin": "http://[::1]:8000", "Host": "[::1]:8000"}) as ws:
        pass # Connection should succeed

    # Invalid origin
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/ws/test_session", headers={"Origin": "http://evil.com", "Host": "127.0.0.1:8000"}) as ws:
            ws.receive_text()

    assert exc_info.value.code == 1008
