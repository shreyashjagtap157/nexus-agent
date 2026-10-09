"""Append-only JSONL hash-chain audit log."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, TextIO

from filelock import FileLock


_SECRET_PATTERNS = (
    re.compile(r"nvapi-[A-Za-z0-9_-]{12,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I),
    re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*[^\s,;]+"),
)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(k): redact(v)
            for k, v in value.items()
            if str(k).lower()
            not in {
                "api_key",
                "api_secret",
                "secret_key",
                "password",
                "token",
                "access_token",
                "refresh_token",
                "private_key",
            }
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        result = value
        for pattern in _SECRET_PATTERNS:
            result = pattern.sub("[REDACTED]", result)
        return result
    return value


@dataclass(frozen=True)
class AuditRecord:
    event_id: str
    timestamp: float
    scope: str
    run_id: str
    actor: str
    event_type: str
    payload: dict[str, Any]
    previous_hash: str
    record_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AuditLog:
    """Serialize audit writes with a deterministic SHA-256 chain."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._file_lock = FileLock(str(self.path) + ".lock", timeout=30)

    @staticmethod
    def _canonical(record: dict[str, Any]) -> str:
        return json.dumps(
            record, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
        )

    def _last_hash(self) -> str:
        if not self.path.exists():
            return "0" * 64
        try:
            with self.path.open("rb") as handle:
                handle.seek(0, 2)
                position = handle.tell()
                buffer = b""
                while position > 0:
                    chunk_size = min(position, 65536)
                    position -= chunk_size
                    handle.seek(position)
                    buffer = handle.read(chunk_size) + buffer
                    if b"\n" in buffer or position == 0:
                        break
            lines = [
                line
                for line in buffer.decode("utf-8", errors="replace").splitlines()
                if line.strip()
            ]
            if not lines:
                return "0" * 64
            item = json.loads(lines[-1])
            return str(item.get("record_hash") or "0" * 64)
        except (OSError, ValueError, json.JSONDecodeError):
            return "0" * 64

    def append(
        self,
        *,
        scope: str,
        run_id: str,
        actor: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> AuditRecord:
        with self._lock, self._file_lock:
            timestamp = time.time()
            previous = self._last_hash()
            body = {
                "event_id": uuid.uuid4().hex,
                "timestamp": timestamp,
                "scope": scope,
                "run_id": run_id,
                "actor": actor,
                "event_type": event_type,
                "payload": redact(payload or {}),
                "previous_hash": previous,
            }
            canonical = self._canonical(body)
            digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            record = AuditRecord(
                **body,
                record_hash=digest,
            )
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(self._canonical(record.to_dict()) + "\n")
                handle.flush()
            return record

    def read(self, run_id: str | None = None, limit: int | None = None) -> list[AuditRecord]:
        if not self.path.exists():
            return []
        records: list[AuditRecord] = []
        with self._lock, self._file_lock:
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        if run_id and str(data.get("run_id")) != run_id:
                            continue
                        records.append(AuditRecord(**data))
                    except (json.JSONDecodeError, TypeError):
                        continue
        if limit is not None:
            return records[-max(0, limit) :]
        return records

    def verify(self) -> dict[str, Any]:
        previous = "0" * 64
        count = 0
        if not self.path.exists():
            return {"valid": True, "records": 0, "last_hash": previous}
        with self._lock, self._file_lock:
            with self.path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    expected_previous = data.get("previous_hash")
                    if expected_previous != previous:
                        return {
                            "valid": False,
                            "records": count,
                            "line": line_number,
                            "reason": "previous_hash_mismatch",
                        }
                    body = dict(data)
                    record_hash = body.pop("record_hash", "")
                    actual = hashlib.sha256(self._canonical(body).encode("utf-8")).hexdigest()
                    if actual != record_hash:
                        return {
                            "valid": False,
                            "records": count,
                            "line": line_number,
                            "reason": "record_hash_mismatch",
                        }
                    previous = record_hash
                    count += 1
        return {"valid": True, "records": count, "last_hash": previous}

    def export_csv(self, stream: TextIO, run_id: str | None = None) -> None:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "event_id",
                "timestamp",
                "scope",
                "run_id",
                "actor",
                "event_type",
                "payload",
                "previous_hash",
                "record_hash",
            ]
        )
        for record in self.read(run_id=run_id):
            writer.writerow(
                [
                    record.event_id,
                    record.timestamp,
                    record.scope,
                    record.run_id,
                    record.actor,
                    record.event_type,
                    json.dumps(record.payload, ensure_ascii=False, default=str),
                    record.previous_hash,
                    record.record_hash,
                ]
            )
