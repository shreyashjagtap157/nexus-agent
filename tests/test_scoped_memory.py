from pathlib import Path

from nexus_agent.memory.scoped import MemoryScope, ScopedMemory
from nexus_agent.storage.layout import StorageLayout


def test_scoped_memory_keeps_project_and_user_separate(tmp_path: Path):
    layout = StorageLayout(tmp_path, project_root=tmp_path)
    memory = ScopedMemory(layout)
    user_id = memory.store("User preference", scope=MemoryScope.USER, category="preference")
    project_id = memory.store("Project architecture", scope=MemoryScope.PROJECT, category="architecture")
    assert user_id != project_id

    project_results = memory.search("architecture", scopes=[MemoryScope.PROJECT], limit=5)
    assert any(row["id"] == project_id and row["scope"] == "project" for row in project_results)
    user_results = memory.search("preference", scopes=[MemoryScope.USER], limit=5)
    assert any(row["id"] == user_id and row["scope"] == "user" for row in user_results)


def test_scoped_memory_supports_team_and_agent_scopes(tmp_path: Path):
    layout = StorageLayout(tmp_path)
    memory = ScopedMemory(layout, agent_id="reviewer", team_id="team-1")
    agent_id = memory.store("reviewer note", scope=MemoryScope.AGENT)
    team_id = memory.store("team decision", scope=MemoryScope.TEAM)
    assert agent_id != team_id
    assert memory.search("decision", scopes=[MemoryScope.TEAM])[0]["id"] == team_id
    memory.close()
