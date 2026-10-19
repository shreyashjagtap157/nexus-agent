import os

from nexus_agent.llm.providers.factory import ProviderFactory


def test_provider_factory_prefers_auth_store_over_environment(monkeypatch, tmp_path):
    """AuthStore credentials take priority over environment variables.

    On Python 3.15+, top-level imports used only inside function bodies are
    lazily loaded, so ``factory.AuthStore`` is not a module-level attribute.
    We monkeypatch ``AuthStore.__init__`` at the canonical source location to
    redirect the file path, then seed the store before calling the factory.
    """
    monkeypatch.setenv("NVIDIA_NIM_API_KEY", "env-value")
    config = {
        "providers": {
            "nvidia_nim": {
                "api_url": "https://example.invalid/v1/chat/completions",
                "model": "nvidia/test-model",
            }
        }
    }
    from nexus_agent.auth.store import AuthStore

    auth_file = tmp_path / "auth.json"
    original_init = AuthStore.__init__

    def patched_init(self, path=None, *, backend="auto"):
        original_init(self, path=auth_file, backend="file")

    monkeypatch.setattr(AuthStore, "__init__", patched_init)
    AuthStore(auth_file).set("nvidia_nim", "stored-value")

    ProviderFactory.clear_cache()
    provider = ProviderFactory.create_provider("nvidia_nim", config)
    assert getattr(provider, "_api_key", None) == "stored-value"
