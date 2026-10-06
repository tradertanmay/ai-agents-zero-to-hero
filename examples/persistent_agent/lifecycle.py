"""
Persistent Agent Lifecycle & State Machine (Applied Agent Systems: A2)
Defines explicit durable states, transition validation, and lifecycle event taxonomy.
Core principle: 'Persistence is not an infinite loop. It is controlled reactivation across time.'
"""

from enum import Enum


class AgentState(str, Enum):
    """Explicit lifecycle states for a durable persistent agent."""

    CREATED = "CREATED"
    SCHEDULED = "SCHEDULED"
    SLEEPING = "SLEEPING"
    WAKING = "WAKING"
    OBSERVING = "OBSERVING"
    DECIDING = "DECIDING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    ACTING = "ACTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class LifecycleEvent(str, Enum):
    """Event log types recorded in the persistent audit trail."""

    WAKE = "WAKE"
    OBSERVATION = "OBSERVATION"
    DECISION = "DECISION"
    ABSTAIN = "ABSTAIN"
    ACTION_PROPOSED = "ACTION_PROPOSED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    VERIFIED = "VERIFIED"
    MEMORY_COMPACTED = "MEMORY_COMPACTED"
    SLEEP = "SLEEP"
    PAUSED = "PAUSED"
    TERMINATED = "TERMINATED"


# Valid state transitions mapping
VALID_TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.CREATED: {AgentState.SCHEDULED, AgentState.SLEEPING, AgentState.WAKING, AgentState.PAUSED, AgentState.CANCELLED},
    AgentState.SCHEDULED: {AgentState.WAKING, AgentState.SLEEPING, AgentState.PAUSED, AgentState.CANCELLED},
    AgentState.SLEEPING: {AgentState.WAKING, AgentState.PAUSED, AgentState.CANCELLED, AgentState.COMPLETED},
    AgentState.WAKING: {
        AgentState.OBSERVING,
        AgentState.SLEEPING,
        AgentState.PAUSED,
        AgentState.CANCELLED,
        AgentState.COMPLETED,
        AgentState.FAILED,
    },
    AgentState.OBSERVING: {AgentState.DECIDING, AgentState.SLEEPING, AgentState.PAUSED, AgentState.CANCELLED, AgentState.FAILED},
    AgentState.DECIDING: {
        AgentState.WAITING_FOR_APPROVAL,
        AgentState.ACTING,
        AgentState.SLEEPING,
        AgentState.COMPLETED,
        AgentState.PAUSED,
        AgentState.CANCELLED,
        AgentState.FAILED,
    },
    AgentState.WAITING_FOR_APPROVAL: {
        AgentState.WAKING,
        AgentState.ACTING,
        AgentState.DECIDING,
        AgentState.SLEEPING,
        AgentState.PAUSED,
        AgentState.CANCELLED,
        AgentState.FAILED,
    },
    AgentState.ACTING: {AgentState.VERIFYING, AgentState.FAILED, AgentState.PAUSED},
    AgentState.VERIFYING: {AgentState.SLEEPING, AgentState.COMPLETED, AgentState.FAILED, AgentState.PAUSED},
    AgentState.PAUSED: {AgentState.WAKING, AgentState.SLEEPING, AgentState.CANCELLED, AgentState.COMPLETED},
    AgentState.COMPLETED: set(),  # Terminal state
    AgentState.CANCELLED: set(),  # Terminal state
    AgentState.FAILED: {AgentState.PAUSED, AgentState.CANCELLED},
}


def validate_transition(current: AgentState, target: AgentState) -> bool:
    """Returns True if transition from current to target state is legally permitted."""
    allowed = VALID_TRANSITIONS.get(current, set())
    return target in allowed
