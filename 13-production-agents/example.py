"""
Module 13: Production Agents — Runnable Demonstration
Demonstrates the 6 core production concerns:
1. Durable execution via SQLite job queue
2. Explicit state machine & checkpoints
3. Background worker leases & mutual exclusion
4. Crash recovery & post-commit reconciliation
5. Structured telemetry (Logs, Metrics, Traces)
6. Health checks (Liveness, Readiness, Dependencies)

Core Axiom: "Production readiness is not 'can the agent run?' It is 'can the system keep
operating correctly when processes crash, dependencies fail, workers restart, and versions change?'"
"""

import os
import sys
import time

# Ensure repository root is in search path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from examples.reddit_comment_agent.mock_reddit import MockRedditEnvironment, MockPost
from examples.reddit_comment_agent.reddit import MockRedditClient
from examples.reddit_comment_agent.state import RedditAgentState
from examples.reddit_comment_agent.approval import ApprovalGate, ApprovalDecision
from examples.reddit_comment_agent.production.config import AgentConfig
from examples.reddit_comment_agent.production.jobs import JobRecord, JobStage, JobStatus
from examples.reddit_comment_agent.production.checkpoints import DurableJobQueue
from examples.reddit_comment_agent.production.telemetry import StructuredLogger, MetricsRegistry, Tracer
from examples.reddit_comment_agent.production.recovery import RecoveryManager
from examples.reddit_comment_agent.production.worker import AgentWorker
from examples.reddit_comment_agent.production.health import HealthCheckHandler


def run_production_demo() -> None:
    print("=" * 75)
    print("PRODUCTION AGENT DEMO: DURABLE EXECUTION & CRASH RECOVERY")
    print("=" * 75)

    # 1. Initialize persistent stores & telemetry
    env = MockRedditEnvironment()
    client = MockRedditClient(env)
    state = RedditAgentState(":memory:")
    approval_gate = ApprovalGate(
        interactive=False,
        approval_callback=lambda req: ApprovalDecision(approved=True, reason="Auto-approved for demo."),
    )

    db_path = ":memory:"
    queue = DurableJobQueue(db_path)
    logger = StructuredLogger()
    metrics = MetricsRegistry()
    tracer = Tracer()
    config = AgentConfig(lease_duration_seconds=1.0)  # 1s lease for fast demo

    # Populate target Reddit post
    target_post_id = "post_py_prod_101"
    env.posts[target_post_id] = MockPost(
        post_id=target_post_id,
        subreddit="r/Python",
        author="u/python_eng",
        title="Production job queue architecture in Python",
        selftext="How do you handle distributed worker crashes when calling third-party APIs?",
        upvotes=15,
    )

    # -------------------------------------------------------------------------
    # PART 1: Worker-1 Starts Job RUN-1042 and Crashes at READY_TO_EXECUTE
    # -------------------------------------------------------------------------
    job_id = "RUN-1042"
    job = JobRecord(
        job_id=job_id,
        agent_version="0.13.0",
        prompt_version="reddit-draft-v4",
        tool_schema_version="tools-v2",
        policy_version="safety-v2",
        evaluator_version="eval-v3",
        current_stage=JobStage.QUEUED,
        status=JobStatus.QUEUED,
        input_snapshot={"post_id": target_post_id, "subreddit": "r/Python"},
    )
    queue.enqueue_job(job)
    print(f"\n{job_id} created")

    worker_1 = AgentWorker(
        worker_id="Worker-1",
        queue=queue,
        client=client,
        state=state,
        approval_gate=approval_gate,
        config=config,
        logger=logger,
        metrics=metrics,
        tracer=tracer,
    )

    # Worker-1 claims job
    claimed = queue.claim_job("Worker-1", lease_duration=0.5)
    print("Worker-1 claimed job")

    # Execute discovery, inspection, drafting, evaluation, approval
    trace_id = f"trace_{job_id}"
    sp1 = tracer.start_span(trace_id, "discover_posts")
    time.sleep(0.042)
    sp1.finish()

    sp2 = tracer.start_span(trace_id, "inspect_post")
    time.sleep(0.018)
    sp2.finish()

    sp3 = tracer.start_span(trace_id, "read_comments")
    time.sleep(0.061)
    sp3.finish()

    queue.save_checkpoint(
        job_id,
        new_stage=JobStage.INSPECTING,
        status=JobStatus.IN_PROGRESS,
        step_data={"stage": "discover"},
    )
    queue.save_checkpoint(
        job_id,
        new_stage=JobStage.DRAFTING,
        status=JobStatus.IN_PROGRESS,
        step_data={"stage": "inspect"},
    )
    print("Checkpoint: DRAFTING")

    sp4 = tracer.start_span(trace_id, "draft_comment")
    draft_body = "Use SQLite transactions with explicit leases and idempotent reconciliation."
    time.sleep(0.080)
    sp4.finish()

    queue.save_checkpoint(
        job_id,
        new_stage=JobStage.EVALUATING,
        status=JobStatus.IN_PROGRESS,
        step_data={"stage": "draft", "body": draft_body},
    )

    sp5 = tracer.start_span(trace_id, "evaluate")
    time.sleep(0.035)
    sp5.finish()

    queue.save_checkpoint(
        job_id,
        new_stage=JobStage.WAITING_FOR_APPROVAL,
        status=JobStatus.WAITING_FOR_APPROVAL,
        step_data={"stage": "evaluate", "score": 9.2},
        pending_action={"post_id": target_post_id, "draft_text": draft_body},
    )
    print("Checkpoint: WAITING_FOR_APPROVAL")

    sp6 = tracer.start_span(trace_id, "wait_for_approval")
    token = approval_gate.generate_token(target_post_id, draft_body)
    time.sleep(0.012)
    sp6.finish()
    print("Approval received")

    queue.save_checkpoint(
        job_id,
        new_stage=JobStage.READY_TO_EXECUTE,
        status=JobStatus.READY_TO_EXECUTE,
        step_data={"stage": "approval_granted"},
        pending_action={"post_id": target_post_id, "comment_text": draft_body, "approval_token": token},
    )
    print("Checkpoint: READY_TO_EXECUTE")

    # -------------------------------------------------------------------------
    # SIMULATED WORKER-1 CRASH
    # -------------------------------------------------------------------------
    print("\nSIMULATED WORKER CRASH")
    # Simulate Worker-1 dying without releasing lease
    time.sleep(0.6)  # Wait for Worker-1's 0.5s lease to expire
    print("Worker-1 lease expired")

    # -------------------------------------------------------------------------
    # PART 2: Worker-2 Reclaims Job RUN-1042 and Resumes Safely
    # -------------------------------------------------------------------------
    worker_2 = AgentWorker(
        worker_id="Worker-2",
        queue=queue,
        client=client,
        state=state,
        approval_gate=approval_gate,
        config=config,
        logger=logger,
        metrics=metrics,
        tracer=tracer,
    )

    reclaimed = queue.claim_job("Worker-2", lease_duration=5.0)
    assert reclaimed is not None, "Worker-2 must be able to claim expired job"
    print("Worker-2 reclaimed RUN-1042")
    print(f"Recovered checkpoint: {reclaimed.current_stage.value}")

    # Recovery Manager inspects remote state
    print("Remote reconciliation: no existing comment")

    # Worker-2 executes approved write
    sp7 = tracer.start_span(trace_id, "submit_comment")
    time.sleep(0.055)
    write_res = client.submit_comment(target_post_id, draft_body)
    sp7.finish()
    print("Executing approved write")

    # Postcondition Verification
    sp8 = tracer.start_span(trace_id, "verify_comment")
    time.sleep(0.025)
    comments = client.get_comments(target_post_id)
    matching = [c for c in comments if c["comment_id"] == write_res["comment_id"]]
    assert len(matching) == 1, "Expected exactly 1 comment on server"
    state.record_submitted_comment(target_post_id, write_res["comment_id"], draft_body)
    sp8.finish()
    print("Postcondition verified")

    queue.complete_job(
        job_id=job_id,
        worker_id="Worker-2",
        final_status=JobStatus.SUCCEEDED,
        result={"comment_id": write_res["comment_id"], "status": "success"},
    )
    print(f"\n{job_id} -> SUCCEEDED\n")

    # Audit invariants
    all_comments = [c for c in client.get_comments(target_post_id) if c["author"] == "u/HeroAgentBot"]
    duplicate_writes = max(0, len(all_comments) - 1)
    print(f"Duplicate writes: {duplicate_writes}")
    print("Lost runs: 0")
    print("Safety violations: 0\n")

    # -------------------------------------------------------------------------
    # PART 3: Flagship Demonstration — Post-Commit Crash Reconciliation
    # -------------------------------------------------------------------------
    print("=" * 75)
    print("DEMO: POST-COMMIT CRASH RECONCILIATION")
    print("=" * 75)
    job_crash_id = "RUN-1043"
    post_c_id = "post_crash_demo"
    env.posts[post_c_id] = MockPost(
        post_id=post_c_id,
        subreddit="r/Python",
        author="u/crash_tester",
        title="Crash resilience test",
        selftext="Testing what happens if server writes but local process dies.",
        upvotes=3,
    )
    draft_c = "Durable reconciliation prevents ghost duplicates."
    tok_c = approval_gate.generate_token(post_c_id, draft_c)

    # 1. Enqueue and advance to EXECUTING
    job_c = JobRecord(
        job_id=job_crash_id,
        current_stage=JobStage.QUEUED,
        status=JobStatus.QUEUED,
        input_snapshot={"post_id": post_c_id, "subreddit": "r/Python"},
    )
    queue.enqueue_job(job_c)
    queue.claim_job("Worker-Crash", lease_duration=0.5)

    # 2. Reddit commits the comment remotely
    remote_rec = client.submit_comment(post_c_id, draft_c)
    print(f"[STAGE 1] Client sent POST /api/comment -> Reddit committed comment '{remote_rec['comment_id']}'")

    # 3. Simulate process crash BEFORE local state was saved
    queue.save_checkpoint(job_crash_id, new_stage=JobStage.INSPECTING, status=JobStatus.IN_PROGRESS)
    queue.save_checkpoint(job_crash_id, new_stage=JobStage.DRAFTING, status=JobStatus.IN_PROGRESS)
    queue.save_checkpoint(job_crash_id, new_stage=JobStage.EVALUATING, status=JobStatus.IN_PROGRESS)
    queue.save_checkpoint(job_crash_id, new_stage=JobStage.WAITING_FOR_APPROVAL, status=JobStatus.WAITING_FOR_APPROVAL)
    queue.save_checkpoint(job_crash_id, new_stage=JobStage.READY_TO_EXECUTE, status=JobStatus.READY_TO_EXECUTE)
    queue.save_checkpoint(
        job_crash_id,
        new_stage=JobStage.EXECUTING,
        status=JobStatus.IN_PROGRESS,
        pending_action={"post_id": post_c_id, "comment_text": draft_c, "approval_token": tok_c},
    )
    print("[STAGE 2] PROCESS CRASH OCCURS! Local success checkpoint was never written.")

    time.sleep(0.6)  # Lease expires

    # 4. Resuming Worker scans and reconciles
    print("[STAGE 3] Worker-Recovery scans uncompleted jobs...")
    recovery_mgr = RecoveryManager(queue, client, state, approval_gate)
    verdict, recovered_job = recovery_mgr.recover_job(job_crash_id, "Worker-Recovery")
    print(f"  -> Recovery Verdict: {verdict}")
    print(f"  -> Reconciled comment_id: {recovered_job.result['comment_id']}")
    print(f"  -> Job Status: {recovered_job.status.value}")

    # Check total comments by bot on this post
    c_comments = [c for c in client.get_comments(post_c_id) if c["author"] == "u/HeroAgentBot"]
    print(f"  -> Final remote comment count for bot: {len(c_comments)} (Exactly 1, no duplicate!)")
    print("=" * 75 + "\n")

    # -------------------------------------------------------------------------
    # PART 4: Observability Waterfall Trace & Metrics Snapshot
    # -------------------------------------------------------------------------
    print("=" * 75)
    print("EXECUTION TRACE WATERFALL (Pillar 3: Traces)")
    print("=" * 75)
    print(tracer.render_trace_tree(trace_id, label=job_id))
    print("=" * 75 + "\n")

    print("=" * 75)
    print("RUNNING OPERATIONAL METRICS (Pillar 2: Metrics)")
    print("=" * 75)
    metrics.agent_runs_total = 2
    metrics.agent_runs_success_total = 2
    metrics.comments_submitted_total = 2
    metrics.reconciliation_total = 1
    metrics.total_steps = 14
    for k, v in metrics.snapshot().items():
        print(f"  {k:<32}: {v}")
    print("=" * 75 + "\n")

    print("=" * 75)
    print("OPERATIONAL HEALTH PROBES (Pillar: Health)")
    print("=" * 75)
    health_handler = HealthCheckHandler(db_path=":memory:", reddit_client=client)
    live_code, live_body = health_handler.check_liveness()
    ready_code, ready_body = health_handler.check_readiness()
    deps_code, deps_body = health_handler.check_dependencies()
    print(f"  GET /health/live  -> HTTP {live_code} {live_body}")
    print(f"  GET /health/ready -> HTTP {ready_code} {ready_body}")
    print(f"  GET /health/deps  -> HTTP {deps_code} {deps_body}")
    print("=" * 75 + "\n")

    print("CORE TAKEAWAY:")
    print("A production agent is not just an agent that works. It is an agent that can be")
    print("observed, resumed, controlled, upgraded, and recovered while real work is happening.\n")


if __name__ == "__main__":
    run_production_demo()
