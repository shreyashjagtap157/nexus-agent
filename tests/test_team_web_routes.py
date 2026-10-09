from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from nexus_agent.team.web_routes import _artifact_root, _require_local_client, register_team_routes


class State:
    def __init__(self, workspace: Path):
        self.workspace = str(workspace)

    def get(self, key, default=None):
        if key == "workspace":
            return self.workspace
        return default


def test_artifact_root_accepts_team_scoped_paths(tmp_path: Path):
    root = _artifact_root(State(tmp_path), "team-1")
    assert root == (tmp_path / ".nexus-agent" / "runtime" / "artifacts" / "team-1").resolve()


def test_artifact_root_rejects_path_traversal(tmp_path: Path):
    with pytest.raises(HTTPException) as exc:
        _artifact_root(State(tmp_path), "../../outside")
    assert exc.value.status_code == 400


def test_team_data_access_rejects_non_local_clients():
    request = type("Request", (), {"client": type("Client", (), {"host": "203.0.113.10"})()})()
    with pytest.raises(HTTPException) as exc:
        _require_local_client(request)
    assert exc.value.status_code == 403


def test_team_data_access_accepts_loopback_clients():
    request = type("Request", (), {"client": type("Client", (), {"host": "127.0.0.1"})()})()
    _require_local_client(request)


class RouteState:
    def __init__(self, workspace: Path):
        self.workspace = str(workspace)

    def get(self, key, default=None):
        if key == "workspace":
            return self.workspace
        return default


@pytest.mark.parametrize(
    "path",
    [
        "/api/workflows",
        "/api/research-depths",
        "/api/research-sources",
        "/api/teams/team-1/artifacts",
        "/api/teams/team-1/artifacts/example.txt",
    ],
)
def test_sensitive_team_read_routes_reject_remote_clients(tmp_path: Path, path: str):
    app = FastAPI()
    register_team_routes(app, RouteState(tmp_path))
    response = TestClient(app).get(path)
    assert response.status_code == 403

def test_team_report_rejects_symlinked_result_artifact(tmp_path: Path):
    root = _artifact_root(State(tmp_path), "team-1")
    root.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    link = root / "result.md"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Symlinks are not available on this platform")

    app = FastAPI()
    register_team_routes(app, State(tmp_path))
    response = TestClient(app).get("/api/teams/team-1/report")
    assert response.status_code == 400
