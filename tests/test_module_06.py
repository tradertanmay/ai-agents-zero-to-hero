"""
Tests for Module 06: Planning and Reasoning
"""

import unittest
import os
import sys
import importlib.util

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

spec = importlib.util.spec_from_file_location("module_06_example", os.path.join(root_dir, "06-planning-and-reasoning", "example.py"))
m06 = importlib.util.module_from_spec(spec)
sys.modules["module_06_example"] = m06
spec.loader.exec_module(m06)


class TestModule06(unittest.TestCase):
    def setUp(self):
        self.planner = m06.Planner()

    def test_plan_initialization_and_properties(self):
        plan = self.planner.create_initial_plan("Deploy auth service")
        self.assertEqual(len(plan.steps), 4)
        self.assertFalse(plan.is_finished)
        
        first = plan.next_pending_step
        self.assertIsNotNone(first)
        self.assertEqual(first.step_id, 1)
        self.assertEqual(first.tool_name, "check_git_status")

    def test_rigid_planner_agent_fails_on_conflict(self):
        env = m06.DeploymentEnvironment(simulate_port_conflict=True)
        reg = m06.setup_registry(env)
        agent = m06.RigidPlannerAgent(self.planner, reg)

        success, msg = agent.run("Deploy service")
        self.assertFalse(success)
        self.assertIn("Rigid execution aborted at Step 2", msg)
        self.assertIn("PortConflictError", msg)

    def test_rigid_planner_agent_succeeds_without_conflict(self):
        env = m06.DeploymentEnvironment(simulate_port_conflict=False)
        reg = m06.setup_registry(env)
        agent = m06.RigidPlannerAgent(self.planner, reg)

        success, msg = agent.run("Deploy service")
        self.assertTrue(success)
        self.assertIn("Deployment completed successfully", msg)
        self.assertTrue(env.deployed)
        self.assertTrue(env.notified)

    def test_adaptive_planning_agent_recovers_from_conflict(self):
        env = m06.DeploymentEnvironment(simulate_port_conflict=True)
        reg = m06.setup_registry(env)
        agent = m06.AdaptivePlanningAgent(self.planner, reg, max_replans=2)

        success, msg = agent.run("Deploy auth service")
        self.assertTrue(success)
        self.assertIn("Deployment succeeded", msg)
        self.assertTrue(env.deployed)
        self.assertTrue(env.notified)
        self.assertIsNone(env.conflicting_pid)

    def test_replan_budget_exhaustion(self):
        # Create an environment where error is never resolved
        env = m06.DeploymentEnvironment(simulate_port_conflict=True)
        # Prevent kill_process from fixing the issue
        env.kill_process = lambda pid: {"status": "error", "error": "Permission denied"}
        reg = m06.setup_registry(env)
        agent = m06.AdaptivePlanningAgent(self.planner, reg, max_replans=1)

        success, msg = agent.run("Deploy auth service")
        self.assertFalse(success)
        self.assertIn("exhausting replan budget", msg)


if __name__ == "__main__":
    unittest.main()
