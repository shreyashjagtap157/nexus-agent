from pathlib import Path

from nexus_agent.auth import AuthStore


def test_auth_store_masks_and_round_trips_credentials(tmp_path: Path):
    store = AuthStore(tmp_path / "auth.json")
    store.set("example", "super-secret-token", metadata={"kind": "api"})
    assert store.get("example") == "super-secret-token"
    listed = store.list()
    assert listed[0]["provider"] == "example"
    assert "super-secret-token" not in listed[0]["key"]
    assert store.remove("example") is True
    assert store.get("example") is None
