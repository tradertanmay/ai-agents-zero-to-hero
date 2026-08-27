"""
Module 04: Build Your First Agent
Runnable Python Demonstration: The Complete End-to-End Agent

This script brings together State, ToolRegistry, DecisionEngine, and Control Loop
in ~140 lines of pure, standard Python 3.11+ (zero dependencies).
"""

from dataclasses import dataclass, field
from typing import Any, Callable
import json
import inspect


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
# 3. Decision Engine (Model Interface)
# ============================================================================

@dataclass
class ModelDecision:
    action_type: str # "tool_call" or "finish"
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    content: str | None = None


class MockLLMDecisionEngine:
    """
    Deterministic model simulator demonstrating multi-step reasoning:
    Goal: "Calculate final bill for customer 'cust_42' on a $250 purchase."
    1. Fetch customer membership tier.
    2. Compute discount amount.
    3. Compute final price.
    4. Return formatted answer.
    """
    def decide(self, state: AgentState, available_tools: list[str]) -> ModelDecision:
        # Check what we have observed so far
        tool_messages = [m for m in state.messages if m.role == "tool"]

        if len(tool_messages) == 0:
            # Step 1: Query customer details
            return ModelDecision(
                action_type="tool_call",
                tool_name="get_customer_info",
                tool_args={"customer_id": "cust_42"},
                content="I need to retrieve the customer's membership tier first."
            )

        if len(tool_messages) == 1:
            # Step 2: Compute discount
            user_data = tool_messages[0].content["result"]
            tier = user_data["tier"] # "gold" -> 20%
            discount_pct = 0.20 if tier == "gold" else 0.05
            return ModelDecision(
                action_type="tool_call",
                tool_name="multiply",
                tool_args={"a": 250.0, "b": discount_pct},
                content=f"Customer tier is {tier} (20% off). Calculating discount on $250."
            )

        if len(tool_messages) == 2:
            # Step 3: Subtract discount from base price
            discount_amount = tool_messages[1].content["result"]
            return ModelDecision(
                action_type="tool_call",
                tool_name="subtract",
                tool_args={"a": 250.0, "b": discount_amount},
                content=f"Discount is ${discount_amount}. Subtracting from base $250."
            )

        if len(tool_messages) == 3:
            # Step 4: Final Answer
            final_price = tool_messages[2].content["result"]
            return ModelDecision(
                action_type="finish",
                content=f"For customer cust_42 (Gold member), the $250 purchase receives a $50 discount (20%), making the final total $200.00."
            )

        return ModelDecision(action_type="finish", content="Completed processing.")


# ============================================================================
# 4. The Complete Agent
# ============================================================================

class Agent:
    def __init__(self, model: MockLLMDecisionEngine, registry: ToolRegistry, max_steps: int = 6) -> None:
        self.model = model
        self.registry = registry
        self.max_steps = max_steps

    def run(self, goal: str) -> str:
        state = AgentState(goal=goal)
        state.messages.append(Message(role="user", content=goal))

        print("=" * 65)
        print(f" AGENT STARTED | Goal: '{goal}'")
        print("=" * 65)

        while not state.is_finished and state.step < self.max_steps:
            state.step += 1
            print(f"\n[Turn {state.step}/{self.max_steps}] Querying Decision Engine...")

            # 1. Model decides next step
            decision = self.model.decide(state, self.registry.get_tool_names())

            if decision.action_type == "finish":
                state.is_finished = True
                state.final_answer = decision.content
                print(f" Model decided to finish!")
                print(f" Final Answer: {decision.content}")
                break

            # 2. Model requested a tool call
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
            print(f" Observation: {observation}")

            # 4. Record tool observation in state
            state.messages.append(Message(
                role="tool",
                name=decision.tool_name,
                content=observation
            ))

        print("\n" + "=" * 65)
        print(f"EXECUTION COMPLETE (Total Steps: {state.step})")
        print("=" * 65)
        return state.final_answer or "Execution ended without terminal answer."


# ============================================================================
# 5. Define Tools & Run
# ============================================================================

def get_customer_info(customer_id: str) -> dict[str, Any]:
    """Retrieve customer tier and account information."""
    database = {
        "cust_42": {"name": "Charlie", "tier": "gold", "joined": "2023"},
        "cust_99": {"name": "Dana", "tier": "standard", "joined": "2024"},
    }
    return database.get(customer_id, {"name": "Unknown", "tier": "none"})


def multiply(a: float, b: float) -> float:
    """Multiplies two numbers."""
    return a * b


def subtract(a: float, b: float) -> float:
    """Subtracts b from a."""
    return a - b


def main() -> None:
    # Setup Registry
    registry = ToolRegistry()
    registry.register(get_customer_info)
    registry.register(multiply)
    registry.register(subtract)

    # Instantiate and Run Agent
    model = MockLLMDecisionEngine()
    agent = Agent(model=model, registry=registry, max_steps=5)
    agent.run(goal="Calculate final bill for customer 'cust_42' on a $250 purchase.")


if __name__ == "__main__":
    main()
