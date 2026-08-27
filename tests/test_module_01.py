"""
Tests for Module 01: What Is an Agent?
"""

import unittest
import sys
import os

# Add root directory to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Import module 01 components
# Note: importlib is used because directory starts with digits
import importlib.util

spec = importlib.util.spec_from_file_location("module_01_example", os.path.join(root_dir, "01-what-is-an-agent", "example.py"))
m01 = importlib.util.module_from_spec(spec)
sys.modules["module_01_example"] = m01
spec.loader.exec_module(m01)


class TestModule01(unittest.TestCase):
    def test_chatbot_preserves_history(self):
        bot = m01.Chatbot()
        r1 = bot.reply("Hello")
        r2 = bot.reply("What is my balance?")
        self.assertEqual(len(bot.history), 4) # 2 user turns + 2 assistant turns
        self.assertIn("Hello", bot.history[0]["content"])

    def test_deterministic_workflow_success(self):
        res = m01.run_deterministic_workflow("user_101")
        self.assertEqual(res["user"], "Alice")
        self.assertEqual(res["discount"], 30.0) # 150 * 0.20

    def test_deterministic_workflow_missing_user(self):
        res = m01.run_deterministic_workflow("user_999")
        self.assertIn("error", res)

    def test_dynamic_agent_loop(self):
        tools = {
            "query_database": m01.query_database,
            "calculate_discount": m01.calculate_discount,
        }
        agent = m01.SimpleAgent(tools=tools)
        answer = agent.run(goal="Find user_101 and determine their discount.", max_steps=5)
        self.assertIn("Alice has a discount of $30.00", answer)
        self.assertEqual(len(agent.trajectory), 2) # 2 tool calls: query_database -> calculate_discount


if __name__ == "__main__":
    unittest.main()
