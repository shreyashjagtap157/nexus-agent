"""SQLite-backed evidence ledger for research-mode teams."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


class _ClosingConnection(sqlite3.Connection):
    """SQLite connection context that commits/rolls back and always closes."""

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        try:
            return bool(super().__exit__(exc_type, exc_value, traceback))
        finally:
            self.close()


class ResearchStore:
    _schema_locks: dict[str, Any] = {}
    _schema_locks_guard = threading.Lock()

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS research_sources (
        source_id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id TEXT NOT NULL,
        agent_id TEXT NOT NULL,
        url TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        provider TEXT NOT NULL DEFAULT '',
        content_hash TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at REAL NOT NULL,
        UNIQUE(team_id, content_hash)
    );
    CREATE TABLE IF NOT EXISTS research_claims (
        claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id TEXT NOT NULL,
        statement TEXT NOT NULL,
        claim_type TEXT NOT NULL DEFAULT 'fact',
        created_by TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'unverified',
        created_at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS research_claim_evidence (
        claim_id INTEGER NOT NULL,
        source_id INTEGER NOT NULL,
        quote TEXT NOT NULL,
        quote_present INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(claim_id, source_id),
        FOREIGN KEY(claim_id) REFERENCES research_claims(claim_id),
        FOREIGN KEY(source_id) REFERENCES research_sources(source_id)
    );
    CREATE TABLE IF NOT EXISTS research_verifications (
        verification_id INTEGER PRIMARY KEY AUTOINCREMENT,
        claim_id INTEGER NOT NULL,
        verifier_id TEXT NOT NULL,
        verdict TEXT NOT NULL,
        note TEXT NOT NULL DEFAULT '',
        source_ids_json TEXT NOT NULL DEFAULT '[]',
        created_at REAL NOT NULL,
        FOREIGN KEY(claim_id) REFERENCES research_claims(claim_id)
    );
    CREATE INDEX IF NOT EXISTS idx_research_sources_team ON research_sources(team_id);
    CREATE INDEX IF NOT EXISTS idx_research_claims_team ON research_claims(team_id);
    CREATE TABLE IF NOT EXISTS research_conflicts (
        conflict_id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id TEXT NOT NULL,
        claim_a INTEGER NOT NULL,
        claim_b INTEGER NOT NULL,
        conflict_type TEXT NOT NULL DEFAULT 'contradiction',
        detected_by TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'unresolved',
        resolution TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL,
        resolved_at REAL,
        FOREIGN KEY(claim_a) REFERENCES research_claims(claim_id),
        FOREIGN KEY(claim_b) REFERENCES research_claims(claim_id)
    );
    CREATE INDEX IF NOT EXISTS idx_research_conflicts_team ON research_conflicts(team_id);
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._schema_locks_guard:
            schema_lock = self._schema_locks.setdefault(
                str(self.db_path), threading.RLock()
            )
        # WAL initialization, DDL and migrations must not race when several
        # team workers open a new ledger for the first time.
        with schema_lock:
            self._ensure_schema()
            self._ensure_migrations()

    def _ensure_migrations(self) -> None:
        with self._connect() as conn:
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(research_verifications)").fetchall()
            }
            if "source_ids_json" not in columns:
                conn.execute(
                    "ALTER TABLE research_verifications ADD COLUMN source_ids_json TEXT NOT NULL DEFAULT '[]'"
                )
                conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30,
            factory=_ClosingConnection,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def close(self) -> None:
        """Compatibility no-op; each operation owns and closes its connection."""
        return None

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(self.SCHEMA)
            conn.commit()

    def record_source(
        self,
        team_id: str,
        agent_id: str,
        url: str,
        title: str,
        content: str,
        provider: str = "",
    ) -> dict[str, Any]:
        content = content[:5_000_000]
        digest = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO research_sources(
                    team_id,agent_id,url,title,provider,content_hash,content,created_at
                ) VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(team_id, content_hash) DO NOTHING""",
                (team_id, agent_id, url, title, provider, digest, content, time.time()),
            )
            conn.commit()
            inserted = cur.rowcount == 1
            row = conn.execute(
                "SELECT source_id FROM research_sources WHERE team_id=? AND content_hash=?",
                (team_id, digest),
            ).fetchone()
            if row is None:
                raise RuntimeError(
                    "Research source insert completed without a persisted source row."
                )
            return {
                "source_id": int(row["source_id"]),
                "duplicate": not inserted,
                "content_hash": digest,
            }

    def record_claim(
        self,
        team_id: str,
        agent_id: str,
        statement: str,
        claim_type: str,
        source_id: int,
        quote: str,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            source = conn.execute(
                "SELECT content FROM research_sources WHERE source_id=? AND team_id=?",
                (source_id, team_id),
            ).fetchone()
            if source is None:
                raise ValueError("Unknown research source for this team.")
            quote_present = int(bool(quote.strip()) and quote.strip() in str(source["content"]))
            cur = conn.execute(
                """INSERT INTO research_claims(
                    team_id,statement,claim_type,created_by,status,created_at
                ) VALUES(?,?,?,?,?,?)""",
                (
                    team_id,
                    statement.strip(),
                    claim_type.strip() or "fact",
                    agent_id,
                    "quote_present" if quote_present else "unverified",
                    time.time(),
                ),
            )
            inserted_claim_id = cur.lastrowid
            if inserted_claim_id is None:
                raise RuntimeError("Claim insert did not return a persisted claim ID.")
            claim_id = inserted_claim_id
            conn.execute(
                """INSERT INTO research_claim_evidence(
                    claim_id,source_id,quote,quote_present
                ) VALUES(?,?,?,?)""",
                (claim_id, source_id, quote, quote_present),
            )
            conn.commit()
            return {
                "claim_id": claim_id,
                "quote_present": bool(quote_present),
                "status": "quote_present" if quote_present else "unverified",
            }

    def attach_evidence(
        self,
        team_id: str,
        claim_id: int,
        source_id: int,
        quote: str,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            claim = conn.execute(
                "SELECT claim_id FROM research_claims WHERE claim_id=? AND team_id=?",
                (claim_id, team_id),
            ).fetchone()
            if claim is None:
                raise ValueError("Unknown research claim for this team.")
            source = conn.execute(
                "SELECT content FROM research_sources WHERE source_id=? AND team_id=?",
                (source_id, team_id),
            ).fetchone()
            if source is None:
                raise ValueError("Unknown research source for this team.")
            quote_present = int(bool(quote.strip()) and quote.strip() in str(source["content"]))
            conn.execute(
                """INSERT INTO research_claim_evidence(
                    claim_id,source_id,quote,quote_present
                ) VALUES(?,?,?,?)
                ON CONFLICT(claim_id,source_id) DO UPDATE SET
                    quote=excluded.quote,
                    quote_present=excluded.quote_present""",
                (claim_id, source_id, quote, quote_present),
            )
            evidence_counts = conn.execute(
                """SELECT COUNT(*) AS total, COALESCE(SUM(quote_present), 0) AS present
                   FROM research_claim_evidence WHERE claim_id=?""",
                (claim_id,),
            ).fetchone()
            evidence_complete = (
                evidence_counts is not None
                and int(evidence_counts["total"]) > 0
                and int(evidence_counts["present"]) == int(evidence_counts["total"])
            )
            # Any evidence mutation invalidates previous verifier decisions. Keep
            # the records for auditability, but mark them stale so coverage and
            # synthesis cannot count them toward the current evidence set.
            conn.execute(
                """UPDATE research_verifications
                   SET verdict='stale',
                       note=CASE WHEN note='' THEN
                           'Superseded because claim evidence changed.'
                           ELSE note || char(10) ||
                           'Superseded because claim evidence changed.'
                       END
                   WHERE claim_id=? AND verdict='verified'""",
                (claim_id,),
            )
            conn.execute(
                "UPDATE research_claims SET status=? WHERE claim_id=? AND team_id=?",
                (
                    "quote_present" if evidence_complete else "unverified",
                    claim_id,
                    team_id,
                ),
            )
            conn.commit()
            return {
                "claim_id": claim_id,
                "source_id": source_id,
                "quote_present": bool(quote_present),
            }

    def verify_claim(
        self, team_id: str, claim_id: int, verifier_id: str, note: str = ""
    ) -> dict[str, Any]:
        with self._connect() as conn:
            claim = conn.execute(
                "SELECT * FROM research_claims WHERE claim_id=? AND team_id=?",
                (claim_id, team_id),
            ).fetchone()
            if claim is None:
                raise ValueError("Unknown research claim for this team.")
            evidence = conn.execute(
                """SELECT e.*, s.content, s.content_hash, s.url
                   FROM research_claim_evidence e
                   JOIN research_sources s ON s.source_id=e.source_id
                   WHERE e.claim_id=?""",
                (claim_id,),
            ).fetchall()
            if not evidence:
                verdict = "rejected"
            else:
                matches = all(
                    bool(row["quote"].strip()) and row["quote"].strip() in str(row["content"])
                    for row in evidence
                )
                verdict = "verified" if matches else "rejected"
            source_ids = [int(row["source_id"]) for row in evidence]
            conn.execute(
                """INSERT INTO research_verifications(
                    claim_id,verifier_id,verdict,note,source_ids_json,created_at
                ) VALUES(?,?,?,?,?,?)""",
                (
                    claim_id,
                    verifier_id,
                    verdict,
                    note[:4000],
                    json.dumps(source_ids),
                    time.time(),
                ),
            )
            conn.execute(
                "UPDATE research_claims SET status=? WHERE claim_id=?",
                (verdict, claim_id),
            )
            conn.commit()
            return {
                "claim_id": claim_id,
                "verdict": verdict,
                "evidence_count": len(evidence),
                "source_ids": source_ids,
            }

    def record_conflict(
        self,
        team_id: str,
        agent_id: str,
        claim_a: int,
        claim_b: int,
        conflict_type: str = "contradiction",
    ) -> dict[str, Any]:
        if claim_a == claim_b:
            raise ValueError("A claim cannot conflict with itself.")
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT claim_id FROM research_claims
                   WHERE team_id=? AND claim_id IN (?, ?)""",
                (team_id, claim_a, claim_b),
            ).fetchall()
            if len(rows) != 2:
                raise ValueError("Both conflict claims must belong to this research team.")
            cur = conn.execute(
                """INSERT INTO research_conflicts(
                    team_id,claim_a,claim_b,conflict_type,detected_by,created_at
                ) VALUES(?,?,?,?,?,?)""",
                (team_id, claim_a, claim_b, conflict_type, agent_id, time.time()),
            )
            conn.commit()
            conflict_id = cur.lastrowid
            if conflict_id is None:
                raise RuntimeError("Conflict insert did not return a persisted conflict ID.")
            return {
                "conflict_id": conflict_id,
                "status": "unresolved",
            }

    def adjudicate_conflict(
        self,
        team_id: str,
        conflict_id: int,
        adjudicator_id: str,
        status: str,
        resolution: str,
    ) -> dict[str, Any]:
        normalized = status.strip().lower()
        if normalized not in {"adjudicated", "accepted_uncertainty", "rejected"}:
            raise ValueError(
                "Conflict status must be adjudicated, accepted_uncertainty or rejected."
            )
        if not resolution.strip():
            raise ValueError("A conflict resolution explanation is required.")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT conflict_id FROM research_conflicts WHERE team_id=? AND conflict_id=?",
                (team_id, conflict_id),
            ).fetchone()
            if row is None:
                raise ValueError("Unknown research conflict.")
            conn.execute(
                """UPDATE research_conflicts
                   SET status=?, resolution=?, detected_by=?, resolved_at=?
                   WHERE conflict_id=? AND team_id=?""",
                (normalized, resolution.strip(), adjudicator_id, time.time(), conflict_id, team_id),
            )
            conn.commit()
        return {"conflict_id": conflict_id, "status": normalized}

    def conflicts(self, team_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM research_conflicts
                   WHERE team_id=? ORDER BY conflict_id""",
                (team_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def unresolved_conflicts(self, team_id: str) -> list[dict[str, Any]]:
        return [item for item in self.conflicts(team_id) if item["status"] == "unresolved"]

    def verified_claims(self, team_id: str) -> list[dict[str, Any]]:
        """Return only claims that passed the persisted verification gate, with provenance."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT c.claim_id, c.statement, c.claim_type, c.created_by, c.status,
                          e.source_id, e.quote, s.url, s.title, s.content_hash
                   FROM research_claims c
                   JOIN research_claim_evidence e ON e.claim_id=c.claim_id
                   JOIN research_sources s ON s.source_id=e.source_id
                   WHERE c.team_id=? AND c.status='verified'
                   ORDER BY c.claim_id, e.source_id""",
                (team_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def claims(self, team_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM research_claims WHERE team_id=? ORDER BY claim_id",
                (team_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def sources(self, team_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT source_id,team_id,agent_id,url,title,provider,content_hash,created_at
                   FROM research_sources WHERE team_id=? ORDER BY source_id""",
                (team_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def export(self, team_id: str) -> dict[str, Any]:
        return {
            "team_id": team_id,
            "sources": self.sources(team_id),
            "claims": self.claims(team_id),
            "verified_claims": self.verified_claims(team_id),
            "conflicts": self.conflicts(team_id),
            "unresolved_conflicts": self.unresolved_conflicts(team_id),
        }

    def coverage(self, team_id: str, required_verification_passes: int) -> dict[str, Any]:
        required = max(1, int(required_verification_passes))
        with self._connect() as conn:
            source_count = int(
                conn.execute(
                    "SELECT COUNT(*) AS count FROM research_sources WHERE team_id=?",
                    (team_id,),
                ).fetchone()["count"]
            )
            claim_rows = conn.execute(
                "SELECT claim_id,status FROM research_claims WHERE team_id=? ORDER BY claim_id",
                (team_id,),
            ).fetchall()
            verification_rows = conn.execute(
                """SELECT v.claim_id, v.verifier_id, v.source_ids_json
                   FROM research_verifications v
                   JOIN research_claims c ON c.claim_id=v.claim_id
                   WHERE c.team_id=? AND v.verdict='verified'""",
                (team_id,),
            ).fetchall()
            claim_source_rows = conn.execute(
                """SELECT ce.claim_id, ce.source_id
                   FROM research_claim_evidence ce
                   JOIN research_claims c ON c.claim_id=ce.claim_id
                   WHERE c.team_id=?""",
                (team_id,),
            ).fetchall()

        source_verifier_counts: dict[tuple[int, int], set[str]] = {}
        for row in verification_rows:
            try:
                source_ids = json.loads(row["source_ids_json"] or "[]")
            except (TypeError, ValueError):
                source_ids = []
            for source_id in source_ids if isinstance(source_ids, list) else []:
                key = (int(row["claim_id"]), int(source_id))
                source_verifier_counts.setdefault(key, set()).add(str(row["verifier_id"]))

        total_claims = len(claim_rows)
        verified_claims = sum(1 for row in claim_rows if row["status"] == "verified")
        rejected_claims = sum(1 for row in claim_rows if row["status"] == "rejected")
        unresolved_claims = sum(
            1 for row in claim_rows if row["status"] not in {"verified", "rejected"}
        )
        required_source_checks: dict[int, int] = {}
        for row in claim_source_rows:
            claim_id = int(row["claim_id"])
            source_id = int(row["source_id"])
            required_source_checks[claim_id] = required_source_checks.get(claim_id, 0) + 1

        threshold_claims = 0
        for row in claim_rows:
            claim_id = int(row["claim_id"])
            if row["status"] != "verified":
                continue
            source_ids_for_claim = [
                int(item["source_id"])
                for item in claim_source_rows
                if int(item["claim_id"]) == claim_id
            ]
            if source_ids_for_claim and all(
                len(source_verifier_counts.get((claim_id, source_id), set())) >= required
                for source_id in source_ids_for_claim
            ):
                threshold_claims += 1
        passed = (
            source_count > 0
            and total_claims > 0
            and verified_claims > 0
            and unresolved_claims == 0
            and threshold_claims == verified_claims
        )
        unresolved_conflicts = self.unresolved_conflicts(team_id)
        return {
            "team_id": team_id,
            "required_verification_passes": required,
            "source_count": source_count,
            "claim_count": total_claims,
            "verified_claims": verified_claims,
            "verified_claim_ids": [
                int(row["claim_id"]) for row in claim_rows if row["status"] == "verified"
            ],
            "rejected_claims": rejected_claims,
            "unresolved_claims": unresolved_claims,
            "claims_meeting_verification_threshold": threshold_claims,
            "unresolved_conflicts": len(unresolved_conflicts),
            "conflicts": unresolved_conflicts,
            "passed": passed and not unresolved_conflicts,
        }
