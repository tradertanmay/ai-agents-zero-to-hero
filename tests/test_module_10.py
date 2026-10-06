"""
Tests for Module 10: Agent Failures and Defensive Resilience
"""

import unittest
import os
import sys
import importlib.util

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

spec = importlib.util.spec_from_file_location("module_10_example", os.path.join(root_dir, "10-agent-failures", "example.py"))
m10 = importlib.util.module_from_spec(spec)
sys.modules["module_10_example"] = m10
spec.loader.exec_module(m10)

from examples.reddit_comment_agent.mock_reddit import MockRedditEnvironment
from examples.reddit_comment_agent.state import RedditAgentState
from examples.reddit_comment_agent.approval import ApprovalGate, ApprovalDecision
from examples.reddit_comment_agent.runtime import AgentRuntime, RuntimeBudget


class TestModule10(unittest.TestCase):
    def setUp(self):
        self.mock_env = MockRedditEnvironment()
        self.client = m10.FaultInjectingRedditClient(self.mock_env)
        self.state = RedditAgentState(":memory:")
        self.approval_gate = ApprovalGate(
            interactive=False,
            approval_callback=lambda req: ApprovalDecision(approved=True, reason="Auto-approved for test.")
        )
        self.runtime = AgentRuntime(RuntimeBudget(max_steps_per_post=8))
        self.agent = m10.ResilientRedditAgent(
            client=self.client,
            state=self.state,
            approval_gate=self.approval_gate,
            runtime=self.runtime,
            max_retries=2,
        )

    def tearDown(self):
        self.state.close()

    def test_ambiguous_write_timeout_reconciles_successfully(self):
        """
        The Core Axiom Test:
        Network drops during POST, but Reddit committed the comment.
        Agent reconciles remote state, marks reconciled=True, and does NOT double-post!
        """
        self.client.set_fault("AMBIGUOUS_WRITE_TIMEOUT")
        post = self.client.get_post("post_py_101")
        draft = "Test comment for reconciliation verification."
        token = self.approval_gate.generate_token(post["post_id"], draft)

        success, result = self.agent.execute_resilient_comment(post["post_id"], post, draft, token)

        # Must succeed via reconciliation
        self.assertTrue(success)
        self.assertEqual(result, "c_gen_1")
        
        # Verify state recorded
        self.assertTrue(self.state.has_commented(post["post_id"]))

        # Check telemetry
        record = self.agent.failure_log[0]
        self.assertEqual(record.failure_type, "AMBIGUOUS")
        self.assertTrue(record.reconciled)
        self.assertEqual(record.final_outcome, "RECONCILED_SUCCESS")

        # Crucial check: Reddit comments count increased by EXACTLY 1 (no duplicate)
        comments = self.mock_env.get_comments(post["post_id"])
        matching = [c for c in comments if c["body"] == draft]
        self.assertEqual(len(matching), 1)

    def test_transient_rate_limit_recovers_after_backoff(self):
        """HTTP 429 rate limit backs off and succeeds on retry 2."""
        self.client.set_fault("RATE_LIMIT_429")
        post = self.client.get_post("post_py_101")
        draft = "Test comment for rate limit retry."
        token = self.approval_gate.generate_token(post["post_id"], draft)

        success, result = self.agent.execute_resilient_comment(post["post_id"], post, draft, token)

        self.assertTrue(success)
        self.assertEqual(result, "c_gen_1")
        
        # Verify telemetry recorded transient failure
        record = self.agent.failure_log[0]
        self.assertEqual(record.failure_type, "TRANSIENT")
        self.assertTrue(record.retryable)
        self.assertEqual(record.final_outcome, "RECOVERED")

    def test_semantic_content_drift_invalidates_draft(self):
        """If user edits post mid-flight, agent invalidates draft and aborts safely."""
        self.client.set_fault("POST_EDITED_MIDFLIGHT")
        post = self.client.get_post("post_py_101")
        draft = "Test comment for semantic drift."
        token = self.approval_gate.generate_token(post["post_id"], draft)

        success, result = self.agent.execute_resilient_comment(post["post_id"], post, draft, token)

        self.assertFalse(success)
        self.assertIn("content modified mid-flight", result)
        
        # Verify telemetry recorded semantic failure
        record = self.agent.failure_log[0]
        self.assertEqual(record.failure_type, "SEMANTIC")
        self.assertEqual(record.final_outcome, "ABORTED_SEMANTIC_DRIFT")
        self.assertFalse(self.state.has_commented(post["post_id"]))

    def test_permanent_post_deleted_halts_without_retrying(self):
        """HTTP 404 deleted post immediately halts without retrying."""
        # Grab initial post before deleting
        post = self.mock_env.get_post("post_py_101")
        self.client.set_fault("POST_DELETED_404")
        draft = "Test comment for deleted post."
        token = self.approval_gate.generate_token(post["post_id"], draft)

        success, result = self.agent.execute_resilient_comment(post["post_id"], post, draft, token)

        self.assertFalse(success)
        self.assertIn("Target post has been deleted", result)
        
        record = self.agent.failure_log[0]
        self.assertEqual(record.failure_type, "PERMANENT")
        self.assertFalse(record.retryable)
        self.assertEqual(record.final_outcome, "ABORTED_PERMANENT")

    def test_auth_token_expired_recovers_after_refresh(self):
        """HTTP 401 triggers credential refresh and succeeds on retry."""
        self.client.set_fault("AUTH_EXPIRED_401")
        self.client.token_valid = False
        post = self.client.get_post("post_py_101")
        draft = "Test comment for auth renewal."
        token = self.approval_gate.generate_token(post["post_id"], draft)

        success, result = self.agent.execute_resilient_comment(post["post_id"], post, draft, token)

        self.assertTrue(success)
        self.assertTrue(self.client.token_valid)
        self.assertEqual(self.agent.failure_log[0].failure_type, "TRANSIENT")

    def test_retry_budget_exhaustion(self):
        """Repeated persistent failures exhaust retry budget and halt."""
        # Force permanent error on submit_comment
        self.client.submit_comment = lambda post_id, body: {"status": "error", "error": "HTTP 429: Unlimited lock"}
        post = self.client.get_post("post_py_101")
        draft = "Test comment for budget exhaustion."
        token = self.approval_gate.generate_token(post["post_id"], draft)

        success, result = self.agent.execute_resilient_comment(post["post_id"], post, draft, token)

        self.assertFalse(success)
        self.assertIn("exhausting all retry", result)


if __name__ == "__main__":
    unittest.main()
