"""
Module 06: Planning and Reasoning
Runnable Python Demonstration: Plan-and-Execute with Dynamic Replanning

This script demonstrates structured planning and runtime failure recovery
in pure standard Python 3.11+ (zero dependencies).
"""

from dataclasses import dataclass, field
from typing import Any, Callable


# ============================================================================
# 1. Plan Representation
# ============================================================================

@dataclass
class PlanStep:
    step_id: int
    description: str
    tool_name: str
    tool_args: dict[str, Any]
    status: str = "PENDING"  # "PENDING", "IN_PROGRESS", "COMPLETED", "FAILED"
    result: Any = None
    error: str | None = None


@dataclass
class Plan:
    goal: str
    steps: list[PlanStep] = field(default_factory=list)

    @property
    def is_finished(self) -> bool:
        return all(s.status == "COMPLETED" for s in self.steps)

    @property
    def next_pending_step(self) -> PlanStep | None:
        for s in self.steps:
            if s.status == "PENDING":
                return s
        return None


# ============================================================================
# 2. Tool Registry & Simulated Deployment Environment
# ============================================================================

class DeploymentEnvironment:
    """Simulates an infrastructure environment with a port conflict bug."""
    def __init__(self, simulate_port_conflict: bool = True) -> None:
        self.port_conflict = simulate_port_conflict
        self.conflicting_pid = 4102 if simulate_port_conflict else None
        self.deployed = False
        self.notified = False

    def check_git_status(self) -> dict[str, Any]:
        return {"clean": True, "branch": "main", "commit": "a1b2c3d"}

    def deploy_service(self, port: int) -> dict[str, Any]:
        if self.port_conflict and self.conflicting_pid:
            return {
                "status": "error",
                "error": f"PortConflictError: Port {port} already bound by process PID {self.conflicting_pid}."
            }
        self.deployed = True
        return {"status": "success", "port": port, "service_id": "srv_auth_prod"}

    def kill_process(self, pid: int) -> dict[str, Any]:
        if pid == self.conflicting_pid:
            self.conflicting_pid = None
            self.port_conflict = False
            return {"status": "success", "message": f"Process {pid} terminated."}
        return {"status": "error", "error": f"Process {pid} not found."}

    def health_check(self, port: int) -> dict[str, Any]:
        if not self.deployed or self.port_conflict:
            return {"status": "error", "error": "Service unreachable"}
        return {"status": "healthy", "latency_ms": 14, "http_code": 200}

    def notify_team(self, channel: str, message: str) -> dict[str, Any]:
        self.notified = True
        return {"status": "success", "channel": channel, "delivered": True}


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, func: Callable[..., Any]) -> None:
        self._tools[name] = func

    def execute(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name not in self._tools:
            return {"status": "error", "error": f"Tool '{name}' not found."}
        try:
            res = self._tools[name](**args)
            if isinstance(res, dict) and "status" in res:
                return res
            return {"status": "success", "result": res}
        except Exception as e:
            return {"status": "error", "error": str(e)}


# ============================================================================
# 3. Planner & Replanner Engine
# ============================================================================

class Planner:
    """Generates initial decomposition and dynamically recalculates plans on error."""
    def create_initial_plan(self, goal: str) -> Plan:
        # High-level decomposition of deployment workflow
        steps = [
            PlanStep(1, "Verify git repository status", "check_git_status", {}),
            PlanStep(2, "Deploy service to production port 8080", "deploy_service", {"port": 8080}),
            PlanStep(3, "Verify HTTP health check endpoint", "health_check", {"port": 8080}),
            PlanStep(4, "Broadcast deployment notification to Slack", "notify_team", {
                "channel": "#devops",
                "message": "Auth service deployed and healthy."
            }),
        ]
        return Plan(goal=goal, steps=steps)

    def replan_on_failure(self, plan: Plan, failed_step: PlanStep, error_info: str) -> Plan:
        """
        Inspects runtime failure and dynamically injects remediation steps
        before continuing the remainder of the plan.
        """
        print(f"\n[REPLANNER ENGAGED] Analyzing failure in Step {failed_step.step_id}: {error_info}")

        if "PortConflictError" in error_info and "PID 4102" in error_info:
            print("[REPLANNER DIAGNOSIS] Detected zombie process holding port 8080. Injecting process termination step.")
            
            # Keep completed steps intact
            completed_steps = [s for s in plan.steps if s.status == "COMPLETED"]
            
            # Synthesize remediation steps + remaining pending steps
            recovery_steps = [
                PlanStep(
                    step_id=201,
                    description="Terminate conflicting zombie process PID 4102",
                    tool_name="kill_process",
                    tool_args={"pid": 4102}
                ),
                PlanStep(
                    step_id=202,
                    description="Retry deployment to production port 8080",
                    tool_name="deploy_service",
                    tool_args={"port": 8080}
                ),
                PlanStep(
                    step_id=3,
                    description="Verify HTTP health check endpoint",
                    tool_name="health_check",
                    tool_args={"port": 8080}
                ),
                PlanStep(
                    step_id=4,
                    description="Broadcast deployment notification to Slack",
                    tool_name="notify_team",
                    tool_args={
                        "channel": "#devops",
                        "message": "Auth service deployed after automatic process conflict recovery."
                    }
                ),
            ]
            return Plan(goal=plan.goal, steps=completed_steps + recovery_steps)

        # Fallback if error is unrecoverable
        return plan


# ============================================================================
# 4. Agents: Rigid vs. Adaptive Replanning
# ============================================================================

class RigidPlannerAgent:
    """Executes an upfront plan blindly without runtime replanning."""
    def __init__(self, planner: Planner, registry: ToolRegistry) -> None:
        self.planner = planner
        self.registry = registry

    def run(self, goal: str) -> tuple[bool, str]:
        plan = self.planner.create_initial_plan(goal)
        print(f"Rigid Agent created {len(plan.steps)}-step upfront plan.")

        while not plan.is_finished:
            step = plan.next_pending_step
            if not step:
                break

            step.status = "IN_PROGRESS"
            res = self.registry.execute(step.tool_name, step.tool_args)

            if res.get("status") == "error":
                step.status = "FAILED"
                step.error = res.get("error")
                return False, f"Rigid execution aborted at Step {step.step_id} ({step.description}): {step.error}"

            step.status = "COMPLETED"
            step.result = res

        return True, "Deployment completed successfully."


class AdaptivePlanningAgent:
    """Executes plan with dynamic reconciliation and replanning upon error."""
    def __init__(self, planner: Planner, registry: ToolRegistry, max_replans: int = 2) -> None:
        self.planner = planner
        self.registry = registry
        self.max_replans = max_replans

    def run(self, goal: str) -> tuple[bool, str]:
        plan = self.planner.create_initial_plan(goal)
        replan_count = 0

        print(f"Adaptive Agent created initial {len(plan.steps)}-step plan:")
        for s in plan.steps:
            print(f"  Step {s.step_id}: {s.description} -> {s.tool_name}()")

        while not plan.is_finished:
            step = plan.next_pending_step
            if not step:
                break

            step.status = "IN_PROGRESS"
            print(f"\n[Executing Step {step.step_id}] {step.description}...")
            res = self.registry.execute(step.tool_name, step.tool_args)

            if res.get("status") == "error":
                step.status = "FAILED"
                step.error = res.get("error", "Unknown error")
                print(f"  Result: FAILED -> {step.error}")

                if replan_count < self.max_replans:
                    replan_count += 1
                    plan = self.planner.replan_on_failure(plan, step, step.error)
                    continue
                else:
                    return False, f"Execution failed after exhausting replan budget ({self.max_replans})."

            step.status = "COMPLETED"
            step.result = res
            print(f"  Result: SUCCESS -> {res}")

        return True, "Deployment succeeded! All steps verified healthy."


# ============================================================================
# 5. Demonstration & Comparison
# ============================================================================

def setup_registry(env: DeploymentEnvironment) -> ToolRegistry:
    reg = ToolRegistry()
    reg.register("check_git_status", env.check_git_status)
    reg.register("deploy_service", env.deploy_service)
    reg.register("kill_process", env.kill_process)
    reg.register("health_check", env.health_check)
    reg.register("notify_team", env.notify_team)
    return reg


def main() -> None:
    print("=" * 65)
    print("DEMO: PLAN-AND-EXECUTE WITH DYNAMIC REPLANNING")
    print("=" * 65)

    goal = "Deploy auth service to port 8080 and verify health."

    # ------------------------------------------------------------------------
    # Part 1: Rigid Planning (Crashes on Unexpected Environment Obstacle)
    # ------------------------------------------------------------------------
    print("\n--- [SCENARIO 1] Rigid Plan-and-Execute (No Replanning) ---")
    env_rigid = DeploymentEnvironment(simulate_port_conflict=True)
    reg_rigid = setup_registry(env_rigid)
    planner = Planner()
    rigid_agent = RigidPlannerAgent(planner, reg_rigid)

    success_1, msg_1 = rigid_agent.run(goal)
    print(f"Status: Success={success_1}")
    print(f"Outcome: {msg_1}")

    # ------------------------------------------------------------------------
    # Part 2: Adaptive Planning (Dynamic Error Recovery & Replanning)
    # ------------------------------------------------------------------------
    print("\n" + "-" * 65)
    print("--- [SCENARIO 2] Adaptive Planning (Dynamic Replanning) ---")
    print("-" * 65)
    env_adaptive = DeploymentEnvironment(simulate_port_conflict=True)
    reg_adaptive = setup_registry(env_adaptive)
    adaptive_agent = AdaptivePlanningAgent(planner, reg_adaptive)

    success_2, msg_2 = adaptive_agent.run(goal)
    print("\n" + "=" * 65)
    print(f"FINAL OUTCOME: Success={success_2}")
    print(f"Summary: {msg_2}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
