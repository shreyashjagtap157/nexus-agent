from pathlib import Path

from nexus_agent.audit import AuditLog


def test_audit_log_hash_chain_and_redaction(tmp_path: Path):
    path = tmp_path / "activity.jsonl"
    audit = AuditLog(path)
    audit.append(
        scope="team",
        run_id="team-1",
        actor="verifier",
        event_type="test",
        payload={
            "message": "keep this",
            "api_key": "nvapi-test-secret",
            "nested": "Bearer secret-token-1234567890",
        },
    )
    audit.append(
        scope="team",
        run_id="team-1",
        actor="orchestrator",
        event_type="done",
        payload={"ok": True},
    )
    verification = audit.verify()
    assert verification["valid"] is True
    assert verification["records"] == 2
    records = audit.read(run_id="team-1")
    assert len(records) == 2
    encoded = path.read_text(encoding="utf-8")
    assert "nvapi-test-secret" not in encoded
    assert "secret-token-1234567890" not in encoded

    # Tampering must invalidate the chain.
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[-1] = lines[-1].replace('"ok":true', '"ok":false')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert audit.verify()["valid"] is False


def test_audit_log_concurrent_writers_are_serialized(tmp_path: Path):
    from concurrent.futures import ThreadPoolExecutor
    from nexus_agent.audit import AuditLog

    path = tmp_path / "concurrent.jsonl"
    logs = [AuditLog(path), AuditLog(path)]

    def write(index: int) -> None:
        logs[index % 2].append(
            scope="team",
            run_id="team-concurrent",
            actor=f"agent-{index}",
            event_type="concurrent",
            payload={"index": index},
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write, range(80)))

    result = logs[0].verify()
    assert result["valid"] is True
    assert result["records"] == 80
