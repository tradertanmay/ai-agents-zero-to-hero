"""
Wake Scheduler & Reactivation Planning (Applied Agent Systems: A2)
Calculates scheduled wake times, exponential backoff on consecutive failures,
and determines reactivation readiness.
Core principle: 'Persistence is not busy-waiting; it is sleeping until reactivation is due.'
"""

from datetime import datetime, timedelta, timezone


class WakeScheduler:
    """Computes and tracks scheduled reactivation intervals with backoff support."""

    def __init__(
        self,
        base_interval_seconds: int = 3600,
        max_backoff_seconds: int = 86400,
        jitter_seconds: int = 0,
    ):
        self.base_interval_seconds = base_interval_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.jitter_seconds = jitter_seconds

    def compute_next_wake(
        self,
        consecutive_failures: int = 0,
        base_time: datetime | None = None,
    ) -> datetime:
        """
        Compute the next scheduled wake timestamp.
        Applies exponential backoff if consecutive failures > 0.
        """
        now = base_time or datetime.now(timezone.utc)
        if consecutive_failures <= 0:
            delay = self.base_interval_seconds
        else:
            exponent = min(consecutive_failures, 6)
            delay = min(
                self.base_interval_seconds * (2 ** exponent),
                self.max_backoff_seconds,
            )

        delay += self.jitter_seconds
        return now + timedelta(seconds=delay)

    def is_due(
        self,
        next_wake_iso: str | None,
        current_time: datetime | None = None,
    ) -> bool:
        """Check whether the agent is due for a scheduled wake."""
        if not next_wake_iso:
            return True
        now = current_time or datetime.now(timezone.utc)
        try:
            wake_time = datetime.fromisoformat(next_wake_iso)
            return now >= wake_time
        except ValueError:
            return True
