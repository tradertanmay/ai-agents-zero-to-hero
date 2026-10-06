"""
Wake Triggers & Event Bus (Applied Agent Systems: A2)
Defines reactivation triggers and event-driven wake dispatch.
Core principle: 'Persistent agents wake up either on schedule or when reality changes.'
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid


class WakeTriggerType(str, Enum):
    """Classification of what prompted the agent to wake up."""

    SCHEDULED = "SCHEDULED"  # Recurring interval or cron-based reactivation
    EVENT = "EVENT"          # Reactive trigger from external webhook or bus
    MANUAL = "MANUAL"        # Explicit human operator intervention


@dataclass
class WakeEvent:
    """The reactivation signal delivered to the persistent agent upon waking."""

    trigger_type: WakeTriggerType
    event_name: str
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "trigger_type": self.trigger_type.value,
            "event_name": self.event_name,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WakeEvent":
        return cls(
            event_id=data["event_id"],
            trigger_type=WakeTriggerType(data["trigger_type"]),
            event_name=data["event_name"],
            payload=data.get("payload", {}),
            timestamp=data["timestamp"],
        )


class EventBus:
    """FIFO queue for event-driven wake notifications."""

    def __init__(self) -> None:
        self._queue: deque[WakeEvent] = deque()

    def publish(self, event: WakeEvent) -> None:
        """Enqueue an incoming event."""
        self._queue.append(event)

    def emit(self, trigger_type: WakeTriggerType, event_name: str, payload: dict[str, Any] | None = None) -> WakeEvent:
        """Helper to construct and enqueue a new wake event."""
        event = WakeEvent(
            trigger_type=trigger_type,
            event_name=event_name,
            payload=payload or {},
        )
        self.publish(event)
        return event

    def poll(self) -> WakeEvent | None:
        """Dequeue the oldest pending wake event."""
        if self._queue:
            return self._queue.popleft()
        return None

    def has_pending(self) -> bool:
        """Check if any wake events are queued."""
        return len(self._queue) > 0

    def clear(self) -> None:
        """Clear all pending events."""
        self._queue.clear()
