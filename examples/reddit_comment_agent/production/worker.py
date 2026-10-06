"""
Background Worker & Execution Loop (Module 13)
Implements durable job polling, lease renewal heartbeats, stage dispatching,
and graceful shutdown on SIGTERM / SIGINT.
"""

import signal
import time
from typing import Any, Callable

from ..reddit import RedditClient
from ..state import RedditAgentState
from ..approval import ApprovalGate, ApprovalDecision
from ..evaluator import CommentEvaluator
from ..safety import (
    SafetyVerificationHarness,
    ActionProposal,
    Capability,
    DEFAULT_AGENT_CAPABILITIES,
)
from .config import AgentConfig
from .jobs import JobRecord, JobStage, JobStatus
from .checkpoints import DurableJobQueue
from .telemetry import StructuredLogger, MetricsRegistry, Tracer
from .recovery import RecoveryManager


class AgentWorker:
    """Production agent worker that claims leased jobs and drives state machine."""

    def __init__(
        self,
        worker_id: str,
        queue: DurableJobQueue,
        client: RedditClient,
        state: RedditAgentState,
        approval_gate: ApprovalGate,
        config: AgentConfig | None = None,
        logger: StructuredLogger | None = None,
        metrics: MetricsRegistry | None = None,
        tracer: Tracer | None = None,
        evaluator: CommentEvaluator | None = None,
    ) -> None:
        self.worker_id = worker_id
        self.queue = queue
        self.client = client
        self.state = state
        self.approval_gate = approval_gate
        self.config = config or AgentConfig()
        self.logger = logger or StructuredLogger()
        self.metrics = metrics or MetricsRegistry()
        self.tracer = tracer or Tracer()
        self.evaluator = evaluator or CommentEvaluator()
        self.recovery = RecoveryManager(self.queue, self.client, self.state, self.approval_gate)
        self.safety_harness = SafetyVerificationHarness(self.client, self.state, self.approval_gate)

        self.shutdown_requested = False
        self.active_job_id: str | None = None

    def setup_signal_handlers(self) -> None:
        """Configures POSIX signal handlers for graceful shutdown."""
        def _handle_shutdown(signum: int, frame: Any) -> None:
            self.request_shutdown()
        try:
            signal.signal(signal.SIGTERM, _handle_shutdown)
            signal.signal(signal.SIGINT, _handle_shutdown)
        except (ValueError, AttributeError):
            # Not supported in some threaded or Windows environments
            pass

    def request_shutdown(self) -> None:
        """Sets shutdown flag, ensuring worker drains or checkpoints safely."""
        self.shutdown_requested = True
        if self.active_job_id:
            # Release lease so other workers can immediately pick up
            self.queue.release_job(self.active_job_id, self.worker_id)
            self.active_job_id = None

    def run_once(self) -> bool:
        """
        Polls and executes one job lifecycle step.
        Returns True if a job was claimed and worked on, False if queue is empty.
        """
        if self.shutdown_requested:
            return False

        job = self.queue.claim_job(
            worker_id=self.worker_id,
            lease_duration=self.config.lease_duration_seconds,
        )
        if not job:
            return False

        self.active_job_id = job.job_id
        self.metrics.agent_runs_total += 1
        start_time = time.time()
        trace_id = f"trace_{job.job_id}"

        self.logger.info(
            run_id=job.job_id,
            job_id=job.job_id,
            trace_id=trace_id,
            stage=job.current_stage.value,
            event="job_claimed",
            worker_id=self.worker_id,
        )

        try:
            self.process_job(job, trace_id)
            duration = time.time() - start_time
            self.metrics.total_duration_seconds += duration
            return True
        except Exception as exc:
            self.metrics.agent_runs_failed_total += 1
            self.logger.error(
                run_id=job.job_id,
                job_id=job.job_id,
                trace_id=trace_id,
                stage=job.current_stage.value,
                event="job_exception",
                error=f"{type(exc).__name__}: {str(exc)}",
            )
            # Release lease on crash
            self.queue.release_job(job.job_id, self.worker_id)
            raise
        finally:
            self.active_job_id = None

    def process_job(self, job: JobRecord, trace_id: str) -> None:
        """Drives the state machine until completion or WAITING_FOR_APPROVAL."""
        # Check if job requires recovery or reconciliation first
        if job.current_stage in (JobStage.EXECUTING, JobStage.VERIFYING):
            verdict, recovered_job = self.recovery.recover_job(job.job_id, self.worker_id)
            if verdict == "RECONCILED_SUCCESS":
                self.metrics.agent_runs_success_total += 1
                self.metrics.reconciliation_total += 1
                return

        # STAGE: QUEUED or DISCOVERING
        if job.current_stage == JobStage.QUEUED:
            span = self.tracer.start_span(trace_id, "discover_posts")
            subreddit = job.input_snapshot.get("subreddit", "r/Python")
            posts = self.client.list_posts(subreddit, limit=3)
            span.finish()
            self.queue.heartbeat(job.job_id, self.worker_id)

            self.queue.save_checkpoint(
                job_id=job.job_id,
                new_stage=JobStage.INSPECTING,
                status=JobStatus.IN_PROGRESS,
                step_data={"stage": "discover", "discovered_count": len(posts)},
            )
            job = self.queue.get_job(job.job_id)

        # STAGE: INSPECTING
        if job.current_stage == JobStage.INSPECTING:
            span = self.tracer.start_span(trace_id, "inspect_post")
            post_id = job.input_snapshot.get("post_id", "post_py_101")
            post = self.client.get_post(post_id)
            span.finish()

            span_comm = self.tracer.start_span(trace_id, "read_comments")
            comments = self.client.get_comments(post_id, limit=3)
            span_comm.finish()
            self.queue.heartbeat(job.job_id, self.worker_id)

            self.queue.save_checkpoint(
                job_id=job.job_id,
                new_stage=JobStage.DRAFTING,
                status=JobStatus.IN_PROGRESS,
                step_data={"stage": "inspect", "post_id": post_id, "comments_count": len(comments)},
            )
            job = self.queue.get_job(job.job_id)

        # STAGE: DRAFTING
        if job.current_stage == JobStage.DRAFTING:
            span = self.tracer.start_span(trace_id, "draft_comment")
            post_id = job.input_snapshot.get("post_id", "post_py_101")
            draft_text = "Use functools.lru_cache for memoization in Python standard library."
            span.finish()
            self.queue.heartbeat(job.job_id, self.worker_id)

            self.queue.save_checkpoint(
                job_id=job.job_id,
                new_stage=JobStage.EVALUATING,
                status=JobStatus.IN_PROGRESS,
                step_data={"stage": "draft", "draft_text": draft_text},
                pending_action={"post_id": post_id, "draft_text": draft_text},
            )
            job = self.queue.get_job(job.job_id)

        # STAGE: EVALUATING
        if job.current_stage == JobStage.EVALUATING:
            span = self.tracer.start_span(trace_id, "evaluate")
            post_id = job.input_snapshot.get("post_id", "post_py_101")
            draft = job.pending_action.get("draft_text", "")
            post = self.client.get_post(post_id) or {"title": "Post", "selftext": ""}
            rules = self.client.get_subreddit_rules("r/Python")
            comments = self.client.get_comments(post_id, limit=3)

            scorecard = self.evaluator.evaluate(post, rules, comments, draft)
            span.finish()
            self.queue.heartbeat(job.job_id, self.worker_id)

            self.logger.info(
                run_id=job.job_id,
                job_id=job.job_id,
                trace_id=trace_id,
                stage="EVALUATING",
                event="draft_scored",
                score=scorecard.total_score,
            )

            self.queue.save_checkpoint(
                job_id=job.job_id,
                new_stage=JobStage.WAITING_FOR_APPROVAL,
                status=JobStatus.WAITING_FOR_APPROVAL,
                step_data={"stage": "evaluate", "score": scorecard.total_score},
                pending_action={"post_id": post_id, "draft_text": draft, "score": scorecard.total_score},
            )
            job = self.queue.get_job(job.job_id)

        # STAGE: WAITING_FOR_APPROVAL
        if job.current_stage == JobStage.WAITING_FOR_APPROVAL:
            span = self.tracer.start_span(trace_id, "wait_for_approval")
            post_id = job.pending_action.get("post_id")
            draft = job.pending_action.get("draft_text")

            # Check if approval decision is already simulated/available
            decision = self.approval_gate.request_approval(post_id, draft)
            span.finish()

            if not decision.approved:
                self.metrics.approval_rejections_total += 1
                self.queue.complete_job(
                    job_id=job.job_id,
                    worker_id=self.worker_id,
                    final_status=JobStatus.CANCELLED,
                    result={"reason": "Rejected by human approval gate."},
                )
                return

            self.metrics.approvals_granted_total += 1
            token = decision.approval_token or self.approval_gate.generate_token(post_id, draft)

            self.queue.save_checkpoint(
                job_id=job.job_id,
                new_stage=JobStage.READY_TO_EXECUTE,
                status=JobStatus.READY_TO_EXECUTE,
                step_data={"stage": "approval_granted"},
                pending_action={
                    "post_id": post_id,
                    "comment_text": draft,
                    "approval_token": token,
                },
            )
            job = self.queue.get_job(job.job_id)

        # STAGE: READY_TO_EXECUTE & EXECUTING
        if job.current_stage == JobStage.READY_TO_EXECUTE:
            # Transition to EXECUTING before making external side effect
            self.queue.save_checkpoint(
                job_id=job.job_id,
                new_stage=JobStage.EXECUTING,
                status=JobStatus.IN_PROGRESS,
            )
            job = self.queue.get_job(job.job_id)

        if job.current_stage == JobStage.EXECUTING:
            span_sub = self.tracer.start_span(trace_id, "submit_comment")
            post_id = job.pending_action.get("post_id")
            text = job.pending_action.get("comment_text")
            token = job.pending_action.get("approval_token")

            # Execute via verified safety harness
            proposal = ActionProposal(
                action_name="submit_comment",
                target_post_id=post_id,
                subreddit=job.input_snapshot.get("subreddit", "r/Python"),
                payload={"body": text},
                approval_token=token,
            )
            caps = set(DEFAULT_AGENT_CAPABILITIES) | {Capability.WRITE_COMMENT}
            ok, exec_res, v_rec = self.safety_harness.execute_verified_write(
                proposal, held_capabilities=caps
            )
            span_sub.finish()

            if not ok:
                self.metrics.comments_blocked_total += 1
                self.queue.complete_job(
                    job_id=job.job_id,
                    worker_id=self.worker_id,
                    final_status=JobStatus.FAILED,
                    result={"error": "SafetyVerificationFailed", "violations": v_rec.violations},
                )
                return

            span_ver = self.tracer.start_span(trace_id, "verify_comment")
            span_ver.finish()

            self.metrics.comments_submitted_total += 1
            self.metrics.agent_runs_success_total += 1

            self.queue.complete_job(
                job_id=job.job_id,
                worker_id=self.worker_id,
                final_status=JobStatus.SUCCEEDED,
                result={
                    "status": "success",
                    "comment_id": exec_res.get("comment_id"),
                    "post_id": post_id,
                },
            )
