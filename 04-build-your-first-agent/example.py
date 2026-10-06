"""
Module 04: Build Your First Agent
Runnable Python Demonstration: The Complete End-to-End Agent + Early Evaluation

This script brings together State, ToolRegistry, DecisionEngine, Control Loop,
and a 10-Case Regression Scorecard in pure, standard Python 3.11+ (zero dependencies).
"""

from dataclasses import dataclass, field
from typing import Any, Callable
import re


# ============================================================================
# 1. State Representation
# ============================================================================

@dataclass
class Message:
    role: str # "user", "assistant", or "tool"
    content: Any
    name: str | None = None
    tool_call: dict[str, Any] | None = None


@dataclass
class AgentState:
    goal: str
    messages: list[Message] = field(default_factory=list)
    step: int = 0
    is_finished: bool = False
    final_answer: str | None = None


# ============================================================================
# 2. Tool Registry
# ============================================================================

class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, func: Callable[..., Any]) -> None:
        self._tools[func.__name__] = func

    def get_tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def execute(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        if tool_name not in self._tools:
            return {"status": "error", "error": f"Tool '{tool_name}' does not exist."}
        try:
            res = self._tools[tool_name](**args)
            return {"status": "success", "result": res}
        except Exception as e:
            return {"status": "error", "error": str(e)}


# ============================================================================
# 3. Decision Engines (Naive vs. Robust for Before/After Evaluation)
# ============================================================================

@dataclass
class ModelDecision:
    action_type: str # "tool_call" or "finish"
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    content: str | None = None


class NaiveDecisionEngine:
    """
    v1 Model: Naive decision engine.
    Assumes all customers exist in the database and purchase amounts are always valid.
    Fails on edge cases (unknown customer, negative purchase, missing args).
    """
    def decide(self, state: AgentState, available_tools: list[str]) -> ModelDecision:
        tool_messages = [m for m in state.messages if m.role == "tool"]

        # Parse customer_id and amount from goal
        cid_match = re.search(r"customer '([^']+)'", state.goal)
        amt_match = re.search(r"\$([-\d.]+)", state.goal)
        
        cid = cid_match.group(1) if cid_match else "cust_42"
        amt = float(amt_match.group(1)) if amt_match else 250.0

        if len(tool_messages) == 0:
            # Naive: always queries customer info without validating input
            return ModelDecision(
                action_type="tool_call",
                tool_name="get_customer_info",
                tool_args={"customer_id": cid},
                content="Looking up customer tier."
            )

        if len(tool_messages) == 1:
            res = tool_messages[0].content.get("result", {})
            # Naive bug: directly assumes tier exists, does not handle unknown customers
            tier = res.get("tier", "none")
            discount_pct = 0.20 if tier == "gold" else (0.05 if tier == "standard" else 0.0)

            # Naive bug: does not validate negative amount
            return ModelDecision(
                action_type="tool_call",
                tool_name="multiply",
                tool_args={"a": amt, "b": discount_pct},
                content=f"Calculating discount for tier '{tier}'."
            )

        if len(tool_messages) == 2:
            discount_amount = tool_messages[1].content.get("result", 0.0)
            return ModelDecision(
                action_type="tool_call",
                tool_name="subtract",
                tool_args={"a": amt, "b": discount_amount},
                content="Subtracting discount from purchase price."
            )

        if len(tool_messages) == 3:
            final_price = tool_messages[2].content.get("result", amt)
            return ModelDecision(
                action_type="finish",
                content=f"Final bill: ${final_price:.2f}"
            )

        return ModelDecision(action_type="finish", content="Completed processing.")


class RobustDecisionEngine:
    """
    v2 Model: Robust decision engine.
    - Validates inputs before executing actions (rejects negative purchase amounts).
    - Gracefully handles unknown customers (0% discount).
    - Verifies calculations and outputs structured, reliable results.
    """
    def decide(self, state: AgentState, available_tools: list[str]) -> ModelDecision:
        # Extract customer ID and purchase amount from goal
        cid_match = re.search(r"customer '([^']+)'", state.goal)
        amt_match = re.search(r"\$([-\d.]+)", state.goal)

        cid = cid_match.group(1) if cid_match else "unknown"
        amt = float(amt_match.group(1)) if amt_match else 0.0

        # Guardrail 1: Input Validation
        if amt < 0:
            return ModelDecision(
                action_type="finish",
                content="Error: Purchase amount cannot be negative."
            )

        tool_messages = [m for m in state.messages if m.role == "tool"]

        if len(tool_messages) == 0:
            return ModelDecision(
                action_type="tool_call",
                tool_name="get_customer_info",
                tool_args={"customer_id": cid},
                content=f"Retrieving account tier for customer '{cid}'."
            )

        if len(tool_messages) == 1:
            cust_info = tool_messages[0].content.get("result", {})
            tier = cust_info.get("tier", "none")
            
            # Safe tier resolution
            if tier == "gold":
                discount_pct = 0.20
            elif tier == "standard":
                discount_pct = 0.05
            else:
                discount_pct = 0.0 # Unknown or new customer gets no discount

            return ModelDecision(
                action_type="tool_call",
                tool_name="multiply",
                tool_args={"a": amt, "b": discount_pct},
                content=f"Customer tier is '{tier}'. Applying discount rate of {discount_pct*100:.0f}%."
            )

        if len(tool_messages) == 2:
            discount_res = tool_messages[1].content
            discount_amount = discount_res.get("result", 0.0) if discount_res.get("status") == "success" else 0.0
            return ModelDecision(
                action_type="tool_call",
                tool_name="subtract",
                tool_args={"a": amt, "b": discount_amount},
                content=f"Subtracting discount of ${discount_amount:.2f} from total ${amt:.2f}."
            )

        if len(tool_messages) == 3:
            final_res = tool_messages[2].content
            final_total = final_res.get("result", amt) if final_res.get("status") == "success" else amt
            cust_info = tool_messages[0].content.get("result", {})
            name = cust_info.get("name", "Guest")
            tier = cust_info.get("tier", "standard")
            return ModelDecision(
                action_type="finish",
                content=f"Final bill for {name} ({tier.capitalize()} member): ${final_total:.2f}"
            )

        return ModelDecision(action_type="finish", content="Completed processing.")


# Default alias for backwards compatibility
MockLLMDecisionEngine = RobustDecisionEngine


# ============================================================================
# 4. The Complete Agent
# ============================================================================

class Agent:
    def __init__(self, model: Any, registry: ToolRegistry, max_steps: int = 6) -> None:
        self.model = model
        self.registry = registry
        self.max_steps = max_steps

    def run(self, goal: str, verbose: bool = True) -> str:
        state = AgentState(goal=goal)
        state.messages.append(Message(role="user", content=goal))

        if verbose:
            print("=" * 65)
            print(f" AGENT STARTED | Goal: '{goal}'")
            print("=" * 65)

        while not state.is_finished and state.step < self.max_steps:
            state.step += 1
            if verbose:
                print(f"\n[Turn {state.step}/{self.max_steps}] Querying Decision Engine...")

            # 1. Model decides next step
            decision = self.model.decide(state, self.registry.get_tool_names())

            if decision.action_type == "finish":
                state.is_finished = True
                state.final_answer = decision.content
                if verbose:
                    print(f" Model decided to finish!")
                    print(f" Final Answer: {decision.content}")
                break

            # 2. Model requested a tool call
            if verbose:
                print(f" Thought: {decision.content}")
                print(f" Tool Call: {decision.tool_name}({decision.tool_args})")
            
            # Record assistant turn
            state.messages.append(Message(
                role="assistant",
                content=decision.content,
                tool_call={"name": decision.tool_name, "args": decision.tool_args}
            ))

            # 3. Runtime executes tool
            observation = self.registry.execute(decision.tool_name or "", decision.tool_args or {})
            if verbose:
                print(f" Observation: {observation}")

            # 4. Record tool observation in state
            state.messages.append(Message(
                role="tool",
                name=decision.tool_name,
                content=observation
            ))

        if verbose:
            print("\n" + "=" * 65)
            print(f"EXECUTION COMPLETE (Total Steps: {state.step})")
            print("=" * 65)

        return state.final_answer or "Execution ended without terminal answer."


# ============================================================================
# 5. Define Tools
# ============================================================================

def get_customer_info(customer_id: str) -> dict[str, Any]:
    """Retrieve customer tier and account information."""
    database = {
        "cust_42": {"name": "Charlie", "tier": "gold", "joined": "2023"},
        "cust_99": {"name": "Dana", "tier": "standard", "joined": "2024"},
    }
    if customer_id not in database:
        return {"name": "Guest", "tier": "none", "status": "unknown_customer"}
    return database[customer_id]


def multiply(a: float, b: float) -> float:
    """Multiplies two numbers."""
    return a * b


def subtract(a: float, b: float) -> float:
    """Subtracts b from a."""
    return a - b


# ============================================================================
# 6. Early Evaluation: 10-Case Regression Scorecard & Failure Log
# ============================================================================

@dataclass
class TestCase:
    case_id: int
    name: str
    goal: str
    max_steps: int
    expected_keyword: str
    expected_amount: str | None = None
    expected_failure_type: str | None = None


@dataclass
class FailureRecord:
    case_id: int
    name: str
    failure_type: str  # "TOOL_SELECTION_FAILURE", "TOOL_EXECUTION_FAILURE", "INPUT_VALIDATION_FAILURE", "BUDGET_EXCEEDED", "UNEXPECTED_ANSWER"
    step_number: int
    expected: str
    actual: str


@dataclass
class ScorecardResult:
    total: int
    passed: int
    failed: int
    pass_rate: float
    failures: list[FailureRecord]


def build_10_case_battery() -> list[TestCase]:
    """Constructs the standard 10-case evaluation battery."""
    return [
        TestCase(1, "Gold tier standard purchase", "Calculate final bill for customer 'cust_42' on a $250 purchase.", 5, "Gold member", "$200.00"),
        TestCase(2, "Standard tier small purchase", "Calculate final bill for customer 'cust_99' on a $100 purchase.", 5, "Standard member", "$95.00"),
        TestCase(3, "Unknown customer handling", "Calculate final bill for customer 'cust_unknown' on a $100 purchase.", 5, "$100.00", "$100.00"),
        TestCase(4, "Negative purchase rejection", "Calculate final bill for customer 'cust_42' on a $-50 purchase.", 5, "cannot be negative"),
        TestCase(5, "Zero dollar purchase", "Calculate final bill for customer 'cust_42' on a $0 purchase.", 5, "$0.00"),
        TestCase(6, "Step budget limit exhaustion", "Calculate final bill for customer 'cust_42' on a $250 purchase.", 2, "without terminal answer"),
        TestCase(7, "Large enterprise purchase", "Calculate final bill for customer 'cust_42' on a $10000 purchase.", 5, "Gold member", "$8000.00"),
        TestCase(8, "Standard tier medium purchase", "Calculate final bill for customer 'cust_99' on a $500 purchase.", 5, "Standard member", "$475.00"),
        TestCase(9, "Zero discount customer purchase", "Calculate final bill for customer 'cust_00' on a $300 purchase.", 5, "$300.00"),
        TestCase(10, "Decimal purchase precision", "Calculate final bill for customer 'cust_42' on a $125.50 purchase.", 5, "$100.40"),
    ]


class RegressionScorecard:
    """Evaluates an agent across a regression battery and records structured failures."""
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def evaluate(self, model: Any, battery: list[TestCase]) -> ScorecardResult:
        failures: list[FailureRecord] = []
        passed = 0

        for case in battery:
            agent = Agent(model=model, registry=self.registry, max_steps=case.max_steps)
            answer = agent.run(case.goal, verbose=False)

            is_pass = True
            fail_type = ""
            actual_reason = answer

            if case.expected_keyword not in answer:
                is_pass = False
                fail_type = "UNEXPECTED_ANSWER"
                if "cannot be negative" in case.expected_keyword and "$-" in answer:
                    fail_type = "INPUT_VALIDATION_FAILURE"
                elif "without terminal answer" in case.expected_keyword:
                    fail_type = "BUDGET_EXCEEDED"
            elif case.expected_amount and case.expected_amount not in answer:
                is_pass = False
                fail_type = "UNEXPECTED_ANSWER"

            if is_pass:
                passed += 1
            else:
                failures.append(FailureRecord(
                    case_id=case.case_id,
                    name=case.name,
                    failure_type=fail_type or "UNEXPECTED_ANSWER",
                    step_number=case.max_steps,
                    expected=f"{case.expected_keyword} ({case.expected_amount or ''})".strip(),
                    actual=actual_reason
                ))

        total = len(battery)
        return ScorecardResult(
            total=total,
            passed=passed,
            failed=total - passed,
            pass_rate=(passed / total) * 100.0,
            failures=failures
        )


def print_scorecard(title: str, result: ScorecardResult) -> None:
    """Prints a clean ASCII scorecard report."""
    print("\n" + "=" * 65)
    print(f"EVALUATION SCORECARD: {title}")
    print("=" * 65)
    print(f"Total Test Cases: {result.total}")
    print(f"Passed:           {result.passed}")
    print(f"Failed:           {result.failed}")
    print(f"Pass Rate:        {result.pass_rate:.1f}%")
    print("-" * 65)

    if result.failures:
        print("STRUCTURED FAILURE LOG:")
        for f in result.failures:
            print(f"  [Case #{f.case_id}] {f.name}")
            print(f"    Type:     {f.failure_type}")
            print(f"    Expected: {f.expected}")
            print(f"    Actual:   {f.actual}")
    else:
        print("All test cases passed successfully. Zero regression failures.")
    print("=" * 65)


# ============================================================================
# 7. Main Demonstration
# ============================================================================

def main() -> None:
    # 1. Setup Registry
    registry = ToolRegistry()
    registry.register(get_customer_info)
    registry.register(multiply)
    registry.register(subtract)

    # 2. Run Single Agent Demo
    robust_model = RobustDecisionEngine()
    agent = Agent(model=robust_model, registry=registry, max_steps=5)
    agent.run(goal="Calculate final bill for customer 'cust_42' on a $250 purchase.")

    # 3. Run Early Evaluation: Before (Naive v1) vs After (Robust v2)
    battery = build_10_case_battery()
    scorecard = RegressionScorecard(registry=registry)

    naive_model = NaiveDecisionEngine()
    naive_result = scorecard.evaluate(naive_model, battery)
    print_scorecard("Naive Decision Engine (v1 - Before)", naive_result)

    robust_result = scorecard.evaluate(robust_model, battery)
    print_scorecard("Robust Decision Engine (v2 - After)", robust_result)

    # 4. Summary Comparison
    print("\n" + "=" * 65)
    print("BEFORE / AFTER REGRESSION COMPARISON")
    print("=" * 65)
    print(f"  v1 Naive Model:  {naive_result.passed}/{naive_result.total} passed ({naive_result.pass_rate:.1f}%)")
    print(f"  v2 Robust Model: {robust_result.passed}/{robust_result.total} passed ({robust_result.pass_rate:.1f}%)")
    print("Evaluation proves reliability improvements objectively without guessing on 'vibes'!")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
