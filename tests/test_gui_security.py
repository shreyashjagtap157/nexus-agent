import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from nexus_agent.agents.web_routes import _require_local as require_agent_local
from nexus_agent.auth.web_routes import _local_only as require_auth_local
from nexus_agent.gui.server import _require_local_client, app
from nexus_agent.mcp.web_routes import _require_local as require_mcp_local
from nexus_agent.memory.web_routes import _require_local as require_memory_local
from nexus_agent.research.web_routes import _require_local as require_research_local


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
        "/api/status",
        "/api/config/full",
        "/api/models",
        "/api/activity/files",
        "/api/sessions",
        "/api/tasks",
        "/api/nla/test-session",
        "/api/memory/scoped/stats",
        "/api/mcp",
        "/api/skills",
        "/api/auth",
        "/api/audit/verify",
        "/api/audit/records",
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

@pytest.mark.parametrize(
    "guard",
    [
        require_agent_local,
        require_auth_local,
        require_memory_local,
        require_mcp_local,
        require_research_local,
        _require_local_client,
    ],
)
def test_sensitive_guards_fail_closed_when_client_address_is_missing(guard):
    request = type("Request", (), {"client": None})()
    with pytest.raises(HTTPException) as exc:
        guard(request)
    assert exc.value.status_code == 403
