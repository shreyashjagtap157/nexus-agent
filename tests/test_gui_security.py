from fastapi import HTTPException
from fastapi.testclient import TestClient

import pytest
from starlette.websockets import WebSocketDisconnect

from nexus_agent.gui.server import _require_local_client, app


def test_gui_mutation_access_rejects_remote_clients():
    request = type("Request", (), {"client": type("Client", (), {"host": "203.0.113.10"})()})()
    try:
        _require_local_client(request)
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("Remote GUI mutation request was accepted")


def test_gui_mutation_access_accepts_loopback_clients():
    for host in ("127.0.0.1", "::1", "localhost"):
        request = type("Request", (), {"client": type("Client", (), {"host": host})()})()
        _require_local_client(request)

@pytest.mark.parametrize(
    "path",
    [
        "/api/agents",
        "/api/memory/scoped/stats",
        "/api/mcp",
        "/api/skills",
        "/api/auth",
        "/api/research/sources",
        "/api/workflows",
        "/api/provider-config",
        "/api/providers/models?provider=openai",
        "/api/teams/team-1/artifacts",
    ],
)
def test_workspace_sensitive_gui_routes_reject_remote_clients(path):
    response = TestClient(app).get(path)
    assert response.status_code == 403


def test_gui_agent_websocket_rejects_remote_clients():
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/ws/test-session"):
            pass
    assert exc.value.code == 1008
