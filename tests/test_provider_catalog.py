from nexus_agent.llm.providers.catalog import get


def test_provider_catalog_has_core_compatible_and_nim_entries():
    nvidia = get("nvidia_nim")
    assert nvidia is not None
    assert nvidia.protocol == "openai_compatible"
    assert nvidia.env_key == "NVIDIA_NIM_API_KEY"
    litellm = get("litellm")
    assert litellm is not None
    assert litellm.protocol == "litellm"
    custom = get("custom")
    assert custom is not None
    assert custom.supports_custom_models is True
