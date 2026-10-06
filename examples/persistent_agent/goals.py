"""
Durable Goals & Commitments (Applied Agent Systems: A2)
Defines long-lived goals, open commitments, and goal revalidation logic.
Core principle: 'Persistent memory = information survives.
Persistent agent = goals, state, unfinished work, and execution continue across time.'
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import uuid


class CommitmentStatus(str, Enum):
    """Lifecycle status of a specific commitment made by the agent."""

    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    FULFILLED = "FULFILLED"
    ABANDONED = "ABANDONED"


@dataclass
class Commitment:
    """A concrete, bounded task or promise the agent tracks across wakes."""

    commitment_id: str
    goal_id: str
    description: str
    target_entity: str  # e.g., "issue:#42" or "pr:#12"
    status: CommitmentStatus = CommitmentStatus.OPEN
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    due_date: str | None = None
    fulfillment_evidence: str | None = None

    def mark_fulfilled(self, evidence: str) -> None:
        """Mark commitment as fulfilled with verifiable audit evidence."""
        self.status = CommitmentStatus.FULFILLED
        self.fulfillment_evidence = evidence
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def mark_abandoned(self, reason: str) -> None:
        """Mark commitment as abandoned with reason."""
        self.status = CommitmentStatus.ABANDONED
        self.fulfillment_evidence = f"ABANDONED: {reason}"
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "commitment_id": self.commitment_id,
            "goal_id": self.goal_id,
            "description": self.description,
            "target_entity": self.target_entity,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "due_date": self.due_date,
            "fulfillment_evidence": self.fulfillment_evidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Commitment":
        return cls(
            commitment_id=data["commitment_id"],
            goal_id=data["goal_id"],
            description=data["description"],
            target_entity=data["target_entity"],
            status=CommitmentStatus(data.get("status", CommitmentStatus.OPEN.value)),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            due_date=data.get("due_date"),
            fulfillment_evidence=data.get("fulfillment_evidence"),
        )


@dataclass
class DurableGoal:
    """A long-running, multi-wake objective assigned to the persistent agent."""

    goal_id: str
    description: str
    target_repo: str
    is_active: bool = True
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    expires_at: str | None = None
    success_criteria: list[str] = field(default_factory=list)
    completion_notes: str | None = None

    @classmethod
    def create(
        cls,
        description: str,
        target_repo: str,
        expires_at: str | None = None,
        success_criteria: list[str] | None = None,
    ) -> "DurableGoal":
        return cls(
            goal_id=str(uuid.uuid4()),
            description=description,
            target_repo=target_repo,
            is_active=True,
            expires_at=expires_at,
            success_criteria=success_criteria or [],
        )

    def is_expired(self, current_time: datetime | None = None) -> bool:
        """Check if goal has expired based on current timestamp."""
        if not self.expires_at:
            return False
        now = current_time or datetime.now(timezone.utc)
        try:
            exp = datetime.fromisoformat(self.expires_at)
            return now >= exp
        except ValueError:
            return False

    def mark_completed(self, notes: str = "") -> None:
        """Mark goal as fulfilled and inactive."""
        self.is_active = False
        self.completion_notes = notes

    def mark_cancelled(self, reason: str = "") -> None:
        """Mark goal as cancelled and inactive."""
        self.is_active = False
        self.completion_notes = f"CANCELLED: {reason}"

    def revalidate(self, repo_context: dict) -> tuple[bool, str]:
        """
        Revalidate goal against live environment reality.
        Returns (is_still_valid, reason).
        """
        if not self.is_active:
            return False, f"Goal is inactive: {self.completion_notes or 'Completed'}"
        if self.is_expired():
            self.mark_cancelled("Goal duration expired")
            return False, "Goal duration has expired."
        if repo_context.get("is_archived", False):
            self.mark_cancelled("Target repository was archived")
            return False, "Target repository has been archived."
        return True, "Goal remains valid and actionable."

    def to_dict(self) -> dict:
        return {
            "goal_id": self.goal_id,
            "description": self.description,
            "target_repo": self.target_repo,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "success_criteria": self.success_criteria,
            "completion_notes": self.completion_notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DurableGoal":
        return cls(
            goal_id=data["goal_id"],
            description=data["description"],
            target_repo=data["target_repo"],
            is_active=data.get("is_active", True),
            created_at=data["created_at"],
            expires_at=data.get("expires_at"),
            success_criteria=data.get("success_criteria", []),
            completion_notes=data.get("completion_notes"),
        )
