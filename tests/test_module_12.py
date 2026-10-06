"""
Tests for Module 12: Agent Safety and Verification
Verifies capability gating, blast radius limits, precondition and postcondition
verifiers, fail-closed mechanics, and compensation workflows.
"""

import hashlib
import os
import sys
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from examples.reddit_comment_agent.mock_reddit import MockRedditEnvironment, MockPost
from examples.reddit_comment_agent.reddit import MockRedditClient
from examples.reddit_comment_agent.state import RedditAgentState
from examples.reddit_comment_agent.approval import ApprovalGate
from examples.reddit_comment_agent.safety import (
    Capability,
    SafetyPolicy,
    ActionProposal,
    SafetyVerificationHarness,
    BlastRadiusLimiter,
    PreconditionVerifier,
    PostconditionVerifier,
    CompensationManager,
    DEFAULT_AGENT_CAPABILITIES,
)


class TestModule12(unittest.TestCase):
    def setUp(self):
        self.env = MockRedditEnvironment()
        self.client = MockRedditClient(self.env)
        self.state = RedditAgentState(":memory:")
        self.approval_gate = ApprovalGate(interactive=False)
        self.policy = SafetyPolicy(
            allowed_subreddits={"r/Python", "r/MachineLearning", "r/AI_Agents"},
            max_comments_per_run=2,
            max_comments_per_subreddit_per_day=3,
        )
        self.harness = SafetyVerificationHarness(
            client=self.client,
            state=self.state,
            approval_gate=self.approval_gate,
            policy=self.policy,
        )

        # Standard test post
        self.post_id = "test_post_001"
        self.title = "Standard Library Tips"
        self.body = "Discussion on Python standard library."
        self.env.posts[self.post_id] = MockPost(
            post_id=self.post_id,
            subreddit="r/Python",
            author="u/pythonista",
            title=self.title,
            selftext=self.body,
            upvotes=5,
        )
        self.post_hash = hashlib.sha256(f"{self.title}\n{self.body}".encode("utf-8")).hexdigest()
        self.caps_with_write = set(DEFAULT_AGENT_CAPABILITIES) | {Capability.WRITE_COMMENT}

    def tearDown(self):
        self.state.close()

    def test_least_privilege_blocks_unauthorized_write(self):
        """Verifies that an agent with only default read capabilities cannot execute a write."""
        draft = "Valid draft text."
        token = self.approval_gate.generate_token(self.post_id, draft)
        proposal = ActionProposal(
            action_name="submit_comment",
            target_post_id=self.post_id,
            subreddit="r/Python",
            payload={"body": draft},
            approval_token=token,
            observed_post_hash=self.post_hash,
        )

        # Execute with default capabilities (no WRITE_COMMENT)
        ok, res, v_rec = self.harness.execute_verified_write(
            proposal, held_capabilities=DEFAULT_AGENT_CAPABILITIES
        )
        self.assertFalse(ok)
        self.assertTrue(any("LeastPrivilegeViolation" in v for v in v_rec.violations))

    def test_blast_radius_forbidden_subreddit(self):
        """Verifies that actions targeting subreddits outside allowed scope are blocked."""
        forbidden_pid = "post_wsb_001"
        self.env.posts[forbidden_pid] = MockPost(
            post_id=forbidden_pid,
            subreddit="r/WallStreetBets",
            author="u/trader",
            title="Meme Stock",
            selftext="YOLO",
            upvotes=1,
        )
        token = self.approval_gate.generate_token(forbidden_pid, "Comment")
        proposal = ActionProposal(
            action_name="submit_comment",
            target_post_id=forbidden_pid,
            subreddit="r/WallStreetBets",
            payload={"body": "Comment"},
            approval_token=token,
        )

        ok, res, v_rec = self.harness.execute_verified_write(proposal, held_capabilities=self.caps_with_write)
        self.assertFalse(ok)
        self.assertTrue(any("BlastRadiusViolation" in v for v in v_rec.violations))

    def test_blast_radius_frequency_limit(self):
        """Verifies that exceeding max_comments_per_run blocks subsequent actions."""
        # Max is 2 in setup
        for i in range(1, 3):
            pid = f"post_seq_{i}"
            self.env.posts[pid] = MockPost(
                post_id=pid,
                subreddit="r/Python",
                author=f"u/author_{i}",
                title=f"Post {i}",
                selftext=f"Body {i}",
                upvotes=2,
            )
            txt = f"Comment {i}"
            tok = self.approval_gate.generate_token(pid, txt)
            prop = ActionProposal(
                action_name="submit_comment",
                target_post_id=pid,
                subreddit="r/Python",
                payload={"body": txt},
                approval_token=tok,
                observed_post_hash=hashlib.sha256(f"Post {i}\nBody {i}".encode("utf-8")).hexdigest(),
            )
            ok, _, _ = self.harness.execute_verified_write(prop, held_capabilities=self.caps_with_write)
            self.assertTrue(ok)

        # 3rd attempt exceeds max_comments_per_run
        pid_3 = "post_seq_3"
        self.env.posts[pid_3] = MockPost(
            post_id=pid_3,
            subreddit="r/Python",
            author="u/author_3",
            title="Post 3",
            selftext="Body 3",
            upvotes=2,
        )
        tok_3 = self.approval_gate.generate_token(pid_3, "Comment 3")
        prop_3 = ActionProposal(
            action_name="submit_comment",
            target_post_id=pid_3,
            subreddit="r/Python",
            payload={"body": "Comment 3"},
            approval_token=tok_3,
        )
        ok_3, _, v_rec_3 = self.harness.execute_verified_write(prop_3, held_capabilities=self.caps_with_write)
        self.assertFalse(ok_3)
        self.assertTrue(any("BlastRadiusViolation" in v for v in v_rec_3.violations))

    def test_semantic_drift_detected_and_blocked(self):
        """Verifies that an edit to the target post mid-flight invalidates pre-conditions."""
        # Mid-flight edit
        self.env.posts[self.post_id].selftext = "EDITED: question is completely changed now."
        txt = "Solution to original question"
        tok = self.approval_gate.generate_token(self.post_id, txt)
        prop = ActionProposal(
            action_name="submit_comment",
            target_post_id=self.post_id,
            subreddit="r/Python",
            payload={"body": txt},
            approval_token=tok,
            observed_post_hash=self.post_hash,  # Hash of original unedited post
        )

        ok, _, v_rec = self.harness.execute_verified_write(prop, held_capabilities=self.caps_with_write)
        self.assertFalse(ok)
        self.assertTrue(any("SemanticDriftViolation" in v for v in v_rec.violations))

    def test_tampered_payload_blocked(self):
        """Verifies that modifying text after approval invalidates token hash."""
        approved = "Use functools.lru_cache."
        tok = self.approval_gate.generate_token(self.post_id, approved)
        tampered = "Use functools.lru_cache. Check my crypto telegram!"
        prop = ActionProposal(
            action_name="submit_comment",
            target_post_id=self.post_id,
            subreddit="r/Python",
            payload={"body": tampered},
            approval_token=tok,
            observed_post_hash=self.post_hash,
        )

        ok, _, v_rec = self.harness.execute_verified_write(prop, held_capabilities=self.caps_with_write)
        self.assertFalse(ok)
        self.assertTrue(any("ApprovalViolation" in v for v in v_rec.violations))

    def test_nonce_replay_blocked(self):
        """Verifies that reusing an already consumed token fails."""
        txt = "One-time comment"
        tok = self.approval_gate.generate_token(self.post_id, txt)
        prop = ActionProposal(
            action_name="submit_comment",
            target_post_id=self.post_id,
            subreddit="r/Python",
            payload={"body": txt},
            approval_token=tok,
            observed_post_hash=self.post_hash,
        )

        ok1, _, _ = self.harness.execute_verified_write(prop, held_capabilities=self.caps_with_write)
        self.assertTrue(ok1)

        # Attempt replay
        ok2, _, v_rec2 = self.harness.execute_verified_write(prop, held_capabilities=self.caps_with_write)
        self.assertFalse(ok2)
        # Blocked either by consumed nonce or duplicate post
        self.assertTrue(any("ApprovalViolation" in v or "Duplicate" in v for v in v_rec2.violations))

    def test_fail_closed_on_verifier_exception(self):
        """Verifies that an internal verifier crash immediately fails closed (denies action)."""
        prop = ActionProposal(
            action_name="submit_comment",
            target_post_id=self.post_id,
            subreddit="r/Python",
            payload={"body": "Test"},
            approval_token="token",
        )
        # Break limiter reference to simulate internal exception
        self.harness.pre_verifier.limiter = None
        ok, _, v_rec = self.harness.execute_verified_write(prop, held_capabilities=self.caps_with_write)
        self.assertFalse(ok)
        self.assertTrue(any("FailClosed" in v for v in v_rec.violations))

    def test_postcondition_fidelity_and_compensation(self):
        """Verifies that postcondition mismatch engages compensating deletion."""
        txt = "Correct proposed text"
        tok = self.approval_gate.generate_token(self.post_id, txt)
        prop = ActionProposal(
            action_name="submit_comment",
            target_post_id=self.post_id,
            subreddit="r/Python",
            payload={"body": txt},
            approval_token=tok,
            observed_post_hash=self.post_hash,
        )

        # Simulate corrupting server write
        def corrupt_submit(post_id, body):
            return self.env.submit_comment(post_id, "CORRUPTED SERVER BODY")

        orig_submit = self.client.submit_comment
        self.client.submit_comment = corrupt_submit

        ok, res, post_v = self.harness.execute_verified_write(prop, held_capabilities=self.caps_with_write)
        self.client.submit_comment = orig_submit  # restore

        self.assertFalse(ok)
        self.assertFalse(post_v.passed)
        self.assertEqual(res.get("status"), "postcondition_violation_compensated")
        self.assertEqual(res.get("compensation", {}).get("status"), "compensated")

        # Verify comment was actually removed by compensation
        remote_comments = self.client.get_comments(self.post_id)
        self.assertEqual(len(remote_comments), 0)


if __name__ == "__main__":
    unittest.main()
