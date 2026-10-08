"""SQLite-backed evidence ledger for research-mode teams."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class ResearchStore:
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
        created_at REAL NOT NULL,
        FOREIGN KEY(claim_id) REFERENCES research_claims(claim_id)
    );
    CREATE INDEX IF NOT EXISTS idx_research_sources_team ON research_sources(team_id);
    CREATE INDEX IF NOT EXISTS idx_research_claims_team ON research_claims(team_id);
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
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
            existing = conn.execute(
                "SELECT source_id FROM research_sources WHERE team_id=? AND content_hash=?",
                (team_id, digest),
            ).fetchone()
            if existing:
                return {"source_id": int(existing["source_id"]), "duplicate": True, "content_hash": digest}
            cur = conn.execute(
                """INSERT INTO research_sources(
                    team_id,agent_id,url,title,provider,content_hash,content,created_at
                ) VALUES(?,?,?,?,?,?,?,?)""",
                (team_id, agent_id, url, title, provider, digest, content, time.time()),
            )
            conn.commit()
            return {"source_id": int(cur.lastrowid), "duplicate": False, "content_hash": digest}

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
            quote_present = int(
                bool(quote.strip()) and quote.strip() in str(source["content"])
            )
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
            claim_id = int(cur.lastrowid)
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
            quote_present = int(
                bool(quote.strip()) and quote.strip() in str(source["content"])
            )
            conn.execute(
                """INSERT INTO research_claim_evidence(
                    claim_id,source_id,quote,quote_present
                ) VALUES(?,?,?,?)
                ON CONFLICT(claim_id,source_id) DO UPDATE SET
                    quote=excluded.quote,
                    quote_present=excluded.quote_present""",
                (claim_id, source_id, quote, quote_present),
            )
            conn.execute(
                "UPDATE research_claims SET status=? WHERE claim_id=? AND status='unverified'",
                ("quote_present" if quote_present else "unverified", claim_id),
            )
            conn.commit()
            return {
                "claim_id": claim_id,
                "source_id": source_id,
                "quote_present": bool(quote_present),
            }

    def verify_claim(self, team_id: str, claim_id: int, verifier_id: str, note: str = "") -> dict[str, Any]:
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
            conn.execute(
                "INSERT INTO research_verifications(claim_id,verifier_id,verdict,note,created_at) VALUES(?,?,?,?,?)",
                (claim_id, verifier_id, verdict, note[:4000], time.time()),
            )
            conn.execute(
                "UPDATE research_claims SET status=? WHERE claim_id=?",
                (verdict, claim_id),
            )
            conn.commit()
            return {"claim_id": claim_id, "verdict": verdict, "evidence_count": len(evidence)}

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
            verified_rows = conn.execute(
                """SELECT v.claim_id, COUNT(DISTINCT v.verifier_id) AS distinct_verifiers
                   FROM research_verifications v
                   JOIN research_claims c ON c.claim_id=v.claim_id
                   WHERE c.team_id=? AND v.verdict='verified'
                   GROUP BY v.claim_id""",
                (team_id,),
            ).fetchall()

        verification_counts = {
            int(row["claim_id"]): int(row["distinct_verifiers"])
            for row in verified_rows
        }
        total_claims = len(claim_rows)
        verified_claims = sum(1 for row in claim_rows if row["status"] == "verified")
        rejected_claims = sum(1 for row in claim_rows if row["status"] == "rejected")
        unresolved_claims = sum(
            1 for row in claim_rows if row["status"] not in {"verified", "rejected"}
        )
        threshold_claims = sum(
            1
            for row in claim_rows
            if row["status"] == "verified"
            and verification_counts.get(int(row["claim_id"]), 0) >= required
        )
        passed = (
            source_count > 0
            and total_claims > 0
            and verified_claims > 0
            and unresolved_claims == 0
            and threshold_claims == verified_claims
        )
        return {
            "team_id": team_id,
            "required_verification_passes": required,
            "source_count": source_count,
            "claim_count": total_claims,
            "verified_claims": verified_claims,
            "rejected_claims": rejected_claims,
            "unresolved_claims": unresolved_claims,
            "claims_meeting_verification_threshold": threshold_claims,
            "passed": passed,
        }

