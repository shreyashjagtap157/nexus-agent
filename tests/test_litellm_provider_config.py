from nexus_agent.llm.providers.catalog import get


def test_provider_catalog_exposes_nvidia_nim_and_litellm():
    assert get("nvidia_nim") is not None
    assert get("litellm") is not None
