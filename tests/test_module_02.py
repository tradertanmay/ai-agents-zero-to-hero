"""
Tests for Module 02: The Agent Loop
"""

import unittest
import os
import sys
import importlib.util

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

spec = importlib.util.spec_from_file_location("module_02_example", os.path.join(root_dir, "02-agent-loop", "example.py"))
m02 = importlib.util.module_from_spec(spec)
sys.modules["module_02_example"] = m02
spec.loader.exec_module(m02)


class TestModule02(unittest.TestCase):
    def test_environment_initial_state(self):
        env = m02.ExplorationWorld()
        obs = env.observe()
        self.assertEqual(obs["current_position"], 0)
        self.assertEqual(obs["has_key"], False)
        self.assertEqual(obs["has_treasure"], False)

    def test_door_blocks_without_key(self):
        env = m02.ExplorationWorld()
        env.agent_pos = 2 # standing right before door at pos 3
        res = env.execute_action("move_right")
        self.assertFalse(res["success"])
        self.assertIn("locked", res["message"].lower())

    def test_full_loop_execution(self):
        env = m02.ExplorationWorld()
        summary = m02.run_agent_loop(env, max_steps=10)
        self.assertEqual(summary["status"], "success")
        self.assertTrue(summary["final_env_state"]["has_treasure"])
        self.assertLessEqual(summary["total_steps"], 10)

    def test_budget_exhaustion_on_low_max_steps(self):
        env = m02.ExplorationWorld()
        summary = m02.run_agent_loop(env, max_steps=2)
        self.assertEqual(summary["status"], "exhausted_budget")
        self.assertFalse(summary["final_env_state"]["has_treasure"])


if __name__ == "__main__":
    unittest.main()
