from pathlib import Path

from nexus_agent.llm.providers.models_dev import ModelsDevCatalog


def test_models_dev_catalog_uses_fresh_local_cache(tmp_path: Path):
    cache = tmp_path / "models.json"
    cache.write_text(
        '{"_nexus_fetched_at": 4102444800, "data": {"test": {"name": "Test", "models": {"m1": {"name": "Model One"}}}}}',
        encoding="utf-8",
    )
    catalog = ModelsDevCatalog(cache)
    providers = catalog.providers()
    assert providers[0]["id"] == "test"
    assert catalog.models("test")[0]["id"] == "m1"
