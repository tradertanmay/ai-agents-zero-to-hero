"""
Minimal Agent Showcase Entry Point
examples/minimal_agent/main.py

Usage:
    python examples/minimal_agent/main.py
"""

import os
import sys

# Ensure parent directory is in sys.path when run directly
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from llm import MockLLM, OpenAIAdapter, AnthropicAdapter, GeminiAdapter, OllamaAdapter
from tools import ToolRegistry, get_weather, calculate_discount
from runtime import AgentRuntime
from agent import Agent


def main() -> None:
    print("=" * 70)
    print(" MINIMAL AGENT SHOWCASE (Zero Dependencies / Python 3.11+)")
    print("=" * 70)

    # 1. Initialize Tool Registry
    registry = ToolRegistry()
    registry.register(get_weather)
    registry.register(calculate_discount)

    # 2. Select Decision Engine (MockLLM default; zero API keys required!)
    # To use a real provider, simply swap the line below:
    # llm = OpenAIAdapter(api_key="your-key")
    # llm = AnthropicAdapter(api_key="your-key")
    # llm = GeminiAdapter(api_key="your-key")
    # llm = OllamaAdapter(model_name="llama3")
    llm = MockLLM()

    # 3. Create Runtime Harness with Step Limit
    runtime = AgentRuntime(max_steps=5, timeout_seconds=5.0)

    # 4. Instantiate Agent
    agent = Agent(llm=llm, registry=registry, runtime=runtime)

    # 5. Execute Goal
    goal = "Check the weather in Seattle and calculate the total for a $100 VIP order."
    print(f"\nUser Goal: '{goal}'\n")

    result = agent.run(goal)

    print("\n" + "-" * 70)
    print(" FINAL AGENT RESPONSE:")
    print(result)
    print("-" * 70)

    print("\n EXECUTION TRAJECTORY:")
    for step in runtime.trajectory:
        print(
            f" [Step {step.step}] Action={step.decision_type:<10} "
            f"Tool={str(step.tool_name):<18} "
            f"Duration={step.duration_ms:>6.2f}ms"
        )
        if step.tool_result:
            print(f" Output -> {step.tool_result}")
    print("=" * 70)


if __name__ == "__main__":
    main()
