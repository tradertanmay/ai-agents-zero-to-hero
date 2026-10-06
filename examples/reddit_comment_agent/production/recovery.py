"""
Crash Recovery and Reconciliation (Module 13)
Recovers uncompleted agent runs after process crashes or worker deaths.
Flagship Concept: Post-commit reconciliation ensures that if a process crashes
after Reddit commits a write, the restarting agent reconciles remote state
rather than creating a duplicate comment.
"""

import hashlib
import time
from typing import Any

from ..reddit import RedditClient
from ..state import RedditAgentState
from ..approval import ApprovalGate
from .jobs import JobRecord, JobStage, JobStatus
from .checkpoints import DurableJobQueue


class RecoveryManager:
    """Scans and recovers orphaned or crashed jobs from durable storage."""

    def __init__(
        self,
        queue: DurableJobQueue,
        client: RedditClient,
        state: RedditAgentState,
        approval_gate: ApprovalGate,
    ) -> None:
        self.queue = queue
        self.client = client
        self.state = state
        self.approval_gate = approval_gate

    def scan_crashed_jobs(self) -> list[JobRecord]:
        """Finds all non-terminal jobs."""
        return self.queue.list_recoverable_jobs()

    def recover_job(self, job_id: str, worker_id: str) -> tuple[str, JobRecord]:
        """
        Recovers a crashed job, determining whether remote reconciliation
        or stage resumption is required.
        Returns: (verdict: str, updated_job: JobRecord)
        """
        job = self.queue.get_job(job_id)
        if not job:
            raise KeyError(f"Job '{job_id}' not found.")

        post_id = job.input_snapshot.get("post_id")
        pending = job.pending_action or {}

        # ---------------------------------------------------------------------
        # FLAGSHIP SCENARIO B: Post-Commit Crash Reconciliation
        # If the job crashed while EXECUTING or VERIFYING, Reddit may have
        # already published the comment before local state was committed!
        # ---------------------------------------------------------------------
        if job.current_stage in (JobStage.EXECUTING, JobStage.VERIFYING):
            target_post_id = pending.get("post_id") or post_id
            expected_body = pending.get("comment_text") or pending.get("body", "")

            # Query remote thread directly from Reddit
            remote_comments = self.client.get_comments(target_post_id, limit=50)
            matching = [
                c for c in remote_comments
                if c["author"] == "u/HeroAgentBot" and c["body"].strip() == expected_body.strip()
            ]

            if matching:
                # RECONCILIATION SUCCESS: Comment exists on Reddit!
                reconciled_comment = matching[0]
                comment_id = reconciled_comment["comment_id"]

                # Ensure local persistent state knows about this comment to prevent duplicates
                self.state.record_submitted_comment(target_post_id, comment_id, expected_body)

                # Transition to SUCCEEDED without re-executing submit_comment!
                self.queue.save_checkpoint(
                    job_id=job.job_id,
                    new_stage=JobStage.SUCCEEDED,
                    status=JobStatus.SUCCEEDED,
                    step_data={
                        "action": "reconciled_after_crash",
                        "comment_id": comment_id,
                        "reconciled": True,
                        "timestamp": time.time(),
                    },
                    result={"comment_id": comment_id, "status": "success", "reconciled": True},
                )
                self.queue.complete_job(
                    job_id=job.job_id,
                    worker_id=worker_id,
                    final_status=JobStatus.SUCCEEDED,
                    result={"comment_id": comment_id, "status": "success", "reconciled": True},
                )
                return "RECONCILED_SUCCESS", self.queue.get_job(job.job_id)

        # ---------------------------------------------------------------------
        # SCENARIO A: Resuming from READY_TO_EXECUTE
        # ---------------------------------------------------------------------
        if job.current_stage == JobStage.READY_TO_EXECUTE:
            # Check if approval capability token is still valid
            token = pending.get("approval_token")
            text = pending.get("comment_text") or pending.get("body", "")

            if token:
                parts = token.split(".")
                if len(parts) == 5:
                    expires_at = float(parts[2])
                    if time.time() < expires_at:
                        return "RESUME_EXECUTION", job

            # Token expired while worker was down -> Re-request approval
            self.queue.save_checkpoint(
                job_id=job.job_id,
                new_stage=JobStage.WAITING_FOR_APPROVAL,
                status=JobStatus.WAITING_FOR_APPROVAL,
                step_data={"event": "approval_expired_reprompt", "timestamp": time.time()},
            )
            return "REPROMPT_APPROVAL", self.queue.get_job(job.job_id)

        # ---------------------------------------------------------------------
        # SCENARIO C: Incomplete Drafting or Inspection
        # ---------------------------------------------------------------------
        return "RESUME_PIPELINE", job
