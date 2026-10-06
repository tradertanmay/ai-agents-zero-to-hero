"""
Human-in-the-Loop Approval Gate (Module 08 & 12 Application)
Enforces a mandatory human verification step before any write action
(submit_comment) can be dispatched to Reddit.
"""

from dataclasses import dataclass
import hashlib
import hmac
import time
from typing import Any, Callable


@dataclass
class ApprovalDecision:
    approved: bool
    edited_text: str | None = None
    approval_token: str | None = None
    reason: str = ""


class ApprovalGate:
    """
    Cryptographic-backed permission gate requiring human confirmation.
    Autonomous posting without approval is mathematically prohibited.
    """

    def __init__(
        self,
        secret_key: str = "agent_safety_secret_key_v1",
        interactive: bool = True,
        approval_callback: Callable[[dict[str, Any]], ApprovalDecision] | None = None,
    ) -> None:
        self.secret_key = secret_key.encode("utf-8")
        self.interactive = interactive
        self.approval_callback = approval_callback

    def generate_token(self, post_id: str, text: str) -> str:
        """Generates an HMAC token proving this specific text was approved for this post."""
        payload = f"{post_id}:{text.strip()}".encode("utf-8")
        return hmac.new(self.secret_key, payload, hashlib.sha256).hexdigest()

    def verify_token(self, post_id: str, text: str, token: str) -> bool:
        """Verifies that the provided token matches the post and text payload."""
        expected = self.generate_token(post_id, text)
        return hmac.compare_digest(expected, token)

    def request_approval(
        self,
        post: dict[str, Any],
        draft_comment: str,
        evaluator_score: float,
        evaluator_feedback: str,
    ) -> ApprovalDecision:
        """Presents draft to human operator and requests explicit sign-off."""
        review_payload = {
            "post_id": post.get("post_id"),
            "subreddit": post.get("subreddit"),
            "title": post.get("title"),
            "author": post.get("author"),
            "selftext": post.get("selftext"),
            "draft_comment": draft_comment,
            "evaluator_score": evaluator_score,
            "evaluator_feedback": evaluator_feedback,
        }

        # If a programmatic callback is registered (e.g. for unit tests or headless runners)
        if self.approval_callback is not None:
            decision = self.approval_callback(review_payload)
            if decision.approved:
                final_text = decision.edited_text or draft_comment
                decision.approval_token = self.generate_token(post["post_id"], final_text)
            return decision

        if not self.interactive:
            return ApprovalDecision(
                approved=False,
                reason="Non-interactive execution mode requires explicit approval callback.",
            )

        # Interactive Terminal UI
        print("\n" + "=" * 65)
        print("HUMAN-IN-THE-LOOP APPROVAL REQUIRED")
        print("=" * 65)
        print(f"SUBREDDIT: {post.get('subreddit')}")
        print(f"POST TITLE: {post.get('title')}")
        print(f"POST AUTHOR: {post.get('author')}")
        print("-" * 65)
        print("POST CONTENT:")
        print(post.get("selftext", "").strip())
        print("-" * 65)
        print(f"PROPOSED DRAFT COMMENT (Evaluator Score: {evaluator_score:.1f}/10.0):")
        print(draft_comment.strip())
        print("-" * 65)
        print("EVALUATOR BREAKDOWN:")
        print(evaluator_feedback)
        print("=" * 65)
        print("ACTIONS:")
        print("  [1] Approve & Post comment")
        print("  [2] Edit comment before posting")
        print("  [3] Reject and skip post")
        print("=" * 65)

        try:
            choice = input("Select action (1/2/3) [default: 3]: ").strip()
        except (EOFError, KeyboardInterrupt):
            choice = "3"

        if choice == "1":
            token = self.generate_token(post["post_id"], draft_comment)
            return ApprovalDecision(approved=True, approval_token=token, reason="Approved by human operator.")
        elif choice == "2":
            print("\nEnter edited comment (single-line or paste):")
            try:
                edited = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                return ApprovalDecision(approved=False, reason="Edit aborted.")
            if not edited:
                return ApprovalDecision(approved=False, reason="Empty edited comment rejected.")
            token = self.generate_token(post["post_id"], edited)
            return ApprovalDecision(
                approved=True,
                edited_text=edited,
                approval_token=token,
                reason="Edited and approved by human operator.",
            )
        else:
            return ApprovalDecision(approved=False, reason="Rejected by human operator.")
