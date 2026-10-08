from nexus_agent.mcp.client import MCPClient


def test_mcp_secret_env_passthrough_is_explicit(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "secret-value")
    client = MCPClient(
        ["python", "-c", "print('ok')"],
        env={
            "GITHUB_TOKEN": "secret-value",
            "NEXUS_TEST": "yes",
            "UNSAFE_SECRET": "no",
        },
        allowed_secret_env=["GITHUB_TOKEN"],
    )
    assert client.env is not None
    assert client.env.get("GITHUB_TOKEN") == "secret-value"
    assert client.env.get("NEXUS_TEST") == "yes"
    assert "UNSAFE_SECRET" not in client.env


def test_mcp_loader_skips_disabled_servers(monkeypatch):
    import nexus_agent.mcp.client as module

    started = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            started.append(kwargs)

        def start(self, **kwargs):
            return False

        @property
        def discovered_tools(self):
            return []

    monkeypatch.setattr(module, "MCPClient", FakeClient)
    module.load_configured_servers({
        "mcp": {
            "servers": [
                {"name": "disabled", "command": "python", "enabled": False},
                {"name": "enabled", "command": "python", "enabled": True},
            ]
        }
    })
    assert len(started) == 1
