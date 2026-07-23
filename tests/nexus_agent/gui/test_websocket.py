import pytest
from fastapi import status
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from nexus_agent.gui.server import app

client = TestClient(app)


def test_websocket_cswsh_protection_rejects_mismatched_origin():
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            "/api/ws/12345", headers={"origin": "http://evil.com", "host": "localhost:8000"}
        ) as websocket:
            websocket.send_text('{"prompt": "hello", "mode": "auto"}')
            websocket.receive_text()
    assert exc.value.code == status.WS_1008_POLICY_VIOLATION


def test_websocket_cswsh_protection_allows_matched_origin():
    try:
        with client.websocket_connect(
            "/api/ws/12345", headers={"origin": "http://localhost", "host": "localhost:8000"}
        ) as websocket:
            websocket.send_text('{"prompt": "hello", "mode": "auto"}')
    except WebSocketDisconnect:
        pass
    except Exception as e:
        pytest.fail(f"WebSocket connection failed with {type(e)}")
