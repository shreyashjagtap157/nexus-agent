from pathlib import Path

import pytest

from fastapi import HTTPException

from nexus_agent.team.web_routes import _artifact_root


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
