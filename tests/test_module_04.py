"""
Tests for Module 04: Build Your First Agent
"""

import unittest
import os
import sys
import importlib.util

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

spec = importlib.util.spec_from_file_location("module_04_example", os.path.join(root_dir, "04-build-your-first-agent", "example.py"))
m04 = importlib.util.module_from_spec(spec)
sys.modules["module_04_example"] = m04
spec.loader.exec_module(m04)


class TestModule04(unittest.TestCase):
    def setUp(self):
        self.registry = m04.ToolRegistry()
        self.registry.register(m04.get_customer_info)
        self.registry.register(m04.multiply)
        self.registry.register(m04.subtract)
        self.model = m04.MockLLMDecisionEngine()

    def test_end_to_end_agent_success(self):
        agent = m04.Agent(model=self.model, registry=self.registry, max_steps=5)
        goal = "Calculate final bill for customer 'cust_42' on a $250 purchase."
        answer = agent.run(goal)
        self.assertIn("Gold member", answer)
        self.assertIn("$200.00", answer)

    def test_agent_step_budget_limit(self):
        # Setting max_steps lower than required (requires ~4 turns)
        agent = m04.Agent(model=self.model, registry=self.registry, max_steps=2)
        goal = "Calculate final bill for customer 'cust_42' on a $250 purchase."
        answer = agent.run(goal)
        self.assertIn("without terminal answer", answer)


if __name__ == "__main__":
    unittest.main()
