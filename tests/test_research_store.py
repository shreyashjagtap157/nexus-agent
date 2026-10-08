from concurrent.futures import ThreadPoolExecutor

from nexus_agent.research.store import ResearchStore


def test_record_source_deduplicates_identical_content(tmp_path):
    store = ResearchStore(tmp_path / "research.db")
    first = store.record_source(
        "team-1",
        "agent-a",
        "https://example.test/source",
        "Example",
        "same content",
        "test",
    )
    second = store.record_source(
        "team-1",
        "agent-b",
        "https://example.test/other",
        "Other",
        "same content",
        "test",
    )
    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["source_id"] == first["source_id"]


def test_record_source_is_atomic_under_concurrent_duplicate_writes(tmp_path):
    db_path = tmp_path / "research.db"

    def write(index: int):
        store = ResearchStore(db_path)
        return store.record_source(
            "team-1",
            f"agent-{index}",
            f"https://example.test/source-{index}",
            "Example",
            "same concurrent content",
            "test",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(write, range(8)))

    source_ids = {item["source_id"] for item in results}
    assert len(source_ids) == 1
    assert sum(not item["duplicate"] for item in results) == 1

    verifier = ResearchStore(db_path)
    assert len(verifier.sources("team-1")) == 1
