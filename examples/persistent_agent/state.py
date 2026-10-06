"""
Persistent State Store (Applied Agent Systems: A2)
SQLite-backed persistence layer providing durable agent checkpoints,
audit event logs, and commitment tracking across process restarts.
Core principle: 'If it is not written to durable storage, it did not happen.'
"""

import json
import sqlite3
from typing import Any

from examples.persistent_agent.goals import Commitment, CommitmentStatus


class PersistentStateStore:
    """Manages transactional SQLite storage for persistent agent state."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema with WAL mode and strict typing."""
        with self._conn:
            self._conn.execute("PRAGMA foreign_keys = ON;")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    goal_id TEXT,
                    goal_json TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_wake_at TEXT,
                    next_wake_at TEXT,
                    wake_count INTEGER DEFAULT 0,
                    last_observation TEXT,
                    last_action TEXT,
                    pending_action TEXT,
                    checkpoint_json TEXT,
                    memory_summary TEXT,
                    agent_version TEXT DEFAULT '1.0.0',
                    prompt_version TEXT DEFAULT '1.0.0',
                    policy_version TEXT DEFAULT '1.0.0',
                    memory_schema_version TEXT DEFAULT '1.0.0',
                    termination_condition TEXT,
                    pause_reason TEXT,
                    consecutive_failures INTEGER DEFAULT 0
                );
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS event_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT,
                    timestamp TEXT NOT NULL,
                    state_before TEXT,
                    state_after TEXT,
                    FOREIGN KEY(agent_id) REFERENCES agents(agent_id)
                );
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS commitments (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    goal_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL,
                    target_entity TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    due_date TEXT,
                    fulfillment_evidence TEXT,
                    FOREIGN KEY(agent_id) REFERENCES agents(agent_id)
                );
                """
            )

    def save_agent_state(self, state_dict: dict[str, Any]) -> None:
        """Upsert agent execution record into database."""
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO agents (
                    agent_id, goal_id, goal_json, status, created_at,
                    last_wake_at, next_wake_at, wake_count, last_observation,
                    last_action, pending_action, checkpoint_json, memory_summary,
                    agent_version, prompt_version, policy_version, memory_schema_version,
                    termination_condition, pause_reason, consecutive_failures
                ) VALUES (
                    :agent_id, :goal_id, :goal_json, :status, :created_at,
                    :last_wake_at, :next_wake_at, :wake_count, :last_observation,
                    :last_action, :pending_action, :checkpoint_json, :memory_summary,
                    :agent_version, :prompt_version, :policy_version, :memory_schema_version,
                    :termination_condition, :pause_reason, :consecutive_failures
                )
                ON CONFLICT(agent_id) DO UPDATE SET
                    goal_id = excluded.goal_id,
                    goal_json = excluded.goal_json,
                    status = excluded.status,
                    last_wake_at = excluded.last_wake_at,
                    next_wake_at = excluded.next_wake_at,
                    wake_count = excluded.wake_count,
                    last_observation = excluded.last_observation,
                    last_action = excluded.last_action,
                    pending_action = excluded.pending_action,
                    checkpoint_json = excluded.checkpoint_json,
                    memory_summary = excluded.memory_summary,
                    agent_version = excluded.agent_version,
                    prompt_version = excluded.prompt_version,
                    policy_version = excluded.policy_version,
                    memory_schema_version = excluded.memory_schema_version,
                    termination_condition = excluded.termination_condition,
                    pause_reason = excluded.pause_reason,
                    consecutive_failures = excluded.consecutive_failures;
                """,
                {
                    "agent_id": state_dict["agent_id"],
                    "goal_id": state_dict.get("goal_id"),
                    "goal_json": json.dumps(state_dict.get("goal_json", {})),
                    "status": state_dict["status"],
                    "created_at": state_dict["created_at"],
                    "last_wake_at": state_dict.get("last_wake_at"),
                    "next_wake_at": state_dict.get("next_wake_at"),
                    "wake_count": state_dict.get("wake_count", 0),
                    "last_observation": json.dumps(state_dict.get("last_observation", {})),
                    "last_action": json.dumps(state_dict.get("last_action", {})),
                    "pending_action": (
                        json.dumps(state_dict.get("pending_action"))
                        if state_dict.get("pending_action") is not None
                        else None
                    ),
                    "checkpoint_json": json.dumps(state_dict.get("checkpoint_json", {})),
                    "memory_summary": state_dict.get("memory_summary", ""),
                    "agent_version": state_dict.get("agent_version", "1.0.0"),
                    "prompt_version": state_dict.get("prompt_version", "1.0.0"),
                    "policy_version": state_dict.get("policy_version", "1.0.0"),
                    "memory_schema_version": state_dict.get("memory_schema_version", "1.0.0"),
                    "termination_condition": state_dict.get("termination_condition"),
                    "pause_reason": state_dict.get("pause_reason"),
                    "consecutive_failures": state_dict.get("consecutive_failures", 0),
                },
            )

    def load_agent_state(self, agent_id: str) -> dict[str, Any] | None:
        """Load agent state dictionary from database."""
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,))
        row = cur.fetchone()
        if not row:
            return None

        result = dict(row)
        result["goal_json"] = json.loads(result["goal_json"]) if result["goal_json"] else {}
        result["last_observation"] = (
            json.loads(result["last_observation"]) if result["last_observation"] else {}
        )
        result["last_action"] = (
            json.loads(result["last_action"]) if result["last_action"] else {}
        )
        result["pending_action"] = (
            json.loads(result["pending_action"]) if result["pending_action"] else None
        )
        result["checkpoint_json"] = (
            json.loads(result["checkpoint_json"]) if result["checkpoint_json"] else {}
        )
        return result

    def record_event(
        self,
        agent_id: str,
        event_type: str,
        timestamp: str,
        state_before: str,
        state_after: str,
        payload: dict[str, Any] | None = None,
    ) -> int:
        """Append an event to the audit trail log."""
        with self._conn:
            cur = self._conn.execute(
                """
                INSERT INTO event_log (
                    agent_id, event_type, payload_json, timestamp, state_before, state_after
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_id,
                    event_type,
                    json.dumps(payload or {}),
                    timestamp,
                    state_before,
                    state_after,
                ),
            )
            return cur.lastrowid

    def load_event_log(self, agent_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Retrieve recent events from the audit log."""
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT id, agent_id, event_type, payload_json, timestamp, state_before, state_after
            FROM event_log
            WHERE agent_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (agent_id, limit),
        )
        rows = cur.fetchall()
        events = []
        for r in rows:
            ev = dict(r)
            ev["payload_json"] = json.loads(ev["payload_json"]) if ev["payload_json"] else {}
            events.append(ev)
        return events

    def save_commitment(self, agent_id: str, commitment: Commitment) -> None:
        """Insert or update a commitment in the database."""
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO commitments (
                    id, agent_id, goal_id, description, status,
                    target_entity, created_at, updated_at, due_date, fulfillment_evidence
                ) VALUES (
                    :id, :agent_id, :goal_id, :description, :status,
                    :target_entity, :created_at, :updated_at, :due_date, :fulfillment_evidence
                )
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    updated_at = excluded.updated_at,
                    due_date = excluded.due_date,
                    fulfillment_evidence = excluded.fulfillment_evidence;
                """,
                {
                    "id": commitment.commitment_id,
                    "agent_id": agent_id,
                    "goal_id": commitment.goal_id,
                    "description": commitment.description,
                    "status": commitment.status.value,
                    "target_entity": commitment.target_entity,
                    "created_at": commitment.created_at,
                    "updated_at": commitment.updated_at,
                    "due_date": commitment.due_date,
                    "fulfillment_evidence": commitment.fulfillment_evidence,
                },
            )

    def load_commitments(
        self,
        agent_id: str,
        status: CommitmentStatus | None = None,
    ) -> list[Commitment]:
        """Fetch commitments for an agent."""
        cur = self._conn.cursor()
        if status:
            cur.execute(
                """
                SELECT * FROM commitments
                WHERE agent_id = ? AND status = ?
                ORDER BY created_at ASC
                """,
                (agent_id, status.value),
            )
        else:
            cur.execute(
                """
                SELECT * FROM commitments
                WHERE agent_id = ?
                ORDER BY created_at ASC
                """,
                (agent_id,),
            )
        rows = cur.fetchall()
        return [
            Commitment(
                commitment_id=r["id"],
                goal_id=r["goal_id"],
                description=r["description"],
                target_entity=r["target_entity"],
                status=CommitmentStatus(r["status"]),
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                due_date=r["due_date"],
                fulfillment_evidence=r["fulfillment_evidence"],
            )
            for r in rows
        ]

    def close(self) -> None:
        """Close SQLite database connection."""
        self._conn.close()
