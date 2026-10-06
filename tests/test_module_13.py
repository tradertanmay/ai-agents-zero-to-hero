"""
Tests for Module 13: Production Agents
Verifies durable execution, state machine constraints, distributed worker leases,
post-commit reconciliation, secret redaction, telemetry, and health probes.
"""

import json
import os
import sys
import tempfile
import time
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from examples.reddit_comment_agent.mock_reddit import MockRedditEnvironment, MockPost
from examples.reddit_comment_agent.reddit import MockRedditClient
from examples.reddit_comment_agent.state import RedditAgentState
from examples.reddit_comment_agent.approval import ApprovalGate
from examples.reddit_comment_agent.production.config import AgentConfig, redact_secrets
from examples.reddit_comment_agent.production.jobs import (
    JobRecord,
    JobStage,
    JobStatus,
    InvalidStateTransitionError,
)
from examples.reddit_comment_agent.production.checkpoints import DurableJobQueue
from examples.reddit_comment_agent.production.telemetry import (
    StructuredLogger,
    MetricsRegistry,
    Tracer,
)
from examples.reddit_comment_agent.production.health import HealthCheckHandler
from examples.reddit_comment_agent.production.recovery import RecoveryManager
from examples.reddit_comment_agent.production.worker import AgentWorker


class TestModule13(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "jobs.db")
        self.queue = DurableJobQueue(self.db_path)
        self.env = MockRedditEnvironment()
        self.client = MockRedditClient(self.env)
        self.state = RedditAgentState(":memory:")
        self.approval_gate = ApprovalGate(interactive=False)

        # Standard test post
        self.post_id = "test_prod_post"
        self.env.posts[self.post_id] = MockPost(
            post_id=self.post_id,
            subreddit="r/Python",
            author="u/test_author",
            title="Production Worker Test",
            selftext="Testing distributed worker leases.",
            upvotes=5,
        )

    def tearDown(self):
        self.queue.close()
        self.state.close()
        self.tmp_dir.cleanup()

    def test_job_survives_process_restart(self):
        """Verifies that an enqueued job persists in SQLite across connection resets."""
        job = JobRecord(
            job_id="RUN-RESTART-01",
            agent_version="0.13.0",
            prompt_version="reddit-draft-v4",
            current_stage=JobStage.QUEUED,
            status=JobStatus.QUEUED,
            input_snapshot={"post_id": self.post_id},
        )
        self.queue.enqueue_job(job)

        # Simulate process termination: close DB connection and create fresh queue instance
        self.queue.close()
        fresh_queue = DurableJobQueue(self.db_path)
        restored = fresh_queue.get_job("RUN-RESTART-01")

        self.assertIsNotNone(restored)
        self.assertEqual(restored.job_id, "RUN-RESTART-01")
        self.assertEqual(restored.current_stage, JobStage.QUEUED)
        self.assertEqual(restored.agent_version, "0.13.0")
        self.assertEqual(restored.input_snapshot.get("post_id"), self.post_id)
        fresh_queue.close()

    def test_expired_lease_can_be_reclaimed(self):
        """Verifies that an expired worker lease can be claimed by another worker."""
        job = JobRecord(job_id="RUN-LEASE-01", current_stage=JobStage.QUEUED, status=JobStatus.QUEUED)
        self.queue.enqueue_job(job)

        # Worker-1 claims with short lease (0.05s)
        claimed_w1 = self.queue.claim_job("Worker-1", lease_duration=0.05)
        self.assertIsNotNone(claimed_w1)
        self.assertEqual(claimed_w1.leased_by, "Worker-1")

        # Wait for lease expiration
        time.sleep(0.08)

        # Worker-2 claims expired job
        claimed_w2 = self.queue.claim_job("Worker-2", lease_duration=5.0)
        self.assertIsNotNone(claimed_w2)
        self.assertEqual(claimed_w2.leased_by, "Worker-2")
        self.assertEqual(claimed_w2.attempt_count, 2)

    def test_active_lease_cannot_be_double_claimed(self):
        """Verifies mutual exclusion: active unexpired lease cannot be claimed by another worker."""
        job = JobRecord(job_id="RUN-MUTEX-01", current_stage=JobStage.QUEUED, status=JobStatus.QUEUED)
        self.queue.enqueue_job(job)

        # Worker-1 claims with 10-second lease
        c1 = self.queue.claim_job("Worker-1", lease_duration=10.0)
        self.assertIsNotNone(c1)

        # Worker-2 attempts to claim concurrently
        c2 = self.queue.claim_job("Worker-2", lease_duration=10.0)
        self.assertIsNone(c2, "Worker-2 should not be able to claim a job with an active lease.")

    def test_checkpoint_resumes_correct_stage(self):
        """Verifies that restarting a crashed job restores the exact stage and pending payload."""
        job = JobRecord(job_id="RUN-STAGE-01", current_stage=JobStage.QUEUED, status=JobStatus.QUEUED)
        self.queue.enqueue_job(job)
        self.queue.claim_job("Worker-1", lease_duration=10.0)

        # Transition through stages
        self.queue.save_checkpoint("RUN-STAGE-01", JobStage.INSPECTING, JobStatus.IN_PROGRESS)
        self.queue.save_checkpoint("RUN-STAGE-01", JobStage.DRAFTING, JobStatus.IN_PROGRESS)
        self.queue.save_checkpoint(
            "RUN-STAGE-01",
            JobStage.EVALUATING,
            JobStatus.IN_PROGRESS,
            pending_action={"draft_text": "Draft for checkpoint test"},
        )
        self.queue.save_checkpoint(
            "RUN-STAGE-01",
            JobStage.WAITING_FOR_APPROVAL,
            JobStatus.WAITING_FOR_APPROVAL,
            pending_action={"draft_text": "Draft for checkpoint test", "score": 8.5},
        )

        # Release lease as if worker crashed
        self.queue.release_job("RUN-STAGE-01", "Worker-1")

        # Worker-2 resumes
        resumed = self.queue.claim_job("Worker-2", lease_duration=10.0)
        self.assertIsNotNone(resumed)
        self.assertEqual(resumed.current_stage, JobStage.WAITING_FOR_APPROVAL)
        self.assertEqual(resumed.pending_action.get("draft_text"), "Draft for checkpoint test")

    def test_remote_success_plus_local_crash_reconciles(self):
        """
        Flagship Test:
        Reddit committed the comment, but the process crashed before saving the local success checkpoint.
        On restart, RecoveryManager reconciles remote state, marks SUCCEEDED, and does NOT duplicate!
        """
        job_id = "RUN-CRASH-RECON"
        draft = "Reconciliation test draft"
        token = self.approval_gate.generate_token(self.post_id, draft)

        job = JobRecord(
            job_id=job_id,
            current_stage=JobStage.QUEUED,
            status=JobStatus.QUEUED,
            input_snapshot={"post_id": self.post_id},
        )
        self.queue.enqueue_job(job)
        self.queue.claim_job("Worker-1", lease_duration=0.5)

        # 1. Reddit commits the comment remotely
        remote_rec = self.client.submit_comment(self.post_id, draft)
        self.assertEqual(remote_rec["status"], "success")

        # 2. Advance to EXECUTING before simulated crash
        self.queue.save_checkpoint(job_id, JobStage.INSPECTING, JobStatus.IN_PROGRESS)
        self.queue.save_checkpoint(job_id, JobStage.DRAFTING, JobStatus.IN_PROGRESS)
        self.queue.save_checkpoint(job_id, JobStage.EVALUATING, JobStatus.IN_PROGRESS)
        self.queue.save_checkpoint(job_id, JobStage.WAITING_FOR_APPROVAL, JobStatus.WAITING_FOR_APPROVAL)
        self.queue.save_checkpoint(job_id, JobStage.READY_TO_EXECUTE, JobStatus.READY_TO_EXECUTE)
        self.queue.save_checkpoint(
            job_id,
            JobStage.EXECUTING,
            JobStatus.IN_PROGRESS,
            pending_action={"post_id": self.post_id, "comment_text": draft, "approval_token": token},
        )

        # 3. Process crashes -> Worker-2 recovers
        time.sleep(0.6)  # Wait for lease expiry
        recovery_mgr = RecoveryManager(self.queue, self.client, self.state, self.approval_gate)
        verdict, recovered_job = recovery_mgr.recover_job(job_id, "Worker-2")

        self.assertEqual(verdict, "RECONCILED_SUCCESS")
        self.assertEqual(recovered_job.status, JobStatus.SUCCEEDED)
        self.assertEqual(recovered_job.result["comment_id"], remote_rec["comment_id"])

        # Invariant: exactly 1 comment exists on server
        comments = [c for c in self.client.get_comments(self.post_id) if c["author"] == "u/HeroAgentBot"]
        self.assertEqual(len(comments), 1)

    def test_duplicate_side_effect_never_occurs(self):
        """Verifies that running recovery repeatedly on the same job never creates duplicate writes."""
        job_id = "RUN-DUP-CHECK"
        draft = "Unique text"
        job = JobRecord(
            job_id=job_id,
            current_stage=JobStage.QUEUED,
            status=JobStatus.QUEUED,
            input_snapshot={"post_id": self.post_id},
        )
        self.queue.enqueue_job(job)
        self.queue.claim_job("Worker-A", lease_duration=0.1)

        # Remote submit
        self.client.submit_comment(self.post_id, draft)

        # Advance to EXECUTING
        self.queue.save_checkpoint(job_id, JobStage.INSPECTING, JobStatus.IN_PROGRESS)
        self.queue.save_checkpoint(job_id, JobStage.DRAFTING, JobStatus.IN_PROGRESS)
        self.queue.save_checkpoint(job_id, JobStage.EVALUATING, JobStatus.IN_PROGRESS)
        self.queue.save_checkpoint(job_id, JobStage.WAITING_FOR_APPROVAL, JobStatus.WAITING_FOR_APPROVAL)
        self.queue.save_checkpoint(job_id, JobStage.READY_TO_EXECUTE, JobStatus.READY_TO_EXECUTE)
        self.queue.save_checkpoint(
            job_id,
            JobStage.EXECUTING,
            JobStatus.IN_PROGRESS,
            pending_action={"post_id": self.post_id, "comment_text": draft},
        )

        recovery_mgr = RecoveryManager(self.queue, self.client, self.state, self.approval_gate)
        # First recovery
        recovery_mgr.recover_job(job_id, "Worker-B")
        # Second recovery attempt on same job
        recovery_mgr.recover_job(job_id, "Worker-C")

        comments = [c for c in self.client.get_comments(self.post_id) if c["author"] == "u/HeroAgentBot"]
        self.assertEqual(len(comments), 1, "Duplicate comment must never be created during multiple recovery cycles.")

    def test_sigterm_produces_safe_checkpoint(self):
        """Verifies that request_shutdown() releases the active job lease immediately."""
        job = JobRecord(job_id="RUN-SIGTERM-01", current_stage=JobStage.QUEUED, status=JobStatus.QUEUED)
        self.queue.enqueue_job(job)

        worker = AgentWorker(
            worker_id="Worker-Graceful",
            queue=self.queue,
            client=self.client,
            state=self.state,
            approval_gate=self.approval_gate,
        )

        # Claim job
        self.queue.claim_job("Worker-Graceful", lease_duration=30.0)
        worker.active_job_id = "RUN-SIGTERM-01"

        # Signal shutdown
        worker.request_shutdown()

        # Check that lease was released in SQLite
        updated = self.queue.get_job("RUN-SIGTERM-01")
        self.assertIsNone(updated.leased_by)
        self.assertIsNone(updated.lease_expires_at)
        self.assertTrue(worker.shutdown_requested)

    def test_secret_values_are_redacted(self):
        """Verifies that sensitive tokens and keys are masked in structured logs and telemetry."""
        payload = {
            "user": "alice",
            "reddit_client_secret": "my_super_secret_password_123",
            "approval_token": "post_101.sha256hash.1790000000.nonce99.signaturehex",
            "normal_data": "public_comment_text",
            "nested": {
                "api_key": "secret_key_456",
            },
        }
        redacted = redact_secrets(payload)
        self.assertEqual(redacted["reddit_client_secret"], "***REDACTED***")
        self.assertEqual(redacted["nested"]["api_key"], "***REDACTED***")
        self.assertEqual(redacted["normal_data"], "public_comment_text")

        # Test logger sink contains redaction
        log_sink = []
        logger = StructuredLogger(log_sink)
        logger.info(
            run_id="R-1",
            job_id="J-1",
            trace_id="T-1",
            stage="TEST",
            event="test_event",
            secret_value="top_secret_token",
        )
        self.assertNotIn("top_secret_token", log_sink[0])
        self.assertIn("***REDACTED***", log_sink[0])

    def test_invalid_state_transition_rejected(self):
        """Verifies that illegal transitions raise InvalidStateTransitionError."""
        job = JobRecord(job_id="RUN-INVALID-01", current_stage=JobStage.QUEUED, status=JobStatus.QUEUED)
        self.queue.enqueue_job(job)

        with self.assertRaises(InvalidStateTransitionError):
            # QUEUED -> EXECUTING is strictly illegal
            self.queue.save_checkpoint("RUN-INVALID-01", JobStage.EXECUTING, JobStatus.IN_PROGRESS)

    def test_readiness_fails_when_db_unavailable(self):
        """Verifies that /health/ready fails when SQLite database is unreachable."""
        invalid_db_path = "/non_existent_dir_xyz/impossible_db.sqlite"
        handler = HealthCheckHandler(db_path=invalid_db_path, reddit_client=self.client)
        code, body = handler.check_readiness()
        self.assertEqual(code, 503)
        self.assertEqual(body["status"], "DOWN")
        self.assertIn("error", body)

    def test_run_ids_propagate_through_telemetry(self):
        """Verifies that all logs and trace spans carry correlation IDs."""
        sink = []
        logger = StructuredLogger(sink)
        tracer = Tracer()
        trace_id = "trace_CORRELATION_99"

        logger.info(
            run_id="RUN-99",
            job_id="RUN-99",
            trace_id=trace_id,
            stage="INSPECTING",
            event="inspected_post",
        )
        entry = json.loads(sink[0])
        self.assertEqual(entry["run_id"], "RUN-99")
        self.assertEqual(entry["trace_id"], trace_id)

        span = tracer.start_span(trace_id, "test_operation")
        span.finish()
        self.assertEqual(span.trace_id, trace_id)

    def test_old_agent_version_remains_attributable(self):
        """Verifies that version tags are preserved across transitions and completions."""
        job = JobRecord(
            job_id="RUN-LEGACY-01",
            agent_version="0.10.0",
            prompt_version="reddit-draft-v1",
            tool_schema_version="tools-v1",
            policy_version="safety-v1",
            evaluator_version="eval-v1",
            current_stage=JobStage.QUEUED,
            status=JobStatus.QUEUED,
        )
        self.queue.enqueue_job(job)
        self.queue.claim_job("Worker-1")

        self.queue.save_checkpoint("RUN-LEGACY-01", JobStage.INSPECTING, JobStatus.IN_PROGRESS)
        self.queue.complete_job("RUN-LEGACY-01", "Worker-1", JobStatus.SUCCEEDED, result={"done": True})

        stored = self.queue.get_job("RUN-LEGACY-01")
        self.assertEqual(stored.agent_version, "0.10.0")
        self.assertEqual(stored.prompt_version, "reddit-draft-v1")
        self.assertEqual(stored.policy_version, "safety-v1")
        self.assertEqual(stored.status, JobStatus.SUCCEEDED)


if __name__ == "__main__":
    unittest.main()
