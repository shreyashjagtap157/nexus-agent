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
    method: str, path: str, kwargs: dict
):
    app = FastAPI()
    register_auth_routes(app)
    client = TestClient(app, client=("203.0.113.10", 12345))

    response = getattr(client, method)(path, **kwargs)

    assert response.status_code == 403


def test_tenant_routes_reject_remote_clients(tmp_path: Path):
    app = FastAPI()
    register_auth_routes(app)
    client = TestClient(app, client=("203.0.113.10", 12345))
    assert client.get("/api/tenants/acme").status_code == 403
    assert client.get("/api/tenants/acme/users").status_code == 403


def test_tenant_user_lifecycle_is_wired(tmp_path: Path):
    from unittest import mock

    store_path = tmp_path / "auth.json"
    # Route handlers call AuthStore() with no args; bind them to the temp store.
    with mock.patch(
        "nexus_agent.auth.web_routes.AuthStore", lambda: AuthStore(store_path)
    ):
        app = FastAPI()
        register_auth_routes(app)
        client = TestClient(app, client=("127.0.0.1", 12345))

        # 1. Add a user to a tenant (exercises AuthStore.add_user).
        resp = client.post(
            "/api/tenants/acme/users",
            json={"user_id": "alice", "profile": {"name": "Alice"}},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["user_id"] == "alice"
        assert body["user"]["tenant_id"] == "acme"

        # 2. Duplicate user is a conflict.
        dup = client.post(
            "/api/tenants/acme/users", json={"user_id": "alice"}
        )
        assert dup.status_code == 409

        # 3. Listing + fetching the user works.
        assert client.get("/api/tenants/acme/users").status_code == 200
        assert client.get("/api/tenants/acme/users/alice").json()["user"]["name"] == "Alice"
        assert client.get("/api/tenants/acme/users/ghost").status_code == 404

        # 4. Assign a role (exercises AuthStore.add_role via the wired route).
        role = client.put(
            "/api/tenants/acme/users/alice/roles",
            json={"role": {"name": "admin", "scope": "workspace"}},
        )
        assert role.status_code == 200, role.text
        assert role.json()["assigned"] is True
        assert any(
            r.get("name") == "admin"
            for r in client.get("/api/tenants/acme/users/alice").json()["user"]["roles"]
        )

        # 5. Set and read a permission (exercises AuthStore permission methods).
        perm = client.put(
            "/api/tenants/acme/users/alice/permissions",
            json={"resource": "tools/shell", "permission": "execute", "value": True},
        )
        assert perm.status_code == 200, perm.text
        read = client.get(
            "/api/tenants/acme/users/alice/permissions",
            params={"resource": "tools/shell", "permission": "execute"},
        )
        assert read.json()["value"] is True

        # 6. Remove the role and delete the user.
        assert client.delete("/api/tenants/acme/users/alice/roles/admin").status_code == 200
        assert client.delete("/api/tenants/acme/users/alice").status_code == 200
        assert client.get("/api/tenants/acme/users/alice").status_code == 404

