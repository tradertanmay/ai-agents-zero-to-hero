"""
Autonomy Budget & Execution Limits (Applied Agent Systems: A2)
Enforces rate limits, tool quotas, runtime timeouts, and failure containment
to ensure autonomous agents operate within strict operational boundaries.
Core principle: 'Persistent autonomy requires deterministic resource bounds.'
"""

from dataclasses import dataclass
import time


class BudgetExceededError(Exception):
    """Raised when an autonomy budget quota is exceeded during execution."""
    pass


@dataclass
class AutonomyBudget:
    """Configurable execution constraints per wake cycle."""

    max_steps_per_wake: int = 10
    max_tool_calls_per_wake: int = 20
    max_writes_per_wake: int = 5
    max_runtime_seconds: float = 30.0
    max_consecutive_failures: int = 3


class BudgetTracker:
    """Tracks and validates consumption of autonomy budget for a wake cycle."""

    def __init__(self, budget: AutonomyBudget):
        self.budget = budget
        self.steps_taken: int = 0
        self.tool_calls_made: int = 0
        self.writes_performed: int = 0
        self.start_time: float = time.monotonic()

    def record_step(self) -> None:
        """Increment step count and check budget."""
        self.steps_taken += 1
        if self.steps_taken > self.budget.max_steps_per_wake:
            raise BudgetExceededError(
                f"Exceeded max steps per wake ({self.steps_taken} > {self.budget.max_steps_per_wake})"
            )

    def record_tool_call(self) -> None:
        """Increment tool call count and check budget."""
        self.tool_calls_made += 1
        if self.tool_calls_made > self.budget.max_tool_calls_per_wake:
            raise BudgetExceededError(
                f"Exceeded max tool calls per wake ({self.tool_calls_made} > {self.budget.max_tool_calls_per_wake})"
            )

    def record_write(self) -> None:
        """Increment external write action count and check budget."""
        self.writes_performed += 1
        if self.writes_performed > self.budget.max_writes_per_wake:
            raise BudgetExceededError(
                f"Exceeded max writes per wake ({self.writes_performed} > {self.budget.max_writes_per_wake})"
            )

    def is_runtime_exceeded(self) -> bool:
        """Check if elapsed time exceeds runtime budget."""
        elapsed = time.monotonic() - self.start_time
        return elapsed > self.budget.max_runtime_seconds

    def check_health(self) -> tuple[bool, str]:
        """Verify all budget metrics remain within allowed boundaries."""
        if self.is_runtime_exceeded():
            return False, "Runtime timeout exceeded"
        if self.steps_taken >= self.budget.max_steps_per_wake:
            return False, "Max steps exhausted"
        if self.writes_performed >= self.budget.max_writes_per_wake:
            return False, "Max writes exhausted"
        return True, "Within budget"
