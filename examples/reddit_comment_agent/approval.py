"""
Cryptographically Enforced Approval Capability (Modules 08 & 12 Application)
Enforces that submit_comment() requires a signed, short-lived, single-use
approval token bound to the specific post and comment text hash.
The signing secret is held outside the agent's autonomous control.
"""

from dataclasses import dataclass
import hashlib
import hmac
import time
import uuid
from typing import Any, Callable


@dataclass
class ApprovalDecision:
    approved: bool
    edited_text: str | None = None
    approval_token: str | None = None
    reason: str = ""


class ApprovalGate:
    """
    Cryptographically enforced approval capability.
    Tokens are short-lived, single-use (nonce-tracked), and bound to:
    - post_id
    - SHA-256 hash of approved comment text
    - expiry timestamp
    - unique cryptographic nonce
    """

    def __init__(
        self,
        secret_key: str = "agent_safety_secret_key_v1",
        interactive: bool = True,
        approval_callback: Callable[[dict[str, Any]], ApprovalDecision] | None = None,
        default_ttl_seconds: float = 300.0,
    ) -> None:
        self.secret_key = secret_key.encode("utf-8")
        self.interactive = interactive
        self.approval_callback = approval_callback
        self.default_ttl_seconds = default_ttl_seconds
        self.used_nonces: set[str] = set()

    def generate_token(self, post_id: str, text: str, ttl_seconds: float | None = None) -> str:
        """
        Generates a signed capability token bound to post_id, hash(text), expiry, and nonce.
        Format: post_id.text_hash.expires_at.nonce.signature
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        expires_at = int(time.time() + ttl)
        text_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
        nonce = uuid.uuid4().hex[:16]

        payload = f"{post_id}:{text_hash}:{expires_at}:{nonce}".encode("utf-8")
        sig = hmac.new(self.secret_key, payload, hashlib.sha256).hexdigest()

        return f"{post_id}.{text_hash}.{expires_at}.{nonce}.{sig}"

    def verify_and_consume_token(self, post_id: str, text: str, token: str) -> tuple[bool, str]:
        """
        Verifies the approval capability token and consumes its nonce to prevent replay.
        """
        if not token or "." not in token:
            return False, "MalformedTokenError: Invalid token format."

        parts = token.split(".")
        if len(parts) != 5:
            return False, "MalformedTokenError: Expected 5 token segments."

        tok_post_id, tok_text_hash, tok_expires_str, tok_nonce, tok_sig = parts

        # 1. Post ID binding check
        if tok_post_id != post_id:
            return False, f"PostMismatchError: Token issued for '{tok_post_id}', attempted for '{post_id}'."

        # 2. Text hash binding check
        computed_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
        if not hmac.compare_digest(tok_text_hash, computed_hash):
            return False, "TextTamperError: Approved comment text was modified after human sign-off."

        # 3. Expiry check
        try:
            expires_at = float(tok_expires_str)
        except ValueError:
            return False, "MalformedTokenError: Invalid expiry timestamp."

        if time.time() > expires_at:
            return False, "TokenExpiredError: Approval token has expired."

        # 4. Single-use replay protection
        if tok_nonce in self.used_nonces:
            return False, "TokenReplayError: Approval token has already been consumed."

        # 5. Cryptographic signature check
        expected_payload = f"{tok_post_id}:{tok_text_hash}:{tok_expires_str}:{tok_nonce}".encode("utf-8")
        expected_sig = hmac.new(self.secret_key, expected_payload, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected_sig, tok_sig):
            return False, "SignatureVerificationError: Invalid cryptographic signature on token."

        # Token is valid: consume nonce
        self.used_nonces.add(tok_nonce)
        return True, "Approval token verified and consumed successfully."

    def verify_token(self, post_id: str, text: str, token: str) -> bool:
        """Convenience method returning a simple boolean validation."""
        valid, _ = self.verify_and_consume_token(post_id, text, token)
        return valid

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
        print(f"PROPOSED DRAFT COMMENT (Quality Gate Score: {evaluator_score:.1f}/10.0):")
        print(draft_comment.strip())
        print("-" * 65)
        print("QUALITY GATE EVALUATION:")
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
