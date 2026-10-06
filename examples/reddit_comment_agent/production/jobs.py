"""
Durable Execution & Explicit State Machine (Module 13)
Replaces implicit runtime control flow with an explicit, verifiable state machine.
Enforces that every state transition is legal and auditable.
"""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any


class InvalidStateTransitionError(Exception):
    """Raised when an illegal state machine transition is attempted."""
    pass


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    READY_TO_EXECUTE = "READY_TO_EXECUTE"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobStage(str, Enum):
    QUEUED = "QUEUED"
    DISCOVERING = "DISCOVERING"
    INSPECTING = "INSPECTING"
    DRAFTING = "DRAFTING"
    EVALUATING = "EVALUATING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    READY_TO_EXECUTE = "READY_TO_EXECUTE"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Explicit state transition map: current_stage -> set of permitted next stages
LEGAL_TRANSITIONS: dict[JobStage, set[JobStage]] = {
    JobStage.QUEUED: {JobStage.DISCOVERING, JobStage.INSPECTING, JobStage.FAILED, JobStage.CANCELLED},
    JobStage.DISCOVERING: {JobStage.INSPECTING, JobStage.SUCCEEDED, JobStage.FAILED, JobStage.CANCELLED},
    JobStage.INSPECTING: {JobStage.DRAFTING, JobStage.SUCCEEDED, JobStage.FAILED, JobStage.CANCELLED},
    JobStage.DRAFTING: {JobStage.EVALUATING, JobStage.FAILED, JobStage.CANCELLED},
    JobStage.EVALUATING: {JobStage.WAITING_FOR_APPROVAL, JobStage.SUCCEEDED, JobStage.FAILED, JobStage.CANCELLED},
    JobStage.WAITING_FOR_APPROVAL: {JobStage.READY_TO_EXECUTE, JobStage.SUCCEEDED, JobStage.FAILED, JobStage.CANCELLED},
    JobStage.READY_TO_EXECUTE: {JobStage.EXECUTING, JobStage.FAILED, JobStage.CANCELLED},
    JobStage.EXECUTING: {JobStage.VERIFYING, JobStage.SUCCEEDED, JobStage.FAILED, JobStage.CANCELLED},
    JobStage.VERIFYING: {JobStage.SUCCEEDED, JobStage.FAILED, JobStage.CANCELLED},
    JobStage.SUCCEEDED: set(),
    JobStage.FAILED: set(),
    JobStage.CANCELLED: set(),
}


def validate_transition(from_stage: JobStage, to_stage: JobStage) -> None:
    """Validates that a stage transition is explicitly allowed."""
    if from_stage == to_stage:
        return
    allowed = LEGAL_TRANSITIONS.get(from_stage, set())
    if to_stage not in allowed:
        raise InvalidStateTransitionError(
            f"IllegalStateTransition: Cannot transition from stage '{from_stage.value}' to '{to_stage.value}'. "
            f"Allowed next stages: {[s.value for s in allowed]}."
        )


@dataclass
class JobRecord:
    """
    Complete persistent representation of an agent job execution.
    Contains version tracking, state machine position, worker lease, and audit trajectory.
    """
    job_id: str
    current_stage: JobStage = JobStage.QUEUED
    status: JobStatus = JobStatus.QUEUED
    attempt_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    leased_by: str | None = None
    lease_expires_at: float | None = None

    # Version tracking for regression attribution
    agent_version: str = "0.13.0"
    prompt_version: str = "reddit-draft-v4"
    tool_schema_version: str = "tools-v2"
    policy_version: str = "safety-v2"
    evaluator_version: str = "eval-v3"

    # Execution payloads
    input_snapshot: dict[str, Any] = field(default_factory=dict)
    trajectory: list[dict[str, Any]] = field(default_factory=list)
    pending_action: dict[str, Any] | None = None
    result: dict[str, Any] | None = None

    def transition_to(self, new_stage: JobStage, new_status: JobStatus | None = None) -> None:
        """Transitions this job to a new stage, checking legal state machine constraints."""
        validate_transition(self.current_stage, new_stage)
        self.current_stage = new_stage
        if new_status:
            self.status = new_status
        self.updated_at = time.time()
