"""
Module 01: What Is an AI Agent?
Runnable Python Demonstration: Chatbot vs Workflow vs Agent

This script demonstrates the architectural differences between:
1. A Stateless LLM / Prompt
2. A Multi-Turn Chatbot
3. A Deterministic Workflow
4. A Dynamic Closed-Loop Agent
"""

from dataclasses import dataclass, field
from typing import Any, Callable


# ============================================================================
# 0. Simulated Environment & Mock Knowledge
# ============================================================================

DATABASE = {
    "user_101": {"name": "Alice", "plan": "premium", "balance": 150},
    "user_102": {"name": "Bob", "plan": "basic", "balance": 20},
}


def query_database(user_id: str) -> dict[str, Any]:
    """Simulated environment tool: Fetch user record from database."""
    print(f" [Environment] Querying database for {user_id}...")
    if user_id in DATABASE:
        return {"status": "success", "data": DATABASE[user_id]}
    return {"status": "error", "message": f"User {user_id} not found"}


def calculate_discount(plan: str, balance: float) -> float:
    """Simulated environment tool: Calculate discount rate."""
    print(f" [Environment] Calculating discount for plan='{plan}', balance={balance}...")
    if plan == "premium":
        return balance * 0.20
    return balance * 0.05


# ============================================================================
# 1. Paradigm 1: Stateless LLM (No memory, no environment access)
# ============================================================================

def run_stateless_llm(prompt: str) -> str:
    print("\n--- Paradigm 1: Stateless LLM ---")
    print(f"Input Prompt: {prompt}")
    # A stateless model cannot query real-time systems without an environment interface.
    simulated_response = (
        "I cannot look up Alice's live balance because I do not have access "
        "to your external database."
    )
    print(f"Response: {simulated_response}")
    return simulated_response


# ============================================================================
# 2. Paradigm 2: Chatbot (Conversational history, but no tools/actions)
# ============================================================================

class Chatbot:
    def __init__(self) -> None:
        self.history: list[dict[str, str]] = []

    def reply(self, user_message: str) -> str:
        self.history.append({"role": "user", "content": user_message})
        # The chatbot preserves history across turns, but still cannot act on the world
        response = f"I hear you asking about '{user_message}'. However, I cannot interact with external systems."
        self.history.append({"role": "assistant", "content": response})
        return response


# ============================================================================
# 3. Paradigm 3: Deterministic Workflow (Hardcoded pipeline)
# ============================================================================

def run_deterministic_workflow(user_id: str) -> dict[str, Any]:
    print("\n--- Paradigm 3: Deterministic Workflow ---")
    print(f"Goal: Compute discount for {user_id} (Fixed 2-step pipeline)")
    
    # Step 1: Always query database
    record = query_database(user_id)
    if record["status"] != "success":
        return {"error": record["message"]}
    
    # Step 2: Always calculate discount
    user_data = record["data"]
    discount = calculate_discount(user_data["plan"], user_data["balance"])
    
    result = {"user": user_data["name"], "discount": discount}
    print(f"Workflow Result: {result}")
    return result


# ============================================================================
# 4. Paradigm 4: Dynamic Agent (Closed-Loop Observe-Decide-Act)
# ============================================================================

@dataclass
class AgentAction:
    tool_name: str
    tool_args: dict[str, Any]
    is_terminal: bool = False
    final_answer: str | None = None


class SimpleAgent:
    """
    Demonstrates the fundamental agent architecture:
    Agent = Model (Decision Engine) + Control Loop + Environment
    """
    def __init__(self, tools: dict[str, Callable[..., Any]]) -> None:
        self.tools = tools
        self.trajectory: list[dict[str, Any]] = []

    def _simulated_model_decision(self, goal: str, observations: list[dict[str, Any]]) -> AgentAction:
        """
        Simulates an LLM inspecting observations and dynamically deciding the next step.
        """
        # Step 0: Initial observation -> Need user data
        if not observations:
            return AgentAction(
                tool_name="query_database",
                tool_args={"user_id": "user_101"}
            )
        
        last_obs = observations[-1]
        
        # Step 1: If database returned user info -> Decide to calculate discount
        if last_obs["tool"] == "query_database" and last_obs["result"]["status"] == "success":
            user_data = last_obs["result"]["data"]
            return AgentAction(
                tool_name="calculate_discount",
                tool_args={"plan": user_data["plan"], "balance": user_data["balance"]}
            )
        
        # Step 2: If discount calculated -> Decide we have enough information to answer
        if last_obs["tool"] == "calculate_discount":
            discount = last_obs["result"]
            return AgentAction(
                tool_name="finish",
                tool_args={},
                is_terminal=True,
                final_answer=f"Alice has a discount of ${discount:.2f} based on her premium plan."
            )
        
        # Fallback termination
        return AgentAction(
            tool_name="finish",
            tool_args={},
            is_terminal=True,
            final_answer="Unable to complete task."
        )

    def run(self, goal: str, max_steps: int = 5) -> str:
        print(f"\n--- Paradigm 4: Dynamic Agent Loop ---")
        print(f"Goal: {goal}")
        
        observations: list[dict[str, Any]] = []
        step = 0

        # The Control Loop (Observe -> Decide -> Act -> Observe)
        while step < max_steps:
            step += 1
            print(f"\n[Step {step}] Observing state and deciding action...")
            
            # 1. Decide: Model reasons over current observations
            action = self._simulated_model_decision(goal, observations)
            
            # 2. Check Termination Condition
            if action.is_terminal:
                print(f"[Agent Finished] {action.final_answer}")
                return action.final_answer or ""
            
            # 3. Act: Runtime executes the selected tool in the environment
            print(f"[Action] Calling tool '{action.tool_name}' with args {action.tool_args}")
            tool_func = self.tools.get(action.tool_name)
            if not tool_func:
                obs_result = {"status": "error", "message": f"Tool {action.tool_name} not found"}
            else:
                obs_result = tool_func(**action.tool_args)
            
            # 4. Observe: Record environment feedback for the next turn
            print(f"[Observation] Received: {obs_result}")
            observations.append({
                "step": step,
                "tool": action.tool_name,
                "args": action.tool_args,
                "result": obs_result
            })
            self.trajectory = observations

        return "Exceeded maximum execution steps."


# ============================================================================
# Main Execution Entry Point
# ============================================================================

def main() -> None:
    # 1. Stateless Prompt
    run_stateless_llm("What is Alice's discount?")

    # 2. Chatbot
    print("\n--- Paradigm 2: Multi-Turn Chatbot ---")
    bot = Chatbot()
    print("Turn 1:", bot.reply("Hi, can you calculate Alice's discount?"))
    print("Turn 2:", bot.reply("Her user ID is user_101."))

    # 3. Deterministic Workflow
    run_deterministic_workflow("user_101")

    # 4. Dynamic Agent
    tools = {
        "query_database": query_database,
        "calculate_discount": calculate_discount,
    }
    agent = SimpleAgent(tools=tools)
    agent.run(goal="Find user_101 and determine their discount.")


if __name__ == "__main__":
    main()
