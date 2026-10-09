"""Tamper-evident append-only audit log for NexusAgent runtime activity."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AuditRecord:
    sequence: int
    record_id: str
    scope: str
    run_id: str | None
    actor: str
    event_type: str
    payload: dict[str, Any]
    created_at: float
    previous_hash: str
    record_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "record_id": self.record_id,
            "scope": self.scope,
            "run_id": self.run_id,
            "actor": self.actor,
            "event_type": self.event_type,
            "payload": self.payload,
            "created_at": self.created_at,
            "previous_hash": self.previous_hash,
            "record_hash": self.record_hash,
        }


_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


class AuditLog:
    """Append-only JSONL audit stream with SHA-256 hash chaining."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = _lock_for(self.path)

    @staticmethod
    def _canonical(payload: dict[str, Any]) -> bytes:
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")

    def _last_hash_and_sequence(self) -> tuple[str, int]:
        if not self.path.exists():
            return "", 0
        last_hash = ""
        sequence = 0
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                data = json.loads(line)
                sequence = int(data["sequence"])
                last_hash = str(data["record_hash"])
        return last_hash, sequence

    def append(
        self,
        *,
        scope: str = "runtime",
        run_id: str | None = None,
        actor: str = "system",
        event_type: str | None = None,
        payload: dict[str, Any] | None = None,
        kind: str | None = None,
    ) -> AuditRecord:
        event = event_type or kind or "event"
        now = time.time()

        with self._lock:
            previous_hash, sequence = self._last_hash_and_sequence()
            record = {
                "sequence": sequence + 1,
                "record_id": uuid.uuid4().hex,
                "scope": str(scope),
                "run_id": run_id,
                "actor": str(actor),
                "event_type": str(event),
                "payload": dict(payload or {}),
                "created_at": now,
                "previous_hash": previous_hash,
            }
            record_hash = hashlib.sha256(self._canonical(record)).hexdigest()
            record["record_hash"] = record_hash

            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        record,
                        ensure_ascii=False,
                        sort_keys=True,
                        default=str,
                    )
                    + "\n"
                )
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass

            return AuditRecord(
                sequence=record["sequence"],
                record_id=record["record_id"],
                scope=record["scope"],
                run_id=run_id,
                actor=record["actor"],
                event_type=record["event_type"],
                payload=record["payload"],
                created_at=now,
                previous_hash=previous_hash,
                record_hash=record_hash,
            )

    def read(self, run_id: str | None = None, limit: int = 1000) -> list[AuditRecord]:
        rows: list[AuditRecord] = []
        if not self.path.exists():
            return rows

        with self._lock:
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if run_id is not None and data.get("run_id") != run_id:
                        continue
                    rows.append(
                        AuditRecord(
                            sequence=int(data["sequence"]),
                            record_id=str(data["record_id"]),
                            scope=str(data.get("scope", "runtime")),
                            run_id=data.get("run_id"),
                            actor=str(data.get("actor", "system")),
                            event_type=str(data.get("event_type", "event")),
                            payload=data.get("payload")
                            if isinstance(data.get("payload"), dict)
                            else {},
                            created_at=float(data["created_at"]),
                            previous_hash=str(data.get("previous_hash", "")),
                            record_hash=str(data["record_hash"]),
                        )
                    )
        return rows[-max(1, min(int(limit), 100000)) :]

    def verify(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"valid": True, "records": 0, "last_hash": ""}

        previous_hash = ""
        records = 0
        last_hash = ""

        with self._lock:
            with self.path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, 1):
                    if not line.strip():
                        continue
                    records += 1
                    data = json.loads(line)
                    if str(data.get("previous_hash", "")) != previous_hash:
                        return {
                            "valid": False,
                            "records": records,
                            "last_hash": last_hash,
                            "error": f"Previous-hash mismatch at line {line_number}.",
                        }

                    stored = str(data.get("record_hash", ""))
                    unsigned = dict(data)
                    unsigned.pop("record_hash", None)
                    calculated = hashlib.sha256(self._canonical(unsigned)).hexdigest()
                    if calculated != stored:
                        return {
                            "valid": False,
                            "records": records,
                            "last_hash": last_hash,
                            "error": f"Record hash mismatch at line {line_number}.",
                        }

                    previous_hash = stored
                    last_hash = stored

        return {"valid": True, "records": records, "last_hash": last_hash}


TamperEvidenceLog = AuditLog
