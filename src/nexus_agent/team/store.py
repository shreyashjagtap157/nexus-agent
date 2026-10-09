"""SQLite persistence for multi-agent teams."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from nexus_agent.audit import AuditLog
from typing import Any


class TeamStore:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS teams (
        team_id TEXT PRIMARY KEY,
        goal TEXT NOT NULL,
        mode TEXT NOT NULL,
        workspace TEXT NOT NULL,
        config_json TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL,
        created_at REAL NOT NULL,
        completed_at REAL,
        quality_json TEXT NOT NULL DEFAULT '{}'
    );
    CREATE TABLE IF NOT EXISTS team_agents (
        agent_id TEXT PRIMARY KEY,
        team_id TEXT NOT NULL,
        name TEXT NOT NULL,
        profession TEXT NOT NULL,
        mission TEXT NOT NULL,
        instructions TEXT NOT NULL,
        role_json TEXT NOT NULL DEFAULT '{}',
        state TEXT NOT NULL,
        model_role TEXT NOT NULL,
        started_at REAL,
        ended_at REAL,
        result TEXT,
        error TEXT,
        FOREIGN KEY(team_id) REFERENCES teams(team_id)
    );
    CREATE TABLE IF NOT EXISTS team_messages (
        message_id TEXT PRIMARY KEY,
        team_id TEXT NOT NULL,
        sender_id TEXT NOT NULL,
        recipient_id TEXT,
        message_type TEXT NOT NULL,
        topic TEXT,
        payload_json TEXT NOT NULL,
        created_at REAL NOT NULL,
        parent_message_id TEXT,
        FOREIGN KEY(team_id) REFERENCES teams(team_id)
    );
    CREATE TABLE IF NOT EXISTS team_events (
        event_id TEXT PRIMARY KEY,
        team_id TEXT NOT NULL,
        agent_id TEXT,
        event_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at REAL NOT NULL,
        FOREIGN KEY(team_id) REFERENCES teams(team_id)
    );
    CREATE INDEX IF NOT EXISTS idx_team_agents_team ON team_agents(team_id);
    CREATE INDEX IF NOT EXISTS idx_team_messages_team_time ON team_messages(team_id, created_at);
    CREATE INDEX IF NOT EXISTS idx_team_events_team_time ON team_events(team_id, created_at);
    CREATE TABLE IF NOT EXISTS team_controls (
        team_id TEXT PRIMARY KEY,
        action TEXT NOT NULL,
        requested_at REAL NOT NULL,
        FOREIGN KEY(team_id) REFERENCES teams(team_id)
    );
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self.SCHEMA)
        self._ensure_migrations()
        self._conn.commit()
        self._audit = AuditLog(self.db_path.parent / "audit.jsonl")

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def migrate(self) -> None:
        """Apply additive schema migrations safely."""
        with self._lock:
            columns = {
                row["name"] for row in self._conn.execute("PRAGMA table_info(teams)").fetchall()
            }
            if "config_json" not in columns:
                self._conn.execute(
                    "ALTER TABLE teams ADD COLUMN config_json TEXT NOT NULL DEFAULT '{}'"
                )
            self._conn.commit()

    def _ensure_migrations(self) -> None:
        columns = {row["name"] for row in self._conn.execute("PRAGMA table_info(teams)").fetchall()}
        if "quality_json" not in columns:
            self._conn.execute(
                "ALTER TABLE teams ADD COLUMN quality_json TEXT NOT NULL DEFAULT '{}'"
            )
        self._conn.commit()

    def create_team(
        self,
        team_id: str,
        goal: str,
        mode: str,
        workspace: str,
        config: dict[str, Any],
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO teams(team_id,goal,mode,workspace,config_json,status,created_at) VALUES(?,?,?,?,?,?,?)",
                (
                    team_id,
                    goal,
                    mode,
                    workspace,
                    json.dumps(config, default=str),
                    "running",
                    time.time(),
                ),
            )
            self._conn.commit()

    def set_status(self, team_id: str, status: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE teams SET status=? WHERE team_id=?",
                (status, team_id),
            )
            self._conn.commit()

    def finish_team(
        self,
        team_id: str,
        status: str,
        quality: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE teams SET status=?, completed_at=?, quality_json=? WHERE team_id=?",
                (
                    status,
                    time.time(),
                    json.dumps(quality or {}, ensure_ascii=False, default=str),
                    team_id,
                ),
            )
            self._conn.commit()

    def add_agent(self, team_id: str, profile: dict[str, Any]) -> str:
        agent_id = f"{team_id}:{profile['role_id']}"
        with self._lock:
            self._conn.execute(
                """INSERT INTO team_agents(
                    agent_id,team_id,name,profession,mission,instructions,role_json,state,model_role
                ) VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    agent_id,
                    team_id,
                    profile["name"],
                    profile["profession"],
                    profile["mission"],
                    profile["instructions"],
                    json.dumps(profile, default=str),
                    "planned",
                    profile.get("model_role", "default"),
                ),
            )
            self._conn.commit()
        return agent_id

    def update_agent(self, agent_id: str, **fields: Any) -> None:
        allowed = {"state", "started_at", "ended_at", "result", "error"}
        updates = {key: value for key, value in fields.items() if key in allowed}
        if not updates:
            return
        with self._lock:
            sets = ",".join(f"{key}=?" for key in updates)
            self._conn.execute(
                f"UPDATE team_agents SET {sets} WHERE agent_id=?",
                (*updates.values(), agent_id),
            )
            self._conn.commit()

    def message(
        self,
        team_id: str,
        sender_id: str,
        message_type: str,
        payload: dict[str, Any],
        recipient_id: str | None = None,
        topic: str | None = None,
        parent_message_id: str | None = None,
    ) -> str:
        message_id = uuid.uuid4().hex[:16]
        with self._lock:
            created_at = time.time()
            self._conn.execute(
                """INSERT INTO team_messages(
                    message_id,team_id,sender_id,recipient_id,message_type,topic,payload_json,created_at,parent_message_id
                ) VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    message_id,
                    team_id,
                    sender_id,
                    recipient_id,
                    message_type,
                    topic,
                    json.dumps(payload, ensure_ascii=False, default=str),
                    created_at,
                    parent_message_id,
                ),
            )
            self._conn.commit()
            self._audit.append(
                scope="team",
                run_id=team_id,
                actor=sender_id,
                event_type=f"message:{message_type}",
                payload={
                    "recipient_id": recipient_id,
                    "topic": topic,
                    "message_id": message_id,
                    "payload": payload,
                },
            )
        return message_id

    def event(
        self,
        team_id: str,
        event_type: str,
        payload: dict[str, Any],
        agent_id: str | None = None,
    ) -> str:
        event_id = uuid.uuid4().hex[:16]
        with self._lock:
            created_at = time.time()
            self._conn.execute(
                "INSERT INTO team_events(event_id,team_id,agent_id,event_type,payload_json,created_at) VALUES(?,?,?,?,?,?)",
                (
                    event_id,
                    team_id,
                    agent_id,
                    event_type,
                    json.dumps(payload, ensure_ascii=False, default=str),
                    created_at,
                ),
            )
            self._conn.commit()
            self._audit.append(
                scope="team",
                run_id=team_id,
                actor=agent_id or "orchestrator",
                event_type=event_type,
                payload=payload,
            )
        return event_id

    def request_control(self, team_id: str, action: str) -> bool:
        action = action.strip().lower()
        if action not in {"pause", "resume", "stop"}:
            return False
        with self._lock:
            team = self._conn.execute(
                "SELECT status FROM teams WHERE team_id=?",
                (team_id,),
            ).fetchone()
            if team is None:
                return False
            if team["status"] in {"completed", "needs_review", "failed", "cancelled"}:
                return False
            self._conn.execute(
                """INSERT INTO team_controls(team_id,action,requested_at)
                   VALUES(?,?,?)
                   ON CONFLICT(team_id) DO UPDATE SET action=excluded.action, requested_at=excluded.requested_at""",
                (team_id, action, time.time()),
            )
            self._conn.commit()
        return True

    def pop_control(self, team_id: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT action FROM team_controls WHERE team_id=?",
                (team_id,),
            ).fetchone()
            if row is None:
                return None
            self._conn.execute("DELETE FROM team_controls WHERE team_id=?", (team_id,))
            self._conn.commit()
        return str(row["action"])

    def list_teams(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """SELECT team_id,goal,mode,workspace,status,config_json,quality_json,created_at,completed_at
                   FROM teams ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (max(1, min(limit, 1000)), max(0, offset)),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["config"] = json.loads(item.pop("config_json") or "{}")
            except (TypeError, ValueError):
                item["config"] = {}
            try:
                item["quality"] = json.loads(item.pop("quality_json") or "{}")
            except (TypeError, ValueError):
                item["quality"] = {}
            result.append(item)
        return result

    def team(self, team_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM teams WHERE team_id=?",
                (team_id,),
            ).fetchone()
        if not row:
            return None
        item = dict(row)
        try:
            item["config"] = json.loads(item.get("config_json") or "{}")
        except (TypeError, ValueError):
            item["config"] = {}
        try:
            item["quality"] = json.loads(item.get("quality_json") or "{}")
        except (TypeError, ValueError):
            item["quality"] = {}
        return item

    def agents(self, team_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM team_agents WHERE team_id=? ORDER BY rowid",
                (team_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def messages(
        self,
        team_id: str,
        recipient_id: str | None = None,
        since: float = 0.0,
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """SELECT * FROM team_messages
                   WHERE team_id=? AND created_at>=?
                     AND (recipient_id IS NULL OR recipient_id=? OR ? IS NULL)
                   ORDER BY created_at ASC""",
                (team_id, since, recipient_id, recipient_id),
            ).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]

    def events(self, team_id: str, limit: int = 1000, offset: int = 0) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM team_events WHERE team_id=? ORDER BY created_at ASC LIMIT ? OFFSET ?",
                (team_id, max(1, min(limit, 5000)), max(offset, 0)),
            ).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]
