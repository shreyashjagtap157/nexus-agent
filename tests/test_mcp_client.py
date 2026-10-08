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
