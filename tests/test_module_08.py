"""
Tests for Module 08: Agent Runtime and Harness
"""

import unittest
import os
import sys
import importlib.util

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

spec = importlib.util.spec_from_file_location("module_08_example", os.path.join(root_dir, "08-agent-runtime-and-harness", "example.py"))
m08 = importlib.util.module_from_spec(spec)
sys.modules["module_08_example"] = m08
spec.loader.exec_module(m08)


class TestModule08(unittest.TestCase):
    def setUp(self):
        self.registry = m08.ToolRegistry()
        self.registry.register(m08.read_file, permission_level="read")
        self.registry.register(m08.delete_database_table, permission_level="admin")

    def test_harness_happy_path(self):
        script = [
            m08.Action(type="tool_call", tool_name="read_file", tool_args={"filepath": "config.json"}),
            m08.Action(type="finish", answer="Done reading")
        ]
        budget = m08.ExecutionBudget(max_steps=5)
        harness = m08.AgentHarness(self.registry, budget)
        res = harness.run("Read config", m08.DecisionEngine(script))
        
        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["final_answer"], "Done reading")
        self.assertEqual(res["total_steps"], 2)
        self.assertEqual(len(harness.trajectory), 2)

    def test_permission_gate_blocks_unauthorized_tool(self):
        script = [
            m08.Action(type="tool_call", tool_name="delete_database_table", tool_args={"table_name": "orders"}),
            m08.Action(type="finish", answer="Recovered after denial")
        ]
        # Only grant read access
        budget = m08.ExecutionBudget(max_steps=5)
        harness = m08.AgentHarness(self.registry, budget, allowed_permissions={"read"})
        res = harness.run("Attempt delete", m08.DecisionEngine(script))
        
        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["final_answer"], "Recovered after denial")
        # Ensure the denied attempt was logged in trajectory
        denied_step = harness.trajectory[0]
        self.assertEqual(denied_step.tool_result["status"], "error")
        self.assertIn("PermissionDenied", denied_step.tool_result["error"])

    def test_budget_tripwire_step_limit(self):
        infinite_script = [
            m08.Action(type="tool_call", tool_name="read_file", tool_args={"filepath": "f.txt"})
            for _ in range(10)
        ]
        budget = m08.ExecutionBudget(max_steps=3)
        harness = m08.AgentHarness(self.registry, budget)
        res = harness.run("Infinite loop attempt", m08.DecisionEngine(infinite_script))
        
        self.assertEqual(res["status"], "budget_exceeded")
        self.assertEqual(res["total_steps"], 4) # Step 4 triggers tripwire before execution


if __name__ == "__main__":
    unittest.main()
