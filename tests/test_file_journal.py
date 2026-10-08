from pathlib import Path

from nexus_agent.storage.journal import FileJournal


def test_file_journal_records_and_reads_mutations(tmp_path: Path):
    journal = FileJournal(tmp_path / "journal.db")
    change_id = journal.record(
        "write",
        "example.txt",
        previous_hash="old",
        new_hash="new",
        actor="test",
        details={"kind": "unit-test"},
    )
    rows = journal.recent(10)
    journal.close()
    assert rows
    assert rows[0]["change_id"] == change_id
    assert rows[0]["operation"] == "write"
    assert rows[0]["actor"] == "test"
    assert rows[0]["details"]["kind"] == "unit-test"
