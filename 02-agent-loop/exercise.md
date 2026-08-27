# Exercise 02: Cycle Detection & Guardrails

## Goal
Enhance the agent loop to detect **repetitive action loops** (e.g. oscillating between `move_left` and `move_right` or repeatedly executing a failing action) and terminate gracefully with a diagnostic alert.

---

## The Challenge

In `example.py`, if the decision engine made an error and started oscillating between `move_left` and `move_right`, the loop would blindly burn through all remaining step budget before halting.

Your task:
1. Implement a `CycleDetector` helper class or function that tracks the last $N$ actions.
2. If the same action or exact action sequence repeats $K$ times without progress (observation state unchanged), trigger an **ABORT: Loop Lock Detected** termination condition.

---

## Starter Template

```python
class LoopGuard:
    def __init__(self, max_consecutive_failures: int = 2) -> None:
        self.failure_count = 0

    def record_step(self, action_name: str, result: dict) -> bool:
        """
        Returns True if execution should continue, or False if a loop lock is detected.
        """
        if not result.get("success", True):
            self.failure_count += 1
            if self.failure_count >= self.max_consecutive_failures:
                return False # Trigger tripwire
        else:
            self.failure_count = 0
        return True
```

---

## Verification Check
1. Modify `ExplorationWorld` so that the door cannot be unlocked.
2. Run the loop with your `LoopGuard`.
3. Verify that the agent halts after 2 failed attempts rather than burning the full 10-step budget.
