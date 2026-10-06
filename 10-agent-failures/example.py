"""
Module 10: Agent Failures
Runnable Python Demonstration: Failure Injection, Reconciliation, and Resilient Recovery

Demonstrates the 5 failure classes (Transient, Permanent, Ambiguous, Partial, Semantic)
and recovery strategies (Retry, Backoff, Re-observe, Reconcile, Abort) built directly
on top of the Reddit Comment Agent capstone.
"""

from dataclasses import dataclass, field
import hashlib
import os
import sys
import time
from typing import Any

# Ensure project root is in sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from examples.reddit_comment_agent.mock_reddit import MockRedditEnvironment
from examples.reddit_comment_agent.reddit import RedditClient
from examples.reddit_comment_agent.state import RedditAgentState
from examples.reddit_comment_agent.evaluator import CommentEvaluator
from examples.reddit_comment_agent.approval import ApprovalGate, ApprovalDecision
from examples.reddit_comment_agent.runtime import AgentRuntime, RuntimeBudget
from examples.reddit_comment_agent.agent import RedditCommentAgent


# ============================================================================
# 1. Structured Failure Telemetry Record
# ============================================================================

@dataclass
class FailureRecord:
    action: str
    attempt: int
    failure_type: str  # TRANSIENT, PERMANENT, AMBIGUOUS, PARTIAL, SEMANTIC
    error_message: str
    retryable: bool
    backoff_seconds: float
    reconciled: bool
    final_outcome: str  # RECOVERED, RECONCILED_SUCCESS, ABORTED_PERMANENT, EXHAUSTED


# ============================================================================
# 2. Deterministic Fault-Injecting Reddit Client
# ============================================================================

class FaultInjectingRedditClient(RedditClient):
    """
    Wraps the mock Reddit environment and injects controlled failure modes
    for testing agent resilience.
    """

    def __init__(self, env: MockRedditEnvironment | None = None) -> None:
        self.env = env or MockRedditEnvironment()
        self.active_fault: str | None = None
        self.call_counts: dict[str, int] = {}
        self.token_valid = True

    def set_fault(self, fault_name: str | None) -> None:
        self.active_fault = fault_name
        self.call_counts.clear()

    def _increment(self, operation: str) -> int:
        count = self.call_counts.get(operation, 0) + 1
        self.call_counts[operation] = count
        return count

    def get_subreddit_rules(self, subreddit: str) -> list[str]:
        return self.env.get_rules(subreddit)

    def list_posts(self, subreddit: str, limit: int = 5) -> list[dict[str, Any]]:
        return self.env.list_posts(subreddit, limit=limit)

    def get_post(self, post_id: str) -> dict[str, Any] | None:
        count = self._increment(f"get_post:{post_id}")

        # Fault: Post Deleted (Permanent Failure)
        if self.active_fault == "POST_DELETED_404":
            return None

        # Fault: Post Edited Mid-Flight (Semantic Drift)
        post = self.env.get_post(post_id)
        if post and self.active_fault == "POST_EDITED_MIDFLIGHT" and count > 1:
            # On second fetch, OP has completely changed the question
            edited = dict(post)
            edited["selftext"] = "NEVERMIND: I figured out the issue myself. Thread closed!"
            edited["title"] = "[SOLVED] What is the cleanest way to query nested dicts?"
            return edited

        return post

    def get_comments(self, post_id: str, limit: int = 3) -> list[dict[str, Any]]:
        count = self._increment(f"get_comments:{post_id}")

        # Fault: Transient Timeout on read
        if self.active_fault == "READ_TIMEOUT" and count == 1:
            raise TimeoutError("Network timeout: read_comments failed to respond within 2.0s.")

        return self.env.get_comments(post_id, limit=limit)

    def submit_comment(self, post_id: str, body: str) -> dict[str, Any]:
        count = self._increment(f"submit_comment:{post_id}")

        # Fault: Rate Limit (HTTP 429)
        if self.active_fault == "RATE_LIMIT_429" and count == 1:
            return {
                "status": "error",
                "error": "HTTP 429: Rate limit exceeded.",
                "retry_after": 0.05,
            }

        # Fault: Auth Expired (HTTP 401)
        if self.active_fault == "AUTH_EXPIRED_401" and not self.token_valid:
            return {
                "status": "error",
                "error": "HTTP 401: OAuth token expired.",
            }

        # Fault: Ambiguous Write Timeout (The Core Axiom!)
        # The remote server writes the comment successfully, but drops the response!
        if self.active_fault == "AMBIGUOUS_WRITE_TIMEOUT" and count == 1:
            # 1. Server actually creates the comment in the database!
            self.env.submit_comment(post_id, body)
            # 2. Connection drops before sending response back to agent
            raise TimeoutError("HTTP 504 Gateway Timeout during POST /api/comment.")

        return self.env.submit_comment(post_id, body)

    def refresh_auth_token(self) -> None:
        self.token_valid = True


# ============================================================================
# 3. Resilient Agent with Reconciliation and Defenses
# ============================================================================

class ResilientRedditAgent:
    """
    Extends the RedditCommentAgent with formal failure classification,
    idempotent reconciliation, rate-limit backoff, and semantic re-observation.
    """

    def __init__(
        self,
        client: FaultInjectingRedditClient,
        state: RedditAgentState,
        approval_gate: ApprovalGate,
        runtime: AgentRuntime,
        max_retries: int = 2,
    ) -> None:
        self.client = client
        self.state = state
        self.approval_gate = approval_gate
        self.runtime = runtime
        self.max_retries = max_retries
        self.evaluator = CommentEvaluator()
        self.failure_log: list[FailureRecord] = []

    def compute_post_hash(self, post: dict[str, Any]) -> str:
        content = f"{post.get('title', '')}:{post.get('selftext', '')}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def reconcile_comment(self, post_id: str, comment_text: str) -> tuple[bool, str | None]:
        """
        Queries the remote environment to verify if an ambiguous write
        actually committed before attempting any retry.
        """
        print(f"    [RECONCILER] Querying remote comment tree for post '{post_id}'...")
        comments = self.client.get_comments(post_id, limit=10)
        clean_text = comment_text.strip()
        for c in comments:
            if c.get("body", "").strip() == clean_text:
                print(f"    [RECONCILER SUCCESS] Found matching comment '{c.get('comment_id')}' already published!")
                return True, c.get("comment_id")
        return False, None

    def execute_resilient_comment(
        self,
        post_id: str,
        initial_post: dict[str, Any],
        draft: str,
        approval_token: str,
    ) -> tuple[bool, str]:
        """
        Executes comment submission with full failure classification,
        reconciliation on timeout, and semantic drift checks.
        """
        # Step 1: Semantic Drift Check (Re-observe before write)
        fresh_post = self.client.get_post(post_id)
        if not fresh_post:
            self.failure_log.append(FailureRecord(
                action="submit_comment",
                attempt=1,
                failure_type="PERMANENT",
                error_message="Post was deleted before comment submission.",
                retryable=False,
                backoff_seconds=0.0,
                reconciled=False,
                final_outcome="ABORTED_PERMANENT",
            ))
            return False, "Aborted: Target post has been deleted."

        initial_hash = self.compute_post_hash(initial_post)
        fresh_hash = self.compute_post_hash(fresh_post)
        if initial_hash != fresh_hash:
            print("    [SEMANTIC DEFENSE] Target post content was modified after drafting!")
            self.failure_log.append(FailureRecord(
                action="submit_comment",
                attempt=1,
                failure_type="SEMANTIC",
                error_message="Post selftext or title changed mid-flight (content drift).",
                retryable=False,
                backoff_seconds=0.0,
                reconciled=False,
                final_outcome="ABORTED_SEMANTIC_DRIFT",
            ))
            return False, "Aborted: Post content modified mid-flight. Draft invalidated."

        # Step 2: Attempt Submission with Reconciliation
        for attempt in range(1, self.max_retries + 2):
            try:
                print(f"    [ATTEMPT {attempt}] Dispatching submit_comment to Reddit...")
                res = self.client.submit_comment(post_id, draft)

                if res.get("status") == "error":
                    err = res.get("error", "Unknown error")
                    
                    # 1. Transient Rate Limit
                    if "429" in err:
                        retry_after = res.get("retry_after", 0.1)
                        print(f"    [TRANSIENT FAILURE] HTTP 429 Rate Limit. Backing off {retry_after}s...")
                        time.sleep(retry_after)
                        self.failure_log.append(FailureRecord(
                            action="submit_comment",
                            attempt=attempt,
                            failure_type="TRANSIENT",
                            error_message=err,
                            retryable=True,
                            backoff_seconds=retry_after,
                            reconciled=False,
                            final_outcome="RECOVERED" if attempt < self.max_retries + 1 else "EXHAUSTED",
                        ))
                        continue

                    # 2. Auth Expiration
                    if "401" in err:
                        print("    [AUTH FAILURE] HTTP 401 Token Expired. Refreshing credentials...")
                        self.client.refresh_auth_token()
                        self.failure_log.append(FailureRecord(
                            action="submit_comment",
                            attempt=attempt,
                            failure_type="TRANSIENT",
                            error_message=err,
                            retryable=True,
                            backoff_seconds=0.0,
                            reconciled=False,
                            final_outcome="RECOVERED",
                        ))
                        continue

                    # Other error
                    return False, f"Submission error: {err}"

                # Direct Success
                cid = res.get("comment_id", "c_unknown")
                self.state.record_submitted_comment(post_id, cid, draft)
                return True, cid

            except TimeoutError as te:
                # 3. Ambiguous Write Timeout! The Core Axiom!
                print(f"    [AMBIGUOUS FAILURE] Caught {type(te).__name__}: {te}")
                print("    [WARNING] Network timed out during write. DO NOT BLINDLY RETRY!")
                
                # Reconcile Remote State
                already_published, found_cid = self.reconcile_comment(post_id, draft)
                if already_published and found_cid:
                    print(f"    [RECONCILIATION COMPLETE] Action actually succeeded on server! comment_id={found_cid}")
                    self.state.record_submitted_comment(post_id, found_cid, draft)
                    self.failure_log.append(FailureRecord(
                        action="submit_comment",
                        attempt=attempt,
                        failure_type="AMBIGUOUS",
                        error_message=str(te),
                        retryable=False,
                        backoff_seconds=0.0,
                        reconciled=True,
                        final_outcome="RECONCILED_SUCCESS",
                    ))
                    return True, found_cid
                else:
                    # Genuinely didn't reach server, safe to retry if budget allows
                    print("    [RECONCILIATION RESULT] Comment not found on server. Safe to retry.")
                    self.failure_log.append(FailureRecord(
                        action="submit_comment",
                        attempt=attempt,
                        failure_type="AMBIGUOUS",
                        error_message=str(te),
                        retryable=True,
                        backoff_seconds=0.1,
                        reconciled=True,
                        final_outcome="RETRY_SCHEDULED",
                    ))
                    time.sleep(0.1)

        return False, "Failed after exhausting all retry and reconciliation attempts."


# ============================================================================
# 4. Demonstrations Across the Failure Matrix
# ============================================================================

def run_scenario(name: str, fault_name: str | None, simulate_change: bool = False) -> None:
    print("\n" + "=" * 65)
    print(f"SCENARIO DEMO: {name}")
    print("=" * 65)

    mock_env = MockRedditEnvironment()
    client = FaultInjectingRedditClient(mock_env)
    client.set_fault(fault_name)

    state = RedditAgentState(":memory:")
    approval_gate = ApprovalGate(
        interactive=False,
        approval_callback=lambda req: ApprovalDecision(approved=True, reason="Auto-approved for scenario test.")
    )
    runtime = AgentRuntime(RuntimeBudget(max_steps_per_post=8))

    agent = ResilientRedditAgent(
        client=client,
        state=state,
        approval_gate=approval_gate,
        runtime=runtime,
        max_retries=2,
    )

    post = client.get_post("post_py_101")
    if not post:
        print("Initial post fetch failed (404 / Deleted).")
        return

    draft = (
        "Use `functools.reduce` for clean nested dictionary lookups:\n\n"
        "```python\nfrom functools import reduce\ndef safe_get(d, *keys, default=None):\n    pass\n```"
    )
    token = approval_gate.generate_token(post["post_id"], draft)

    success, result = agent.execute_resilient_comment(post["post_id"], post, draft, token)

    print(f"\nResult: Success={success} | Details={result}")
    print("Recorded Failure Telemetry:")
    for f in agent.failure_log:
        print(f"  - [{f.failure_type:<10}] Attempt={f.attempt} Reconciled={f.reconciled:<5} Outcome={f.final_outcome}")
        print(f"    Error: {f.error_message}")


def main() -> None:
    print("=" * 65)
    print("MODULE 10: AGENT FAILURE INJECTION & RECONCILIATION HARNESS")
    print("=" * 65)

    # Scenario A: The Core Axiom (Ambiguous Write Timeout -> Reconciled Success)
    run_scenario(
        name="Ambiguous Write Timeout with Idempotent Reconciliation",
        fault_name="AMBIGUOUS_WRITE_TIMEOUT",
    )

    # Scenario B: Transient Rate Limit (HTTP 429) -> Backoff & Recovery
    run_scenario(
        name="Transient HTTP 429 Rate Limit with Backoff Retry",
        fault_name="RATE_LIMIT_429",
    )

    # Scenario C: Semantic Drift (Post Edited by OP Mid-Draft) -> Draft Invalidation
    run_scenario(
        name="Semantic Content Drift (Post Modified Mid-Flight)",
        fault_name="POST_EDITED_MIDFLIGHT",
    )

    # Scenario D: Permanent Failure (Post Deleted / 404) -> Immediate Abort
    run_scenario(
        name="Permanent HTTP 404 (Post Deleted Mid-Flight)",
        fault_name="POST_DELETED_404",
    )

    print("\n" + "=" * 65)
    print("ALL MODULE 10 FAILURE DEMONSTRATIONS COMPLETED")
    print("=" * 65)


if __name__ == "__main__":
    main()
