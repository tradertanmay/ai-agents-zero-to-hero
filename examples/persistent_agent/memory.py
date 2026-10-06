"""
Consolidated Memory Architecture (Applied Agent Systems: A2)
Implements memory tiering and compaction to prevent token context bloat:
- Working State: ephemeral scratchpad for current wake cycle
- Recent Events: FIFO buffer of recent agent cycles
- Long-Term Summary: rolling consolidated synopsis of repository history
- Important Facts: durable key-value knowledge base
- Open Commitments: active tracking of explicit promises
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from examples.persistent_agent.goals import Commitment


@dataclass
class ConsolidatedMemory:
    """
    Tiered memory model designed for persistent execution across days and weeks.
    Prevents token window explosion via structured compaction.
    """

    working_state: dict[str, Any] = field(default_factory=dict)
    recent_events: list[dict[str, Any]] = field(default_factory=list)
    long_term_summary: str = ""
    important_facts: dict[str, str] = field(default_factory=dict)
    commitments: list[Commitment] = field(default_factory=list)

    def record_event(self, event_type: str, summary: str, details: dict[str, Any] | None = None) -> None:
        """Append an event to the recent events FIFO buffer."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "summary": summary,
            "details": details or {},
        }
        self.recent_events.append(record)

    def record_fact(self, key: str, value: str) -> None:
        """Store or update a durable factual insight about the repository."""
        self.important_facts[key] = value

    def add_commitment(self, commitment: Commitment) -> None:
        """Add an active commitment to track."""
        self.commitments.append(commitment)

    def get_open_commitments(self) -> list[Commitment]:
        """Return commitments that are open or in progress."""
        return [c for c in self.commitments if c.status.value in {"OPEN", "IN_PROGRESS"}]

    def compact(self, max_recent_events: int = 5) -> int:
        """
        Compact memory when recent events exceed max threshold.
        Rolls older events into long_term_summary and archives fulfilled commitments.
        Returns the number of events compacted.
        """
        if len(self.recent_events) <= max_recent_events:
            return 0

        num_to_compact = len(self.recent_events) - max_recent_events
        events_to_archive = self.recent_events[:num_to_compact]
        self.recent_events = self.recent_events[num_to_compact:]

        # Build rolled summary lines
        archive_lines = []
        for ev in events_to_archive:
            ts = ev.get("timestamp", "")[:19]
            archive_lines.append(f"[{ts}] {ev.get('type')}: {ev.get('summary')}")

        compacted_chunk = "\n".join(archive_lines)
        if self.long_term_summary:
            self.long_term_summary += f"\n{compacted_chunk}"
        else:
            self.long_term_summary = compacted_chunk

        # Also summarize and remove fulfilled/abandoned commitments older than 1 cycle
        active_commitments = []
        for c in self.commitments:
            if c.status.value in {"FULFILLED", "ABANDONED"}:
                summary_line = f"Commitment {c.commitment_id} ({c.description}) -> {c.status.value}"
                if c.fulfillment_evidence:
                    summary_line += f" (Evidence: {c.fulfillment_evidence})"
                self.long_term_summary += f"\n- {summary_line}"
            else:
                active_commitments.append(c)

        self.commitments = active_commitments
        return num_to_compact

    def to_dict(self) -> dict[str, Any]:
        return {
            "working_state": self.working_state,
            "recent_events": self.recent_events,
            "long_term_summary": self.long_term_summary,
            "important_facts": self.important_facts,
            "commitments": [c.to_dict() for c in self.commitments],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConsolidatedMemory":
        commitments = [
            Commitment.from_dict(c) for c in data.get("commitments", [])
        ]
        return cls(
            working_state=data.get("working_state", {}),
            recent_events=data.get("recent_events", []),
            long_term_summary=data.get("long_term_summary", ""),
            important_facts=data.get("important_facts", {}),
            commitments=commitments,
        )
