from pathlib import Path

from nexus_agent.auth import AuthStore
from nexus_agent.agents import AgentRegistry, AgentScope, AgentSpec
from nexus_agent.storage.layout import StorageLayout


def test_version_contract_script_is_valid():
    root = Path(__file__).resolve().parents[1]
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    assert version == "0.3.0-alpha.1"
    result = __import__("subprocess").run(
        ["python", str(root / "scripts" / "check_version.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_agent_registry_persists_workspace_profile(tmp_path: Path):
    registry = AgentRegistry(tmp_path)
    spec = AgentSpec(
        id="security-reviewer",
        name="Security Reviewer",
        profession="Application Security Engineer",
        description="Reviews security boundaries.",
        mission="Find exploitable defects and insecure assumptions.",
        instructions="Inspect dependencies, inputs, permissions and dangerous tool use.",
        scope=AgentScope.WORKSPACE,
        tool_categories=["read", "search", "code_intel"],
        reviewer=True,
    )
    path = registry.save(spec, AgentScope.WORKSPACE)
    assert path.exists()
    loaded = registry.get("security-reviewer")
    assert loaded is not None
    assert loaded.to_team_profile().reviewer is True
    assert loaded.to_team_profile().profession == "Application Security Engineer"


def test_auth_store_masks_and_separates_provider_credentials(tmp_path: Path):
    store = AuthStore(tmp_path / "auth.json")
    store.set("nvidia_nim", "nvapi-secret-value")
    assert store.get("nvidia_nim") == "nvapi-secret-value"
    listed = store.list()
    assert listed[0]["provider"] == "nvidia_nim"
    assert "nvapi-secret-value" not in str(listed[0])
    assert store.remove("nvidia_nim") is True
    assert store.get("nvidia_nim") is None


def test_storage_layout_separates_user_and_workspace_state(tmp_path: Path):
    layout = StorageLayout(tmp_path, project_root=tmp_path)
    assert layout.user_root != layout.workspace_root
    assert layout.user_agents != layout.workspace_agents
    assert layout.team_db.parent == layout.workspace_runtime
