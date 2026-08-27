"""
Module 08: Agent Runtime and Harness
Runnable Python Demonstration: The Production-Style Agent Harness

This script demonstrates an agent harness that enforces execution budgets,
tool permission gates, middleware interceptors, and trajectory logging
using only Python 3.11+ standard library.
"""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Callable


# ============================================================================
# 1. Harness Configuration & Budget Objects
# ============================================================================

class ExecutionStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    BUDGET_EXCEEDED = "budget_exceeded"
    PERMISSION_DENIED = "permission_denied"
    FAILED = "failed"


@dataclass
class ExecutionBudget:
    max_steps: int = 5
    max_time_seconds: float = 2.0
    max_cost_usd: float = 0.10
    step_cost_usd: float = 0.01 # Simulated cost per LLM call


@dataclass
class TrajectoryStep:
    step_number: int
    timestamp: float
    decision_type: str
    tool_name: str | None
    tool_args: dict[str, Any] | None
    tool_result: dict[str, Any] | None
    duration_ms: float
    cost_usd: float


# ============================================================================
# 2. Tool Registry with Permission Levels
# ============================================================================

class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}
        self._permissions: dict[str, str] = {} # tool_name -> "read" | "write" | "admin"

    def register(self, func: Callable[..., Any], permission_level: str = "read") -> None:
        name = func.__name__
        self._tools[name] = func
        self._permissions[name] = permission_level

    def get_permission_level(self, tool_name: str) -> str | None:
        return self._permissions.get(tool_name)

    def execute(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        if tool_name not in self._tools:
            return {"status": "error", "error": f"Tool '{tool_name}' not found."}
        try:
            res = self._tools[tool_name](**args)
            return {"status": "success", "result": res}
        except Exception as e:
            return {"status": "error", "error": f"Tool execution failed: {str(e)}"}


# ============================================================================
# 3. Decision Model Simulator
# ============================================================================

@dataclass
class Action:
    type: str # "tool_call" or "finish"
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    answer: str | None = None


class DecisionEngine:
    def __init__(self, script: list[Action]) -> None:
        self._script = script
        self._index = 0

    def decide(self, state: list[dict[str, Any]]) -> Action:
        if self._index < len(self._script):
            action = self._script[self._index]
            self._index += 1
            return action
        return Action(type="finish", answer="No more scripted actions.")


# ============================================================================
# 4. The Agent Runtime Harness
# ============================================================================

class AgentHarness:
    """
    The Operating System for Agent Execution.
    Owns execution control, limits, permissions, middleware, and telemetry.
    """
    def __init__(
        self,
        registry: ToolRegistry,
        budget: ExecutionBudget,
        allowed_permissions: set[str] | None = None
    ) -> None:
        self.registry = registry
        self.budget = budget
        self.allowed_permissions = allowed_permissions or {"read", "write"}
        self.trajectory: list[TrajectoryStep] = []
        self.total_cost: float = 0.0

    def run(self, goal: str, model: DecisionEngine) -> dict[str, Any]:
        start_time = time.perf_counter()
        state: list[dict[str, Any]] = [{"role": "user", "goal": goal}]
        step_count = 0
        final_answer: str | None = None
        status = ExecutionStatus.RUNNING

        print("\n" + "=" * 65)
        print(f" HARNESS STARTED | Goal: '{goal}'")
        print(f" Limits: MaxSteps={self.budget.max_steps}, MaxTime={self.budget.max_time_seconds}s, MaxCost=${self.budget.max_cost_usd}")
        print("=" * 65)

        while status == ExecutionStatus.RUNNING:
            step_count += 1
            step_start = time.perf_counter()

            # --- 1. BUDGET GATE CHECKS ---
            elapsed_total = time.perf_counter() - start_time
            if step_count > self.budget.max_steps:
                print(f" [Budget Tripwire] Reached step limit ({self.budget.max_steps}). Aborting.")
                status = ExecutionStatus.BUDGET_EXCEEDED
                break

            if elapsed_total > self.budget.max_time_seconds:
                print(f" [Budget Tripwire] Reached time limit ({self.budget.max_time_seconds}s). Aborting.")
                status = ExecutionStatus.BUDGET_EXCEEDED
                break

            if self.total_cost + self.budget.step_cost_usd > self.budget.max_cost_usd:
                print(f" [Budget Tripwire] Reached cost limit (${self.budget.max_cost_usd}). Aborting.")
                status = ExecutionStatus.BUDGET_EXCEEDED
                break

            # Deduct simulated step cost
            self.total_cost += self.budget.step_cost_usd

            # --- 2. MODEL INFERENCE ---
            action = model.decide(state)
            print(f"\n[Step {step_count}] Model Decision: {action.type} -> {action.tool_name or action.answer}")

            # --- 3. TERMINATION CHECK ---
            if action.type == "finish":
                final_answer = action.answer
                status = ExecutionStatus.COMPLETED
                duration_ms = (time.perf_counter() - step_start) * 1000
                self._record_step(step_count, action, None, duration_ms)
                break

            # --- 4. PERMISSION & SAFETY GATES ---
            tool_name = action.tool_name or ""
            perm_level = self.registry.get_permission_level(tool_name)
            
            if perm_level not in self.allowed_permissions:
                print(f" [Security Gate] Tool '{tool_name}' requires '{perm_level}' permission. Denied!")
                tool_result = {
                    "status": "error",
                    "error": f"PermissionDenied: Current user session lacks '{perm_level}' permissions."
                }
            else:
                # --- 5. EXECUTION IN RUNTIME ---
                tool_result = self.registry.execute(tool_name, action.tool_args or {})
                print(f" [Execution] Result: {tool_result}")

            # --- 6. RECORD TELEMETRY ---
            duration_ms = (time.perf_counter() - step_start) * 1000
            self._record_step(step_count, action, tool_result, duration_ms)

            # Update State
            state.append({
                "step": step_count,
                "action": action.tool_name,
                "args": action.tool_args,
                "result": tool_result
            })

        total_duration = time.perf_counter() - start_time
        return {
            "status": status.value,
            "final_answer": final_answer,
            "total_steps": step_count,
            "total_duration_seconds": round(total_duration, 4),
            "total_cost_usd": round(self.total_cost, 4),
            "trajectory_count": len(self.trajectory)
        }

    def _record_step(
        self,
        step: int,
        action: Action,
        result: dict[str, Any] | None,
        duration_ms: float
    ) -> None:
        self.trajectory.append(TrajectoryStep(
            step_number=step,
            timestamp=time.time(),
            decision_type=action.type,
            tool_name=action.tool_name,
            tool_args=action.tool_args,
            tool_result=result,
            duration_ms=round(duration_ms, 2),
            cost_usd=self.budget.step_cost_usd
        ))


# ============================================================================
# 5. Example Demonstration Scenarios
# ============================================================================

def read_file(filepath: str) -> str:
    """Read contents of a file."""
    return f"Contents of {filepath}: [Config Data: OK]"


def delete_database_table(table_name: str) -> str:
    """Dangerous admin tool."""
    return f"Table {table_name} permanently deleted."


def main() -> None:
    # Setup Tool Registry with Permission Levels
    registry = ToolRegistry()
    registry.register(read_file, permission_level="read")
    registry.register(delete_database_table, permission_level="admin")

    # -------------------------------------------------------------
    # Scenario A: Standard Execution under normal budget
    # -------------------------------------------------------------
    print("\n--- SCENARIO A: Normal Successful Execution ---")
    script_a = [
        Action(type="tool_call", tool_name="read_file", tool_args={"filepath": "app.conf"}),
        Action(type="finish", answer="Configuration loaded successfully.")
    ]
    harness_a = AgentHarness(registry, ExecutionBudget(max_steps=5))
    result_a = harness_a.run("Load app configuration", DecisionEngine(script_a))
    print(f"Summary: {result_a}")

    # -------------------------------------------------------------
    # Scenario B: Permission Gate Blocking Admin Tool
    # -------------------------------------------------------------
    print("\n--- SCENARIO B: Security Gate Blocks Dangerous Action ---")
    script_b = [
        Action(type="tool_call", tool_name="delete_database_table", tool_args={"table_name": "users"}),
        Action(type="finish", answer="Recovery completed.")
    ]
    # Restrict permissions to read-only
    harness_b = AgentHarness(registry, ExecutionBudget(max_steps=5), allowed_permissions={"read"})
    result_b = harness_b.run("Clean up database", DecisionEngine(script_b))
    print(f"Summary: {result_b}")

    # -------------------------------------------------------------
    # Scenario C: Step Limit Tripwire Stopping Infinite Loop
    # -------------------------------------------------------------
    print("\n--- SCENARIO C: Budget Tripwire Halts Infinite Loop ---")
    infinite_script = [
        Action(type="tool_call", tool_name="read_file", tool_args={"filepath": "data.csv"})
        for _ in range(10)
    ]
    harness_c = AgentHarness(registry, ExecutionBudget(max_steps=3))
    result_c = harness_c.run("Process massive stream", DecisionEngine(infinite_script))
    print(f"Summary: {result_c}")


if __name__ == "__main__":
    main()
