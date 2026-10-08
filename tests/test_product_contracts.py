from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def test_team_console_references_existing_controls():
    html = (ROOT / "src/nexus_agent/gui/frontend/team.html").read_text(encoding="utf-8")
    ids = set(re.findall(r'id=["\']([^"\']+)["\']', html))
    referenced = set(re.findall(r'\$\(["\']([A-Za-z0-9_-]+)["\']\)', html))
    missing = sorted(name for name in referenced if name not in ids and name not in {"start", "pause", "resume", "stop", "refresh"})
    assert not missing, f"team.html references missing DOM ids: {missing}"


def test_workflow_console_contains_research_and_output_controls():
    html = (ROOT / "src/nexus_agent/gui/frontend/workflows.html").read_text(encoding="utf-8")
    required_ids = {
        "workflow", "mode", "agents", "parallelism", "iterations",
        "output", "format", "depth", "collection", "source_strategy",
        "research_max_minutes", "research_idle_rounds", "agent_ids", "sources",
    }
    missing = [item for item in required_ids if f'id="{item}"' not in html]
    assert not missing, f"workflow UI missing controls: {missing}"


def test_provider_vault_has_inference_test_and_no_raw_secret_rendering():
    html = (ROOT / "src/nexus_agent/gui/frontend/providers.html").read_text(encoding="utf-8")
    assert 'id="test"' in html
    assert "/api/providers/" in html
    assert "/test" in html
    assert "type=\"password\"" in html


def test_native_ci_covers_both_rust_clients():
    workflow = (ROOT / ".github/workflows/native-desktop.yml").read_text(encoding="utf-8")
    assert 'nexus-desktop/**' in workflow
    assert 'nexus-rs/**' in workflow
    assert 'cargo check --manifest-path nexus-rs/Cargo.toml' in workflow
    assert 'cargo test --manifest-path nexus-rs/Cargo.toml' in workflow


def test_canonical_team_artifact_path_is_consistent():
    runtime = (ROOT / "src/nexus_agent/team/runtime.py").read_text(encoding="utf-8")
    routes = (ROOT / "src/nexus_agent/team/web_routes.py").read_text(encoding="utf-8")
    assert 'self.data_dir / "artifacts" / team_id' in runtime
    assert 'StorageLayout(_workspace(state_manager)).artifacts / team_id' in routes
