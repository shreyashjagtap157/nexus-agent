import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from nexus_agent.gui.server import app

client = TestClient(app)


def test_websocket_cswsh_protection():
    # Test malicious origin
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            "/api/ws/test-session-123",
            headers={"Origin": "http://attacker.com", "Host": "127.0.0.1:7860"},
        ) as ws:
            ws.send_json({"prompt": "hello", "mode": "auto"})
            ws.receive_json()
    assert exc.value.code == 1008

    # Test null origin
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            "/api/ws/test-session-123", headers={"Origin": "null", "Host": "127.0.0.1:7860"}
        ) as ws:
            ws.send_json({"prompt": "hello", "mode": "auto"})
            ws.receive_json()
    assert exc.value.code == 1008

    # Test missing origin (programmatic client)
    try:
        with client.websocket_connect(
            "/api/ws/test-session-123", headers={"Host": "127.0.0.1:7860"}
        ) as ws:
            pass
    except WebSocketDisconnect as e:
        # If it fails with 1008, the protection is blocking programmatic clients erroneously
        assert e.code != 1008
