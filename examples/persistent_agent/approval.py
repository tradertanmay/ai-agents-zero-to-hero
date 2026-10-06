"""
Human Approval Gate & Stale Action Protection (Applied Agent Systems: A2)
Ensures external mutations require authorized, unexpired human approval,
and prevents executing actions against stale repository states.
Core principle: 'Persistent agents must never execute stale approvals if reality has drifted.'
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
from typing import Any
import uuid


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass
class ApprovalRequest:
    token: str
    action_type: str
    target_entity: str
    proposed_parameters: dict[str, Any]
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    expires_at: str = field(
        default_factory=lambda: (
            datetime.now(timezone.utc) + timedelta(hours=24)
        ).isoformat()
    )
    expected_state_hash: str | None = None
    decision_reason: str | None = None

    def is_expired(self, current_time: datetime | None = None) -> bool:
        now = current_time or datetime.now(timezone.utc)
        try:
            exp = datetime.fromisoformat(self.expires_at)
            return now >= exp
        except ValueError:
            return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "action_type": self.action_type,
            "target_entity": self.target_entity,
            "proposed_parameters": self.proposed_parameters,
            "status": self.status.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "expected_state_hash": self.expected_state_hash,
            "decision_reason": self.decision_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApprovalRequest":
        return cls(
            token=data["token"],
            action_type=data["action_type"],
            target_entity=data["target_entity"],
            proposed_parameters=data.get("proposed_parameters", {}),
            status=ApprovalStatus(data.get("status", ApprovalStatus.PENDING.value)),
            created_at=data["created_at"],
            expires_at=data["expires_at"],
            expected_state_hash=data.get("expected_state_hash"),
            decision_reason=data.get("decision_reason"),
        )


class ApprovalGate:
    """Manages creation, review, and verification of human approvals."""

    def __init__(self) -> None:
        self.requests: dict[str, ApprovalRequest] = {}

    @staticmethod
    def compute_state_hash(state_data: dict[str, Any]) -> str:
        """Compute SHA256 fingerprint of current observed entity state."""
        serialized = json.dumps(state_data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def create_request(
        self,
        action_type: str,
        target_entity: str,
        proposed_parameters: dict[str, Any],
        ttl_seconds: int = 86400,
        current_state: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        """Generate a new pending approval request with optional state fingerprint."""
        token = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()
        state_hash = self.compute_state_hash(current_state) if current_state else None

        req = ApprovalRequest(
            token=token,
            action_type=action_type,
            target_entity=target_entity,
            proposed_parameters=proposed_parameters,
            status=ApprovalStatus.PENDING,
            created_at=now.isoformat(),
            expires_at=expires_at,
            expected_state_hash=state_hash,
        )
        self.requests[token] = req
        return req

    def approve(self, token: str, reason: str = "Human maintainer approved") -> bool:
        """Approve a pending request."""
        if token not in self.requests:
            return False
        req = self.requests[token]
        if req.is_expired():
            req.status = ApprovalStatus.EXPIRED
            req.decision_reason = "Approval attempted after token expiration."
            return False
        if req.status != ApprovalStatus.PENDING:
            return False

        req.status = ApprovalStatus.APPROVED
        req.decision_reason = reason
        return True

    def reject(self, token: str, reason: str = "Human maintainer rejected") -> bool:
        """Reject a pending request."""
        if token not in self.requests:
            return False
        req = self.requests[token]
        req.status = ApprovalStatus.REJECTED
        req.decision_reason = reason
        return True

    def validate_for_execution(
        self,
        token: str,
        current_state: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """
        Validate whether the action may be executed now:
        - Must exist and be APPROVED
        - Must not be expired
        - Must match expected state hash (stale action protection)
        """
        if token not in self.requests:
            return False, "Approval token not found."

        req = self.requests[token]

        if req.is_expired():
            req.status = ApprovalStatus.EXPIRED
            return False, "Approval token has expired."

        if req.status != ApprovalStatus.APPROVED:
            return False, f"Request has not been approved (status: {req.status.value})."

        if req.expected_state_hash and current_state is not None:
            live_hash = self.compute_state_hash(current_state)
            if live_hash != req.expected_state_hash:
                return False, "Stale action rejected: target entity changed since proposal."

        return True, "Approval valid and verified against live state."
