"""
Durable Job Queue & Worker Leases (Module 13)
Implements SQLite-backed distributed job leasing, atomic claims, heartbeats,
and stage checkpoints.
Guarantees: Two workers cannot execute the same job concurrently.
"""

import json
import sqlite3
import time
from typing import Any

from .jobs import JobRecord, JobStage, JobStatus, validate_transition


class DurableJobQueue:
    """
    SQLite-backed durable job queue supporting atomic worker leasing,
    heartbeats, and stage checkpointing.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS durable_jobs (
                    job_id TEXT PRIMARY KEY,
                    current_stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    last_heartbeat REAL NOT NULL,
                    leased_by TEXT,
                    lease_expires_at REAL,
                    agent_version TEXT,
                    prompt_version TEXT,
                    tool_schema_version TEXT,
                    policy_version TEXT,
                    evaluator_version TEXT,
                    input_snapshot TEXT,
                    trajectory TEXT,
                    pending_action TEXT,
                    result TEXT
                );
            """)

    def enqueue_job(self, job: JobRecord) -> None:
        """Enqueues a new job into the durable queue."""
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO durable_jobs (
                    job_id, current_stage, status, attempt_count, created_at, updated_at,
                    last_heartbeat, leased_by, lease_expires_at, agent_version, prompt_version,
                    tool_schema_version, policy_version, evaluator_version, input_snapshot,
                    trajectory, pending_action, result
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.job_id,
                    job.current_stage.value,
                    job.status.value,
                    job.attempt_count,
                    job.created_at,
                    job.updated_at,
                    job.last_heartbeat,
                    job.leased_by,
                    job.lease_expires_at,
                    job.agent_version,
                    job.prompt_version,
                    job.tool_schema_version,
                    job.policy_version,
                    job.evaluator_version,
                    json.dumps(job.input_snapshot),
                    json.dumps(job.trajectory),
                    json.dumps(job.pending_action) if job.pending_action else None,
                    json.dumps(job.result) if job.result else None,
                ),
            )

    def claim_job(self, worker_id: str, lease_duration: float = 30.0) -> JobRecord | None:
        """
        Atomically claims an available or expired job for worker_id.
        Prevents multiple workers from executing the same job concurrently.
        """
        now = time.time()
        lease_until = now + lease_duration

        with self.conn:
            # Find candidate job that is not finished and either unleased or lease expired
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT job_id FROM durable_jobs
                WHERE status NOT IN ('SUCCEEDED', 'FAILED', 'CANCELLED')
                  AND (leased_by IS NULL OR lease_expires_at < ?)
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (now,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            job_id = row["job_id"]

            # Acquire exclusive lease
            cursor.execute(
                """
                UPDATE durable_jobs
                SET leased_by = ?,
                    lease_expires_at = ?,
                    last_heartbeat = ?,
                    updated_at = ?,
                    attempt_count = attempt_count + 1
                WHERE job_id = ?
                  AND (leased_by IS NULL OR lease_expires_at < ?)
                """,
                (worker_id, lease_until, now, now, job_id, now),
            )
            if cursor.rowcount == 0:
                # Race condition: another worker claimed it first
                return None

        return self.get_job(job_id)

    def heartbeat(self, job_id: str, worker_id: str, lease_extension: float = 30.0) -> bool:
        """Refreshes the lease expiration for an active job held by worker_id."""
        now = time.time()
        lease_until = now + lease_extension
        with self.conn:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                UPDATE durable_jobs
                SET last_heartbeat = ?,
                    lease_expires_at = ?
                WHERE job_id = ? AND leased_by = ?
                """,
                (now, lease_until, job_id, worker_id),
            )
            return cursor.rowcount > 0

    def save_checkpoint(
        self,
        job_id: str,
        new_stage: JobStage,
        status: JobStatus,
        step_data: dict[str, Any] | None = None,
        pending_action: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        """
        Persists a state checkpoint to durable SQLite storage, validating transitions.
        """
        existing = self.get_job(job_id)
        if not existing:
            raise KeyError(f"Job '{job_id}' not found.")

        validate_transition(existing.current_stage, new_stage)

        trajectory = existing.trajectory
        if step_data:
            trajectory.append(step_data)

        now = time.time()
        with self.conn:
            self.conn.execute(
                """
                UPDATE durable_jobs
                SET current_stage = ?,
                    status = ?,
                    updated_at = ?,
                    trajectory = ?,
                    pending_action = ?,
                    result = ?
                WHERE job_id = ?
                """,
                (
                    new_stage.value,
                    status.value,
                    now,
                    json.dumps(trajectory),
                    json.dumps(pending_action) if pending_action else None,
                    json.dumps(result) if result else None,
                    job_id,
                ),
            )

    def complete_job(
        self,
        job_id: str,
        worker_id: str,
        final_status: JobStatus,
        result: dict[str, Any] | None = None,
    ) -> None:
        """Marks a job finished and clears worker leasing."""
        now = time.time()
        with self.conn:
            self.conn.execute(
                """
                UPDATE durable_jobs
                SET status = ?,
                    current_stage = ?,
                    updated_at = ?,
                    leased_by = NULL,
                    lease_expires_at = NULL,
                    pending_action = NULL,
                    result = ?
                WHERE job_id = ? AND leased_by = ?
                """,
                (final_status.value, final_status.value, now, json.dumps(result) if result else None, job_id, worker_id),
            )

    def release_job(self, job_id: str, worker_id: str) -> None:
        """Releases a worker's lease immediately (e.g. during graceful shutdown)."""
        with self.conn:
            self.conn.execute(
                """
                UPDATE durable_jobs
                SET leased_by = NULL,
                    lease_expires_at = NULL
                WHERE job_id = ? AND leased_by = ?
                """,
                (job_id, worker_id),
            )

    def get_job(self, job_id: str) -> JobRecord | None:
        """Fetches a job record from SQLite."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM durable_jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        if not row:
            return None

        return JobRecord(
            job_id=row["job_id"],
            current_stage=JobStage(row["current_stage"]),
            status=JobStatus(row["status"]),
            attempt_count=row["attempt_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_heartbeat=row["last_heartbeat"],
            leased_by=row["leased_by"],
            lease_expires_at=row["lease_expires_at"],
            agent_version=row["agent_version"] or "0.13.0",
            prompt_version=row["prompt_version"] or "reddit-draft-v4",
            tool_schema_version=row["tool_schema_version"] or "tools-v2",
            policy_version=row["policy_version"] or "safety-v2",
            evaluator_version=row["evaluator_version"] or "eval-v3",
            input_snapshot=json.loads(row["input_snapshot"] or "{}"),
            trajectory=json.loads(row["trajectory"] or "[]"),
            pending_action=json.loads(row["pending_action"]) if row["pending_action"] else None,
            result=json.loads(row["result"]) if row["result"] else None,
        )

    def list_recoverable_jobs(self) -> list[JobRecord]:
        """Finds all incomplete jobs that require resumption or reconciliation."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT job_id FROM durable_jobs
            WHERE status NOT IN ('SUCCEEDED', 'FAILED', 'CANCELLED')
            ORDER BY created_at ASC
            """
        )
        return [self.get_job(r["job_id"]) for r in cursor.fetchall() if r]

    def close(self) -> None:
        self.conn.close()
