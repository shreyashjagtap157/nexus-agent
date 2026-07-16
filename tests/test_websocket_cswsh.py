import pytest
from fastapi.testclient import TestClient
from nexus_agent.gui.server import app
from starlette.websockets import WebSocketDisconnect

def test_websocket_cswsh_protection():
    client = TestClient(app)

    # Valid origin (matches host)
    with client.websocket_connect("/api/ws/test1", headers={"Origin": "http://testserver", "Host": "testserver"}) as ws:
        pass

    # Valid - missing origin
    with client.websocket_connect("/api/ws/test2", headers={"Host": "testserver"}) as ws:
        pass

    # Invalid - Origin mismatch
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/ws/test3", headers={"Origin": "http://evil.com", "Host": "testserver"}) as ws:
            ws.receive_json()
    assert exc_info.value.code == 1008

    # Invalid - null Origin
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/ws/test4", headers={"Origin": "null", "Host": "testserver"}) as ws:
            ws.receive_json()
    assert exc_info.value.code == 1008
