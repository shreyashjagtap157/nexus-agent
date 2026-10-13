from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nexus_agent.auth import AuthStore
from nexus_agent.auth.web_routes import register_auth_routes


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


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("post", "/api/providers/nvidia_nim/test", {"json": {}}),
        ("post", "/api/providers/nvidia_nim/activate", {"json": {}}),
        ("get", "/api/provider-config", {}),
        ("put", "/api/provider-config/nvidia_nim", {"json": {}}),
        ("get", "/api/providers/models?provider=nvidia_nim", {}),
        ("get", "/api/auth", {}),
        ("put", "/api/auth/nvidia_nim", {"json": {"api_key": "test-secret"}}),
        ("delete", "/api/auth/nvidia_nim", {}),
    ],
)
def test_provider_and_credential_routes_reject_remote_clients(
    tmp_path: Path, method: str, path: str, kwargs: dict
):
    app = FastAPI()
    register_auth_routes(app)
    client = TestClient(app, client=("203.0.113.10", 12345))

    response = getattr(client, method)(path, **kwargs)

    assert response.status_code == 403
