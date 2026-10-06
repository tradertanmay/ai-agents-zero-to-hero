"""
Tests for Module 04: Build Your First Agent & Early Evaluation
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
        self.robust_model = m04.RobustDecisionEngine()
        self.naive_model = m04.NaiveDecisionEngine()
        self.battery = m04.build_10_case_battery()
        self.scorecard = m04.RegressionScorecard(registry=self.registry)

    def test_end_to_end_agent_success(self):
        agent = m04.Agent(model=self.robust_model, registry=self.registry, max_steps=5)
        goal = "Calculate final bill for customer 'cust_42' on a $250 purchase."
        answer = agent.run(goal, verbose=False)
        self.assertIn("Gold member", answer)
        self.assertIn("$200.00", answer)

    def test_agent_step_budget_limit(self):
        # Setting max_steps lower than required (requires ~4 turns)
        agent = m04.Agent(model=self.robust_model, registry=self.registry, max_steps=2)
        goal = "Calculate final bill for customer 'cust_42' on a $250 purchase."
        answer = agent.run(goal, verbose=False)
        self.assertIn("without terminal answer", answer)

    def test_10_case_battery_structure(self):
        self.assertEqual(len(self.battery), 10)
        case_ids = [c.case_id for c in self.battery]
        self.assertEqual(case_ids, list(range(1, 11)))

    def test_regression_scorecard_robust_passes(self):
        res = self.scorecard.evaluate(self.robust_model, self.battery)
        self.assertEqual(res.total, 10)
        self.assertEqual(res.passed, 10)
        self.assertEqual(res.failed, 0)
        self.assertEqual(res.pass_rate, 100.0)
        self.assertEqual(len(res.failures), 0)

    def test_regression_scorecard_naive_catches_failures(self):
        res = self.scorecard.evaluate(self.naive_model, self.battery)
        self.assertEqual(res.total, 10)
        self.assertTrue(res.failed > 0)
        self.assertTrue(len(res.failures) > 0)
        # Verify structured failure record format
        failure = res.failures[0]
        self.assertIsInstance(failure.case_id, int)
        self.assertIn(failure.failure_type, ["UNEXPECTED_ANSWER", "INPUT_VALIDATION_FAILURE", "BUDGET_EXCEEDED"])
        self.assertTrue(len(failure.expected) > 0)
        self.assertTrue(len(failure.actual) > 0)

    def test_before_after_comparison(self):
        naive_res = self.scorecard.evaluate(self.naive_model, self.battery)
        robust_res = self.scorecard.evaluate(self.robust_model, self.battery)
        self.assertGreater(robust_res.pass_rate, naive_res.pass_rate)


if __name__ == "__main__":
    unittest.main()
