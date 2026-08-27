"""
Tests for Flagship Showcase: examples/minimal_agent
"""

import unittest
import os
import sys
import time

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
example_dir = os.path.join(root_dir, "examples", "minimal_agent")
if example_dir not in sys.path:
    sys.path.insert(0, example_dir)

from llm import MockLLM, BaseLLM, LLMResponse
from tools import ToolRegistry, get_weather, calculate_discount
from runtime import AgentRuntime
from agent import Agent


class TestMinimalAgent(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(get_weather)
        self.registry.register(calculate_discount)
        self.llm = MockLLM()

    def test_minimal_agent_end_to_end(self):
        runtime = AgentRuntime(max_steps=5)
        agent = Agent(llm=self.llm, registry=self.registry, runtime=runtime)
        
        goal = "Check the weather in Seattle and calculate the total for a $100 VIP order."
        result = agent.run(goal)
        
        # Verify the final response
        self.assertIn("Seattle", result)
        self.assertIn("14°C", result)
        self.assertIn("$75.00", result) # $100 - $25 VIP discount = $75.00
        
        # Verify trajectory logs
        self.assertEqual(len(runtime.trajectory), 3)
        self.assertEqual(runtime.trajectory[0].tool_name, "get_weather")
        self.assertEqual(runtime.trajectory[1].tool_name, "calculate_discount")
        self.assertEqual(runtime.trajectory[2].decision_type, "finish")

    def test_timeout_protection(self):
        class SlowLLM(BaseLLM):
            def generate_decision(self, messages, tools_schema):
                time.sleep(0.02)
                return LLMResponse(
                    action_type="tool_call",
                    tool_name="get_weather",
                    tool_args={"city": "Seattle"}
                )

        runtime = AgentRuntime(max_steps=5, timeout_seconds=0.01)
        agent = Agent(llm=SlowLLM(), registry=self.registry, runtime=runtime)
        
        result = agent.run("Do work")
        self.assertIn("timeout", result.lower())

    def test_custom_tool_registration(self):
        def square(x: float) -> float:
            """Compute square of a number."""
            return x * x

        self.registry.register(square)
        schemas = self.registry.get_schemas()
        square_schema = next(s for s in schemas if s["function"]["name"] == "square")
        self.assertIsNotNone(square_schema)
        
        exec_res = self.registry.execute("square", {"x": 9.0})
        self.assertEqual(exec_res["status"], "success")
        self.assertEqual(exec_res["result"], 81.0)


if __name__ == "__main__":
    unittest.main()
