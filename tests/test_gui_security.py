from typing import Any, cast

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import nexus_agent.gui.server as gui_server
from nexus_agent.agents.web_routes import _require_local as require_agent_local
from nexus_agent.auth.web_routes import _local_only as require_auth_local
from nexus_agent.gui.server import (
    _allowed_local_http_origin,
    _allowed_websocket_origin,
    _format_gui_url,
    _require_local_client,
    _require_loopback_bind_host,
    app,
)
from nexus_agent.mcp.web_routes import (
    _require_local as require_mcp_local,
    register_mcp_routes,
)
from nexus_agent.team.web_routes import _require_local_client as require_team_local
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
    response = TestClient(app, client=("203.0.113.10", 12345)).get(path)
    assert response.status_code == 403


def test_gui_agent_websocket_rejects_remote_clients():
    client = TestClient(app, client=("203.0.113.10", 12345))
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/ws/test-session"):
            pass
    assert exc.value.code == 1008


@pytest.mark.parametrize(
    "headers",
    [
        {"origin": "https://attacker.example", "host": "127.0.0.1:8765"},
        {"origin": "http://attacker.example", "host": "127.0.0.1:8765"},
        {"origin": "http://localhost:8080", "host": "localhost:8765"},
        {"origin": "null", "host": "localhost:8765"},
        {"origin": "http://localhost:8765/path", "host": "localhost:8765"},
    ],
)
def test_websocket_origin_guard_rejects_untrusted_origins(headers):
    assert _allowed_websocket_origin(headers) is False


@pytest.mark.parametrize(
    "headers",
    [
        {"origin": "http://localhost:8765", "host": "localhost:8765"},
        {"origin": "http://127.0.0.1:8765", "host": "127.0.0.1:8765"},
        {"origin": "http://127.0.0.2:8765", "host": "127.0.0.2:8765"},
        {"origin": "http://[::1]:8765", "host": "[::1]:8765"},
        {},
    ],
)
def test_websocket_origin_guard_allows_same_origin_and_nonbrowser_clients(headers):
    assert _allowed_websocket_origin(headers) is True


@pytest.mark.parametrize(
    "guard",
    [
        require_agent_local,
        require_auth_local,
        require_memory_local,
        require_mcp_local,
        require_research_local,
        require_team_local,
        _require_local_client,
    ],
)
def test_sensitive_guards_fail_closed_when_client_address_is_missing(guard):
    request = type("Request", (), {"client": None})()
    with pytest.raises(HTTPException) as exc:
        guard(request)
    assert exc.value.status_code == 403


@pytest.mark.parametrize(
    "host",
    (
        "127.0.0.1",
        "::1",
        "localhost",
    ),
)
def test_gui_bind_policy_accepts_only_loopback_targets(host):
    _require_loopback_bind_host(host)


@pytest.mark.parametrize(
    "host",
    (
        "0.0.0.0",
        "127.0.0.2",
        "192.168.1.20",
        "10.0.0.4",
        "::",
        "2001:db8::1",
        "attacker.example",
        "",
    ),
)
def test_gui_bind_policy_rejects_network_accessible_targets(host):
    with pytest.raises(ValueError, match="loopback"):
        _require_loopback_bind_host(host)


def test_gui_startup_rejects_configured_remote_bind_before_initializing_runtime(monkeypatch):
    monkeypatch.setattr(
        gui_server, "load_config", lambda **_: {"gui": {"host": "0.0.0.0"}}
    )

    with pytest.raises(ValueError, match="loopback"):
        gui_server.start_gui_server(open_browser=False)

@pytest.mark.parametrize(
    ("method", "path", "payload"),
    (
        ("post", "/api/mcp/validate", None),
        ("put", "/api/mcp", []),
    ),
)
def test_mcp_mutation_routes_reject_missing_client_address(
    method, path, payload, tmp_path, monkeypatch
):
    isolated_app = FastAPI()
    register_mcp_routes(isolated_app, {"workspace": str(tmp_path)})
    monkeypatch.setattr(
        "nexus_agent.mcp.web_routes.load_config",
        lambda **_: {"mcp": {"servers": []}},
    )
    monkeypatch.setattr("nexus_agent.mcp.web_routes.save_user_config", lambda *_: None)

    client = TestClient(isolated_app, client=cast(Any, None))
    if method == "post":
        response = client.post(path)
    else:
        response = client.put(path, json=payload)

    assert response.status_code == 403

@pytest.mark.parametrize(
    ("host", "expected"),
    (
        ("127.0.0.1", "http://127.0.0.1:7860"),
        ("localhost", "http://localhost:7860"),
        ("::1", "http://[::1]:7860"),
    ),
)
def test_gui_url_formats_loopback_addresses(host, expected):
    assert _format_gui_url(host, 7860) == expected

@pytest.mark.parametrize(
    ("headers", "scheme", "allowed"),
    (
        ({"host": "127.0.0.1:7860", "origin": "http://127.0.0.1:7860"}, "http", True),
        ({"host": "[::1]:7860", "origin": "http://[::1]:7860"}, "http", True),
        ({"host": "localhost:7860", "origin": "http://localhost:7860"}, "http", True),
        ({"host": "127.0.0.1:7860"}, "http", True),
        ({"host": "127.0.0.1:7860", "origin": "https://127.0.0.1:7860"}, "http", False),
        ({"host": "127.0.0.1:7860", "origin": "http://127.0.0.2:7860"}, "http", False),
        ({"host": "127.0.0.1:7860", "origin": "http://evil.example:7860"}, "http", False),
        ({"host": "127.0.0.1:7860", "origin": "http://127.0.0.1:3000"}, "http", False),
        ({"host": "127.0.0.1:7860", "origin": "http://127.0.0.1:7860/path"}, "http", False),
    ),
)
def test_http_origin_policy(headers, scheme, allowed):
    assert _allowed_local_http_origin(headers, scheme) is allowed


def test_api_middleware_blocks_cross_origin_mutation_before_handler():
    client = TestClient(app, client=("127.0.0.1", 12345))
    response = client.post(
        "/api/commit",
        headers={"Origin": "https://attacker.example"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Cross-origin GUI/API requests are blocked."

@pytest.mark.parametrize("path", ("/api/skills", "/api/audit/verify"))
def test_sensitive_routes_reject_missing_client_address(path):
    client = TestClient(app, client=cast(Any, None))
    response = client.get(path)
    assert response.status_code == 403

