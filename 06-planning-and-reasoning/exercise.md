# Exercise 06: Implement Dependency-Aware DAG Execution and Step Retries

## Goal
Extend the `Plan` and `AdaptivePlanningAgent` in Module 06 by implementing **Dependency-Aware Execution (DAG)** and **Per-Step Retry Limits** before triggering a full replanning cycle.

---

## The Challenge

1. **Add Dependencies to PlanStep**:
   Update `PlanStep` to track prerequisite step IDs:
   ```python
   @dataclass
   class PlanStep:
       step_id: int
       description: str
       tool_name: str
       tool_args: dict[str, Any]
       depends_on: list[int] = field(default_factory=list)
       status: str = "PENDING"  # PENDING, IN_PROGRESS, COMPLETED, FAILED, SKIPPED
       result: Any = None
       error: str | None = None
       retry_count: int = 0
   ```

2. **Implement Dependency Resolution in Plan**:
   Replace simple sequential execution with dependency checking:
   ```python
   def get_executable_steps(self) -> list[PlanStep]:
       """Returns all PENDING steps whose dependencies are all COMPLETED."""
       completed_ids = {s.step_id for s in self.steps if s.status == "COMPLETED"}
       return [
           s for s in self.steps
           if s.status == "PENDING" and all(dep in completed_ids for dep in s.depends_on)
       ]
   ```

3. **Add Step-Level Retry Before Replanning**:
   In `AdaptivePlanningAgent`, distinguish between transient errors (which should be retried up to `max_step_retries`) and structural blockers (which trigger `replan_on_failure`):
   ```python
   if res.get("status") == "error":
       if step.retry_count < self.max_step_retries:
           step.retry_count += 1
           # keep status as PENDING for immediate retry
       else:
           step.status = "FAILED"
           # trigger planner.replan_on_failure(...)
   ```

4. **Block Downstream Steps on Permanent Failure**:
   If a step fails permanently and cannot be replanned, mark all downstream steps that depend on it as `SKIPPED`.

---

## Verification Check

Write a short verification test:
1. Define a 3-step plan where Step 3 depends on Step 2, and Step 2 depends on Step 1.
2. Simulate a transient failure on Step 1 that succeeds on retry 1.
3. Verify that Step 2 only executes after Step 1 completes.
4. Verify that all 3 steps successfully complete.
