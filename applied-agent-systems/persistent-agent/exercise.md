# A2 — Persistent Agent: Hands-On Engineering Exercises

These exercises challenge you to extend the GitHub Steward Persistent Agent with production-grade reliability, failure isolation, and operational defenses.

---

## Exercise 1: Webhook Jitter & Thundering Herd Protection

### Context
In high-activity open-source repositories, a sudden burst of events (e.g., automated Dependabot PRs or issue bot updates) can dispatch dozens of webhook events simultaneously. If your agent reactivates instantly on each webhook, it can exhaust GitHub API rate limits or trigger database lock contention in SQLite.

### Requirements
1. Modify the `WakeScheduler` or `EventBus` to implement a debounce/batching window (e.g., 5 seconds).
2. When multiple events arrive within the window, aggregate them into a single wake event containing a list of target entity IDs rather than waking the agent once per event.
3. Add randomized jitter (`random.uniform(0.5, 2.0)`) to the scheduled reactivation time to ensure multiple running agent workers do not wake simultaneously.

### Acceptance Criteria
- 10 incoming webhook events arriving within 2 seconds result in exactly 1 wake cycle.
- The wake payload contains all 10 entity references.
- All 10 entities are observed and triaged in a single pass.

---

## Exercise 2: Dead-Letter Queue (DLQ) for Poison Pill Events

### Context
An external contributor opens an issue with malformed markdown, unhandled characters, or huge payloads that crash your parser during the `OBSERVING` or `DECIDING` phase. Without a poison pill defense, the agent will repeatedly wake, crash on the same issue, and enter an infinite failure loop.

### Requirements
1. Create a `dead_letter_events` SQLite table:
   ```sql
   CREATE TABLE dead_letter_events (
       event_id TEXT PRIMARY KEY,
       agent_id TEXT NOT NULL,
       event_name TEXT NOT NULL,
       payload_json TEXT NOT NULL,
       failure_reason TEXT NOT NULL,
       failed_at TEXT NOT NULL
   );
   ```
2. In `agent.py`, track failures per entity ID. If a specific event or entity triggers 3 consecutive exceptions during parsing or decision-making:
   - Quarantine the event into `dead_letter_events`.
   - Log an audit event: `POISON_PILL_QUARANTINED`.
   - Remove the event from the active processing queue.
   - Continue processing remaining healthy events.

### Acceptance Criteria
- When an issue raises `ValueError("Malformed entity")`, the agent retries up to 3 times with exponential backoff.
- On the 3rd failure, the issue is written to `dead_letter_events`.
- On the 4th wake, the agent skips the quarantined issue and safely processes subsequent valid issues.

---

## Exercise 3: TTL-Based Commitment Escalation & Expiration

### Context
An agent creates a commitment to review a pull request, but the human maintainer neither approves nor rejects the approval request within 72 hours. An unmanaged commitment remains `OPEN` or `IN_PROGRESS` indefinitely, cluttering working state.

### Requirements
1. Implement a commitment expiration audit sweep in `memory.compact()`.
2. If `datetime.now(timezone.utc) > commitment.due_date` and status is still `IN_PROGRESS`:
   - Transition status to `ABANDONED`.
   - Record reason: `"Maintainer approval SLA timed out after 72 hours."`
   - Dispatch an escalation notification (e.g., log event `COMMITMENT_TIMED_OUT`).
   - Move the abandoned commitment to `long_term_summary` during compaction.

### Acceptance Criteria
- Commitments past their `due_date` automatically transition out of `IN_PROGRESS`.
- The audit log records the abandonment with timestamps.
- The agent does not attempt to execute expired commitments.

---

## Exercise 4: Stale-Action Dynamic Re-Evaluation

### Context
An agent proposed closing an inactive issue #55, and generated an approval request. During the 12 hours before the maintainer clicks "Approve", the original author posts a comment: `"Wait, here is the reproduction script!"`
The approval token is now stale.

### Requirements
1. In `approval.py`, enhance `validate_for_execution` to verify not only whether the issue is still open, but whether `comment_count` has changed since the approval request was created.
2. If `live_comment_count != expected_comment_count`:
   - Reject execution with reason: `"Target entity modified by user during approval window."`
   - Revert the commitment to `OPEN`.
   - Force a re-observation cycle to inspect the author's new comment.

### Acceptance Criteria
- New comments added to an issue while an approval is pending invalidate the approval token.
- The agent safely abstains from executing the stale closure.
- The agent schedules a re-observation cycle.
