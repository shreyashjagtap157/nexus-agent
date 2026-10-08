from pathlib import Path

from nexus_agent.storage import StorageLayout


def test_storage_layout_keeps_credentials_outside_project_runtime(tmp_path: Path):
    layout = StorageLayout(tmp_path, project_root=tmp_path)
    layout.ensure()
    assert layout.auth_file.parent != layout.workspace_runtime
    assert layout.workspace_agents.is_relative_to(tmp_path)
    assert layout.trash.is_relative_to(layout.workspace_runtime)
    assert layout.artifacts.is_relative_to(layout.workspace_runtime)
    assert not layout.auth_file.is_relative_to(layout.workspace_runtime)
