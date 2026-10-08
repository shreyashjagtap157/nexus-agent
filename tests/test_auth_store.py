from pathlib import Path

from nexus_agent.auth import AuthStore


def test_auth_store_masks_and_round_trips_credentials(tmp_path: Path):
    path = tmp_path / "auth.json"
    store = AuthStore(path)
    store.set("nvidia_nim", "secret-token-value")
    assert store.get("nvidia_nim") == "secret-token-value"
    rows = store.list()
    assert rows[0]["provider"] == "nvidia_nim"
    assert "secret-token-value" not in str(rows)
    assert store.remove("nvidia_nim") is True
    assert store.get("nvidia_nim") is None
