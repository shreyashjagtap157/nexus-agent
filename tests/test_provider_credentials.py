import os

from nexus_agent.llm.providers.factory import ProviderFactory


def test_provider_factory_prefers_auth_store_over_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("NVIDIA_NIM_API_KEY", "env-value")
    config = {
        "providers": {
            "nvidia_nim": {
                "api_url": "https://example.invalid/v1/chat/completions",
                "model": "nvidia/test-model",
            }
        }
    }
    from nexus_agent.auth import AuthStore
    monkeypatch.setattr(
        "nexus_agent.llm.providers.factory.AuthStore",
        lambda: AuthStore(tmp_path / "auth.json"),
    )
    AuthStore(tmp_path / "auth.json").set("nvidia_nim", "stored-value")
    provider = ProviderFactory.create_provider("nvidia_nim", config)
    assert getattr(provider, "_api_key", None) == "stored-value"
