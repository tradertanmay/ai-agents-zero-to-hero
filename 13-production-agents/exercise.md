# Exercise: Incident Triage & Graceful Worker Shutdown

## Objective
Investigate a real-world telemetry incident (`INC-REDDIT-LATENCY-402`) and implement an automated **Graceful Worker Shutdown (SIGTERM)** workflow with durable checkpointing.

---

## Scenario Part 1: Incident Root-Cause Analysis

Your team receives a PagerDuty alert:
```text
ALERT: Agent task success rate dropped from 86% to 61% over the past 30 minutes!
```

A junior developer suspects the prompt formatting changed and creates a pull request to rewrite the system prompt.

### Your Task:
1. Examine the JSONL log stream and trace waterfalls generated in `13-production-agents/example.py`.
2. Find the metrics counter responsible for the drop (`tool_errors_total` on `read_comments` due to HTTP 504 timeouts).
3. Formulate the correct production remedy: adjust retry backoff and timeout parameters in `AgentConfig` without touching the model prompts.

---

## Scenario Part 2: Graceful Worker Drain (SIGTERM Handling)

In a containerized environment (Kubernetes, AWS ECS), deployment rolling updates send a `SIGTERM` signal to existing worker pods. If a worker is abruptly killed midway through `submit_comment()`, it leaves behind an orphaned lease and creates a risk of ghost writes.

### Requirements:
1. In `worker.py`, implement `request_shutdown()`:
   - When `SIGTERM` or `SIGINT` is received, set `self.shutdown_requested = True`.
   - Prevent the worker from claiming any new jobs from `DurableJobQueue`.
   - If an active job is in progress:
     - Allow the current atomic step to complete safely.
     - Persist the current stage as a durable checkpoint.
     - Call `queue.release_job(job_id, worker_id)` so the replacement worker can immediately claim the job without waiting for the 30-second lease to expire.
2. Verify that after release:
   - The job's `leased_by` is set to `NULL`.
   - `lease_expires_at` is set to `NULL`.
   - `status` remains `IN_PROGRESS` or `WAITING_FOR_APPROVAL`.

---

## Verification Test Checklist

Write tests in your test environment to verify:
1. [ ] Simulated `SIGTERM` signal cleanly sets `shutdown_requested = True`.
2. [ ] Worker completes the active step and persists the current checkpoint before exiting.
3. [ ] Worker releases the lease in SQLite (`leased_by IS NULL`).
4. [ ] Replacement worker (`Worker-Replacement`) can immediately claim and resume the job without waiting for lease expiry.
5. [ ] No duplicate comments or lost jobs occur throughout the rolling restart.
