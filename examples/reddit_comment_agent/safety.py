"""
Agent Safety and Verification System (Module 12)
Implements four layers of defense:
1. Policy: Allowed actions, subreddits, and blast-radius constraints
2. Permission: Read vs Write capability separation (least privilege)
3. Verification: Executable precondition and postcondition invariant checks
4. Recovery / Compensation: Mitigating side effects for irreversible actions

Core Axiom: "Do not ask the model to 'be safe' when the property can be enforced by code."
"""

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import time
from typing import Any, Callable

from .reddit import RedditClient
from .state import RedditAgentState
from .approval import ApprovalGate


class Capability(str, Enum):
    """
    Granular capability tokens enforcing the Principle of Least Privilege.
    Read capabilities are granted by default; write and delete capabilities
    require explicit external authorization.
    """
    READ_POSTS = "READ_POSTS"
    READ_POST = "READ_POST"
    READ_COMMENTS = "READ_COMMENTS"
    READ_RULES = "READ_RULES"
    WRITE_COMMENT = "WRITE_COMMENT"
    EDIT_COMMENT = "EDIT_COMMENT"
    DELETE_COMMENT = "DELETE_COMMENT"


DEFAULT_AGENT_CAPABILITIES = {
    Capability.READ_POSTS,
    Capability.READ_POST,
    Capability.READ_COMMENTS,
    Capability.READ_RULES,
}


@dataclass
class SafetyPolicy:
    """
    Blast Radius Control Policy.
    Formula: Blast Radius = Capability x Scope x Frequency x Duration
    """
    allowed_subreddits: set[str] = field(default_factory=lambda: {"r/Python", "r/MachineLearning", "r/AI_Agents"})
    allowed_accounts: set[str] = field(default_factory=lambda: {"u/HeroAgentBot"})
    max_comments_per_run: int = 1
    max_comments_per_subreddit_per_day: int = 3
    write_requires_human_approval: bool = True
    delete_requires_separate_approval: bool = True


@dataclass
class ActionProposal:
    """A proposed action emitted by the agent model policy."""
    action_name: str
    target_post_id: str
    subreddit: str
    payload: dict[str, Any]
    approval_token: str | None = None
    observed_post_hash: str | None = None
    actor: str = "u/HeroAgentBot"
    timestamp: float = field(default_factory=time.time)


@dataclass
class VerificationResult:
    """Outcome of precondition or postcondition verification."""
    passed: bool
    violations: list[str] = field(default_factory=list)
    failure_type: str | None = None  # "detection", "enforcement", "policy", or None
    details: dict[str, Any] = field(default_factory=dict)


class BlastRadiusLimiter:
    """
    Tracks and limits action frequencies across runs and rolling time windows.
    Prevents runaway loops from causing widespread external damage.
    """

    def __init__(self, policy: SafetyPolicy) -> None:
        self.policy = policy
        self.run_comment_count = 0
        # Maps subreddit -> list of timestamps of submitted comments
        self.subreddit_comment_history: dict[str, list[float]] = {}

    def check_limits(self, subreddit: str) -> tuple[bool, str]:
        # 1. Scope check
        if subreddit not in self.policy.allowed_subreddits:
            return False, f"BlastRadiusViolation: Subreddit '{subreddit}' is outside allowed scope {self.policy.allowed_subreddits}."

        # 2. Run frequency check
        if self.run_comment_count >= self.policy.max_comments_per_run:
            return False, (
                f"BlastRadiusViolation: Exceeded max comments per run "
                f"({self.run_comment_count}/{self.policy.max_comments_per_run})."
            )

        # 3. Rolling 24-hour frequency check
        now = time.time()
        one_day_ago = now - 86400.0
        recent = [t for t in self.subreddit_comment_history.get(subreddit, []) if t > one_day_ago]
        self.subreddit_comment_history[subreddit] = recent

        if len(recent) >= self.policy.max_comments_per_subreddit_per_day:
            return False, (
                f"BlastRadiusViolation: Exceeded daily comment limit for '{subreddit}' "
                f"({len(recent)}/{self.policy.max_comments_per_subreddit_per_day})."
            )

        return True, "Within blast-radius limits."

    def record_comment_action(self, subreddit: str) -> None:
        self.run_comment_count += 1
        if subreddit not in self.subreddit_comment_history:
            self.subreddit_comment_history[subreddit] = []
        self.subreddit_comment_history[subreddit].append(time.time())


class PreconditionVerifier:
    """
    Verifies that all required system invariants are satisfied BEFORE executing a side effect.
    The model proposes an action; this verifier determines if it is legally permissible.
    """

    def __init__(self, policy: SafetyPolicy, limiter: BlastRadiusLimiter) -> None:
        self.policy = policy
        self.limiter = limiter

    def verify(
        self,
        proposal: ActionProposal,
        client: RedditClient,
        state: RedditAgentState,
        approval_gate: ApprovalGate,
        held_capabilities: set[Capability],
    ) -> VerificationResult:
        violations: list[str] = []

        try:
            # 1. Capability & Least Privilege Check
            required_cap = Capability.WRITE_COMMENT if proposal.action_name == "submit_comment" else (
                Capability.DELETE_COMMENT if proposal.action_name == "delete_comment" else Capability.READ_POST
            )
            if required_cap not in held_capabilities:
                violations.append(
                    f"LeastPrivilegeViolation: Action '{proposal.action_name}' requires capability "
                    f"'{required_cap.value}', but agent only possesses {[c.value for c in held_capabilities]}."
                )

            # 2. Blast Radius & Scope Check
            within_limits, limit_reason = self.limiter.check_limits(proposal.subreddit)
            if not within_limits:
                violations.append(limit_reason)

            # 3. Target Post Existence Check
            remote_post = client.get_post(proposal.target_post_id)
            if not remote_post:
                violations.append(f"TargetPostMissing: Post '{proposal.target_post_id}' does not exist on Reddit.")
            else:
                # 4. Semantic Content Drift Check (Invariant 5)
                if proposal.observed_post_hash:
                    current_content = f"{remote_post['title']}\n{remote_post.get('selftext', '')}"
                    current_hash = hashlib.sha256(current_content.encode("utf-8")).hexdigest()
                    if current_hash != proposal.observed_post_hash:
                        violations.append(
                            f"SemanticDriftViolation: Target post content was modified after agent observation. "
                            f"Observed: {proposal.observed_post_hash[:8]}..., Current: {current_hash[:8]}..."
                        )

            # 5. Duplicate Action Check (Invariant 4)
            if state.has_commented(proposal.target_post_id):
                violations.append(
                    f"DuplicateActionViolation: Local state shows post '{proposal.target_post_id}' already commented on."
                )

            # 6. Cryptographic Approval Gate Verification (Invariants 1, 2, 3)
            if proposal.action_name == "submit_comment":
                submitted_text = proposal.payload.get("body", "")
                if not proposal.approval_token:
                    violations.append("ApprovalViolation: submit_comment called without approval_token.")
                else:
                    valid, reason = approval_gate.verify_and_consume_token(
                        proposal.target_post_id,
                        submitted_text,
                        proposal.approval_token,
                    )
                    if not valid:
                        violations.append(f"ApprovalViolation: {reason}")

        except Exception as exc:
            # FAIL-CLOSED INVARIANT: Any verifier crash denies the action immediately
            return VerificationResult(
                passed=False,
                violations=[f"VerifierCrashFailClosed: Verifier encountered unexpected exception: {type(exc).__name__}: {str(exc)}"],
                failure_type="detection",
            )

        if violations:
            return VerificationResult(passed=False, violations=violations, failure_type="policy")
        return VerificationResult(passed=True, violations=[])


class PostconditionVerifier:
    """
    Verifies system invariants AFTER an external write completes.
    Do not declare success simply because the API returned 200 OK.
    Re-read the remote state to confirm the exact expected side effect occurred.
    """

    @staticmethod
    def verify(
        proposal: ActionProposal,
        execution_result: dict[str, Any],
        client: RedditClient,
        state: RedditAgentState,
    ) -> VerificationResult:
        violations: list[str] = []

        try:
            # 1. API Response Check
            if execution_result.get("status") != "success":
                return VerificationResult(
                    passed=False,
                    violations=[f"ExecutionFailed: Remote client reported error: {execution_result.get('error')}"],
                    failure_type="enforcement",
                )

            comment_id = execution_result.get("comment_id")
            if not comment_id:
                return VerificationResult(
                    passed=False,
                    violations=["MissingCommentId: API returned success but omitted comment_id."],
                    failure_type="enforcement",
                )

            # 2. Remote State Re-Read (Reconciliation)
            remote_comments = client.get_comments(proposal.target_post_id, limit=50)
            matching_id = [c for c in remote_comments if c["comment_id"] == comment_id]

            if not matching_id:
                violations.append(
                    f"PostconditionMismatch: Comment '{comment_id}' not found in remote post comments after write."
                )
            else:
                found_comment = matching_id[0]
                expected_body = proposal.payload.get("body", "")
                # 3. Exact Text Fidelity Check (Invariant 2)
                if found_comment["body"].strip() != expected_body.strip():
                    violations.append(
                        f"ContentTamperViolation: Remote comment text does not match submitted text. "
                        f"Expected: {expected_body[:30]}..., Found: {found_comment['body'][:30]}..."
                    )

            # 4. Duplicate Check: Ensure exactly one copy exists from this agent
            my_matching_comments = [
                c for c in remote_comments
                if c["author"] == proposal.actor and c["body"].strip() == proposal.payload.get("body", "").strip()
            ]
            if len(my_matching_comments) > 1:
                violations.append(
                    f"DoublePostViolation: Detected {len(my_matching_comments)} duplicate copies of comment on server."
                )

            # 5. Audit Trajectory Check (Invariant 6)
            if not state.has_commented(proposal.target_post_id):
                violations.append(
                    f"AuditInvariantViolation: State failed to record comment submission in persistent audit memory."
                )

        except Exception as exc:
            return VerificationResult(
                passed=False,
                violations=[f"PostconditionVerifierCrash: {type(exc).__name__}: {str(exc)}"],
                failure_type="enforcement",
            )

        if violations:
            return VerificationResult(passed=False, violations=violations, failure_type="enforcement")
        return VerificationResult(passed=True, violations=[])


class CompensationManager:
    """
    Manages compensation workflows for side effects that violate invariants.
    Important Lesson: External side effects are COMPENSATABLE, not truly REVERSIBLE.
    Deleting a comment removes it from the current thread, but users may have already
    read it, notifications fired, and external scrapers cached the content.
    """

    @staticmethod
    def compensate_failed_write(
        proposal: ActionProposal,
        execution_result: dict[str, Any],
        client: RedditClient,
        state: RedditAgentState,
        reason: str,
    ) -> dict[str, Any]:
        comment_id = execution_result.get("comment_id")
        if not comment_id:
            return {"status": "error", "message": "No comment_id available to compensate."}

        # Attempt compensating deletion
        del_res = client.delete_comment(proposal.target_post_id, comment_id)
        # Log compensation event in persistent memory
        state.record_draft(
            post_id=proposal.target_post_id,
            draft_text=proposal.payload.get("body", ""),
            score=0.0,
            status="COMPENSATED_DELETED",
            reason=f"Compensation deletion: {reason}",
        )

        return {
            "status": "compensated",
            "comment_id": comment_id,
            "post_id": proposal.target_post_id,
            "reason": reason,
            "deletion_result": del_res,
        }


class SafetyVerificationHarness:
    """
    Central Safety Controller.
    Pipeline:
      Model proposes
        -> Policy checks
        -> Precondition verification
        -> Capability elevation / Authorization
        -> Runtime executes
        -> Postcondition verification
        -> Record outcome (or trigger Compensation)
    """

    def __init__(
        self,
        client: RedditClient,
        state: RedditAgentState,
        approval_gate: ApprovalGate,
        policy: SafetyPolicy | None = None,
    ) -> None:
        self.client = client
        self.state = state
        self.approval_gate = approval_gate
        self.policy = policy or SafetyPolicy()
        self.limiter = BlastRadiusLimiter(self.policy)
        self.pre_verifier = PreconditionVerifier(self.policy, self.limiter)
        self.post_verifier = PostconditionVerifier()
        self.compensation = CompensationManager()

        # Audit counters
        self.audit_log: list[dict[str, Any]] = []

    def execute_verified_write(
        self,
        proposal: ActionProposal,
        held_capabilities: set[Capability] | None = None,
    ) -> tuple[bool, dict[str, Any], VerificationResult]:
        """
        Executes a write side effect through all four safety layers.
        Returns: (success: bool, result_dict: dict, verification_record: VerificationResult)
        """
        caps = held_capabilities if held_capabilities is not None else set(DEFAULT_AGENT_CAPABILITIES)

        # ---------------------------------------------------------------------
        # LAYER 1 & 2: Policy & Precondition Verification
        # ---------------------------------------------------------------------
        pre_result = self.pre_verifier.verify(
            proposal=proposal,
            client=self.client,
            state=self.state,
            approval_gate=self.approval_gate,
            held_capabilities=caps,
        )

        if not pre_result.passed:
            self.audit_log.append({
                "stage": "precondition_denied",
                "action": proposal.action_name,
                "post_id": proposal.target_post_id,
                "violations": pre_result.violations,
                "failure_type": pre_result.failure_type,
            })
            return False, {"status": "blocked", "violations": pre_result.violations}, pre_result

        # ---------------------------------------------------------------------
        # LAYER 3: Runtime Execution
        # ---------------------------------------------------------------------
        exec_res = self.client.submit_comment(
            post_id=proposal.target_post_id,
            body=proposal.payload.get("body", ""),
        )

        if exec_res.get("status") == "success":
            comment_id = exec_res.get("comment_id", "c_unknown")
            self.state.record_submitted_comment(
                proposal.target_post_id,
                comment_id,
                proposal.payload.get("body", ""),
            )
            self.limiter.record_comment_action(proposal.subreddit)

        # ---------------------------------------------------------------------
        # LAYER 4: Postcondition Verification & Compensation
        # ---------------------------------------------------------------------
        post_result = self.post_verifier.verify(
            proposal=proposal,
            execution_result=exec_res,
            client=self.client,
            state=self.state,
        )

        if not post_result.passed:
            # Invariant violated after execution -> Trigger Compensating Action
            comp_res = self.compensation.compensate_failed_write(
                proposal=proposal,
                execution_result=exec_res,
                client=self.client,
                state=self.state,
                reason="; ".join(post_result.violations),
            )
            self.audit_log.append({
                "stage": "postcondition_failed_compensated",
                "action": proposal.action_name,
                "post_id": proposal.target_post_id,
                "violations": post_result.violations,
                "compensation": comp_res,
            })
            return False, {"status": "postcondition_violation_compensated", "violations": post_result.violations, "compensation": comp_res}, post_result

        self.audit_log.append({
            "stage": "verified_success",
            "action": proposal.action_name,
            "post_id": proposal.target_post_id,
            "comment_id": exec_res.get("comment_id"),
        })
        return True, exec_res, post_result
