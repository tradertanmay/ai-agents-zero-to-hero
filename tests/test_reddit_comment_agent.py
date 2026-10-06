"""
Tests for Capstone Project: Reddit Comment Agent (Modules 01-09)
"""

import unittest
import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from examples.reddit_comment_agent.mock_reddit import MockRedditEnvironment
from examples.reddit_comment_agent.reddit import MockRedditClient
from examples.reddit_comment_agent.state import RedditAgentState
from examples.reddit_comment_agent.evaluator import CommentEvaluator
from examples.reddit_comment_agent.approval import ApprovalGate, ApprovalDecision
from examples.reddit_comment_agent.tools import RedditToolRegistry
from examples.reddit_comment_agent.runtime import AgentRuntime, RuntimeBudget
from examples.reddit_comment_agent.agent import RedditCommentAgent


class TestRedditCommentAgent(unittest.TestCase):
    def setUp(self):
        self.mock_env = MockRedditEnvironment()
        self.client = MockRedditClient(self.mock_env)
        self.state = RedditAgentState(":memory:")
        self.evaluator = CommentEvaluator()
        
        # Test approval gate with programmable callback
        self.approval_gate = ApprovalGate(
            interactive=False,
            approval_callback=lambda req: ApprovalDecision(
                approved=True,
                reason="Test runner auto-approved.",
            ),
        )
        self.runtime = AgentRuntime(RuntimeBudget(max_steps_per_post=8, max_daily_comments=5))
        self.agent = RedditCommentAgent(
            client=self.client,
            state=self.state,
            evaluator=self.evaluator,
            approval_gate=self.approval_gate,
            runtime=self.runtime,
        )

    def tearDown(self):
        self.state.close()

    def test_mock_reddit_client(self):
        posts = self.client.list_posts("r/Python", limit=10)
        self.assertEqual(len(posts), 3)

        post = self.client.get_post("post_py_101")
        self.assertIsNotNone(post)
        self.assertEqual(post["subreddit"], "r/Python")

        comments = self.client.get_comments("post_py_101")
        self.assertEqual(len(comments), 1)

        rules = self.client.get_subreddit_rules("r/Python")
        self.assertTrue(len(rules) >= 3)

    def test_state_persistence_and_duplicate_prevention(self):
        self.assertFalse(self.state.is_post_seen("p1"))
        self.state.mark_post_seen("p1", "r/Python", "Title 1", "u/author1")
        self.assertTrue(self.state.is_post_seen("p1"))
        self.assertEqual(self.state.get_seen_count(), 1)

        self.assertFalse(self.state.has_commented("p1"))
        self.state.record_submitted_comment("p1", "c1", "Helpful comment")
        self.assertTrue(self.state.has_commented("p1"))
        self.assertEqual(self.state.get_commented_count(), 1)

    def test_evaluator_scorecard_passing_and_failing(self):
        post = {"post_id": "p1", "title": "Safe nested dict query in Python?", "selftext": "How to get nested dict keys?"}
        rules = ["Rule 1: Format code in code blocks."]
        existing = []

        # High-quality comment
        good_comment = (
            "You can use functools.reduce with a safe lookup helper:\n\n"
            "```python\ndef safe_get(d, *keys):\n    pass\n```\n\n"
            "This handles missing keys cleanly and idiomatically."
        )
        res_good = self.evaluator.evaluate(post, rules, existing, good_comment)
        self.assertTrue(res_good.passed)
        self.assertGreaterEqual(res_good.total_score, 7.0)

        # Spam comment
        spam_comment = "Guaranteed 10,000% returns! Download now and join telegram!"
        res_spam = self.evaluator.evaluate(post, rules, existing, spam_comment)
        self.assertFalse(res_spam.passed)
        self.assertEqual(res_spam.criteria[1].score, 0.0)  # rule_compliance failed

    def test_approval_gate_hmac_verification(self):
        gate = ApprovalGate(secret_key="unit_test_key")
        token = gate.generate_token("post_123", "Approved text")
        
        # Exact match succeeds on first use
        valid, msg = gate.verify_and_consume_token("post_123", "Approved text", token)
        self.assertTrue(valid)
        self.assertIn("verified", msg.lower())
        
        # Second use with same token fails (replay prevention)
        valid_again, msg_again = gate.verify_and_consume_token("post_123", "Approved text", token)
        self.assertFalse(valid_again)
        self.assertIn("TokenReplayError", msg_again)

        # Fresh token with tampered text fails
        token2 = gate.generate_token("post_123", "Original text")
        valid_tampered, msg_tampered = gate.verify_and_consume_token("post_123", "Tampered text", token2)
        self.assertFalse(valid_tampered)
        self.assertIn("TextTamperError", msg_tampered)

        # Fresh token with expired TTL fails
        token_expired = gate.generate_token("post_123", "Expired text", ttl_seconds=-1.0)
        valid_expired, msg_expired = gate.verify_and_consume_token("post_123", "Expired text", token_expired)
        self.assertFalse(valid_expired)
        self.assertIn("TokenExpiredError", msg_expired)

    def test_tool_registry_permission_gate(self):
        tools = RedditToolRegistry(self.client, self.state, self.approval_gate)

        # Attempt submit_comment without valid token
        res_invalid = tools.execute(
            "submit_comment",
            {"post_id": "post_py_101", "comment_text": "Unauthorized text", "approval_token": "fake_token"},
        )
        self.assertEqual(res_invalid["status"], "error")
        self.assertIn("PermissionDeniedError", res_invalid["error"])

        # Generate valid token and submit
        valid_token = self.approval_gate.generate_token("post_py_101", "Authorized text")
        res_valid = tools.execute(
            "submit_comment",
            {"post_id": "post_py_101", "comment_text": "Authorized text", "approval_token": valid_token},
        )
        self.assertEqual(res_valid["status"], "success")
        self.assertIn("comment_id", res_valid)

        # Attempt duplicate comment
        res_dup = tools.execute(
            "submit_comment",
            {"post_id": "post_py_101", "comment_text": "Authorized text", "approval_token": valid_token},
        )
        self.assertEqual(res_dup["status"], "error")
        self.assertIn("DuplicateCommentError", res_dup["error"])

    def test_agent_contribution_filtering(self):
        # 1. Technical post -> should contribute
        post_good = self.client.get_post("post_py_101")
        can_help, _ = self.agent.should_contribute(post_good, [])
        self.assertTrue(can_help)

        # 2. Spam post -> should skip
        post_spam = self.client.get_post("post_py_102")
        can_help_spam, reason_spam = self.agent.should_contribute(post_spam, [])
        self.assertFalse(can_help_spam)
        self.assertIn("promotional marketing or spam", reason_spam)

        # 3. Solved post -> should skip
        post_solved = self.client.get_post("post_py_103")
        can_help_solved, reason_solved = self.agent.should_contribute(post_solved, [])
        self.assertFalse(can_help_solved)
        self.assertIn("comprehensively answered", reason_solved)

    def test_agent_end_to_end_lifecycle(self):
        # Pass 1: Process all posts
        outcomes = self.agent.run_on_subreddit("r/Python", limit=5)
        self.assertEqual(len(outcomes), 3)

        # Post 1 was published
        self.assertEqual(outcomes[0]["status"], "published")
        # Post 2 was skipped (spam)
        self.assertEqual(outcomes[1]["status"], "skipped")
        # Post 3 was skipped (already answered)
        self.assertEqual(outcomes[2]["status"], "skipped")

        # Pass 2: Verify duplicate prevention on rescanning
        outcomes_pass2 = self.agent.run_on_subreddit("r/Python", limit=5)
        self.assertEqual(outcomes_pass2[0]["status"], "skipped")
        self.assertIn("Already commented", outcomes_pass2[0]["reason"])

    def test_human_rejection_halts_submission(self):
        # Configure approval gate to simulate human REJECTION
        rejecting_gate = ApprovalGate(
            interactive=False,
            approval_callback=lambda req: ApprovalDecision(
                approved=False,
                reason="Operator rejected: comment does not fit tone.",
            ),
        )
        agent = RedditCommentAgent(
            client=self.client,
            state=self.state,
            evaluator=self.evaluator,
            approval_gate=rejecting_gate,
            runtime=self.runtime,
        )

        post = self.client.get_post("post_py_101")
        outcome = agent.process_post(post)
        
        self.assertEqual(outcome["status"], "rejected_by_human")
        self.assertIn("Operator rejected", outcome["reason"])
        # Verify no comment was published
        self.assertFalse(self.state.has_commented("post_py_101"))


if __name__ == "__main__":
    unittest.main()
