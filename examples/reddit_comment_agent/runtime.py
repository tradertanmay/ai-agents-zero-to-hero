"""
Agent Runtime & Safety Harness (Module 08 Application)
Supervises execution boundaries: step limits, comment rate limits,
tripwires, and structured trajectory logging.
"""

from dataclasses import dataclass, field
import time
from typing import Any


@dataclass
class RuntimeBudget:
    """Operational limits governing agent execution safety."""
    max_steps_per_post: int = 8
    max_daily_comments: int = 5
    min_delay_between_actions: float = 0.0  # seconds (rate limit buffer)


@dataclass
class TrajectoryStep:
    step_num: int
    post_id: str | None
    action_name: str
    action_args: dict[str, Any]
    result_status: str
    details: str
    timestamp: float = field(default_factory=time.time)


class AgentRuntime:
    """The operating system harness governing the Reddit Comment Agent."""

    def __init__(self, budget: RuntimeBudget | None = None) -> None:
        self.budget = budget or RuntimeBudget()
        self.trajectory: list[TrajectoryStep] = []
        self.action_count = 0
        self.total_comments_submitted = 0

    def check_can_comment(self) -> tuple[bool, str]:
        """Tripwire preventing spam or runaway comment generation."""
        if self.total_comments_submitted >= self.budget.max_daily_comments:
            return False, f"TripwireTriggered: Reached maximum daily comments limit ({self.budget.max_daily_comments})."
        return True, ""

    def log_step(
        self,
        step_num: int,
        post_id: str | None,
        action_name: str,
        action_args: dict[str, Any],
        result_status: str,
        details: str,
    ) -> None:
        step = TrajectoryStep(
            step_num=step_num,
            post_id=post_id,
            action_name=action_name,
            action_args=action_args,
            result_status=result_status,
            details=details,
        )
        self.trajectory.append(step)
        self.action_count += 1

        if action_name == "submit_comment" and result_status == "success":
            self.total_comments_submitted += 1

        if self.budget.min_delay_between_actions > 0:
            time.sleep(self.budget.min_delay_between_actions)

    def print_summary(self) -> None:
        print("\n" + "=" * 65)
        print("AGENT RUNTIME HARNESS EXECUTION SUMMARY")
        print("=" * 65)
        print(f"Total Trajectory Steps Recorded: {len(self.trajectory)}")
        print(f"Total Comments Submitted: {self.total_comments_submitted} / {self.budget.max_daily_comments}")
        print("-" * 65)
        for s in self.trajectory:
            print(f"  Step {s.step_num:02d} | [{s.action_name:<16}] Status={s.result_status:<7} | {s.details[:50]}")
        print("=" * 65 + "\n")
