import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from nexus_agent.gui.server import app


def test_websocket_cswsh_protection():
    client = TestClient(app)

    # Should fail with mismatched origin
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/api/ws/123", headers={"Origin": "http://malicious.com", "Host": "localhost:8000"}
        ):
            pass
    assert exc_info.value.code == 1008

    # Should fail with null origin
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/api/ws/123", headers={"Origin": "null", "Host": "localhost:8000"}
        ):
            pass
    assert exc_info.value.code == 1008

    # Should pass with missing origin
    with client.websocket_connect("/api/ws/123", headers={"Host": "localhost:8000"}) as ws:
        assert ws is not None

    # Should pass with matching origin
    with client.websocket_connect(
        "/api/ws/123", headers={"Origin": "http://localhost", "Host": "localhost:8000"}
    ) as ws:
        assert ws is not None
