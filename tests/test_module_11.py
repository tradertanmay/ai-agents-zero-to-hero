"""
Tests for Module 11: Advanced Agent Evaluation & Trajectory Benchmarks
"""

import json
import os
import sys
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from examples.reddit_comment_agent.evals.judges import (
    DeterministicJudge,
    HeuristicJudge,
    LLMJudge,
    JudgeVerdict,
)
from examples.reddit_comment_agent.evals.metrics import (
    CaseEvalRecord,
    EvaluationMetrics,
    MetricsCalculator,
)
from examples.reddit_comment_agent.evals.runner import EvalRunner
from examples.reddit_comment_agent.evals.report import RegressionReporter
from examples.reddit_comment_agent.mock_reddit import MockRedditEnvironment
from examples.reddit_comment_agent.reddit import MockRedditClient
from examples.reddit_comment_agent.agent import RedditCommentAgent


class TestModule11(unittest.TestCase):
    def test_deterministic_judge_safety(self):
        """Verifies that DeterministicJudge catches unapproved write attempts."""
        safe_trajectory = [
            {"action_name": "read_post", "result_status": "success"},
            {"action_name": "human_approval_gate", "result_status": "success"},
            {"action_name": "submit_comment", "result_status": "success"},
        ]
        verdict = DeterministicJudge.verify_safety_and_permissions(safe_trajectory)
        self.assertTrue(verdict.passed)
        self.assertEqual(verdict.score, 1.0)

        unsafe_trajectory = [
            {"action_name": "read_post", "result_status": "success"},
            {"action_name": "submit_comment", "result_status": "success"},
        ]
        verdict_bad = DeterministicJudge.verify_safety_and_permissions(unsafe_trajectory)
        self.assertFalse(verdict_bad.passed)
        self.assertEqual(verdict_bad.score, 0.0)
        self.assertIn("SAFETY VIOLATION", verdict_bad.rationale)

    def test_deterministic_judge_duplicate_avoidance(self):
        """Verifies duplicate prevention verification."""
        v_ok = DeterministicJudge.verify_duplicate_avoidance("post_1", True, "ABSTAIN_ALREADY_ANSWERED")
        self.assertTrue(v_ok.passed)

        v_dup = DeterministicJudge.verify_duplicate_avoidance("post_1", True, "CONTRIBUTE")
        self.assertFalse(v_dup.passed)
        self.assertEqual(v_dup.score, 0.0)
        self.assertIn("DUPLICATE ACTION", v_dup.rationale)

    def test_heuristic_judge_rules(self):
        """Verifies structural and rule-based heuristic checks."""
        # Code formatting check
        unformatted_code = "Here is the solution: def add(a, b): return a + b"
        v_unformatted = HeuristicJudge.check_rule_compliance(unformatted_code, [])
        self.assertFalse(v_unformatted.passed)
        self.assertIn("code fence", v_unformatted.rationale)

        formatted_code = "Here is the solution:\n```python\ndef add(a, b):\n    return a + b\n```"
        v_formatted = HeuristicJudge.check_rule_compliance(formatted_code, [])
        self.assertTrue(v_formatted.passed)

        # Spam detection
        spam = "Guaranteed 10,000% returns join our telegram crypto bot!"
        v_spam = HeuristicJudge.check_rule_compliance(spam, [])
        self.assertFalse(v_spam.passed)
        self.assertEqual(v_spam.score, 0.0)

    def test_llm_judge_and_human_calibration(self):
        """Verifies semantic scoring and calibration against human ground truth."""
        judge = LLMJudge()
        v = judge.evaluate_groundedness("How to memoize in Python?", "Use functools.lru_cache.")
        self.assertTrue(v.passed)
        self.assertGreaterEqual(v.score, 0.7)

        # Calibration agreement test
        human_ratings = [0.9, 0.85, 0.2, 0.95, 0.1, 0.8, 0.75, 0.3, 0.9, 0.15]
        judge_scores = [0.9, 0.8, 0.15, 0.9, 0.1, 0.85, 0.7, 0.35, 0.95, 0.1]
        agreement = LLMJudge.calibrate_agreement(human_ratings, judge_scores, tolerance=0.1)
        self.assertEqual(agreement, 1.0)

        # Non-matching ratings
        divergent_scores = [0.1] * 10
        agreement_low = LLMJudge.calibrate_agreement(human_ratings, divergent_scores, tolerance=0.1)
        self.assertLess(agreement_low, 0.5)

    def test_metrics_calculator(self):
        """Verifies multi-dimensional metric calculations."""
        # Empty case
        empty_metrics = MetricsCalculator.compute([])
        self.assertEqual(empty_metrics.total_cases, 0)
        self.assertEqual(empty_metrics.task_success_rate, 0.0)

        records = [
            CaseEvalRecord(
                case_id="case_1",
                category="relevant",
                expected_action="CONTRIBUTE",
                actual_action="CONTRIBUTE",
                task_success=True,
                correct_abstention=None,
                false_action=False,
                tool_accuracy=1.0,
                unsafe_action_attempted=False,
                duplicate_action_attempted=False,
                recovery_attempted=False,
                recovery_succeeded=False,
                steps_consumed=5,
                tool_calls_consumed=5,
            ),
            CaseEvalRecord(
                case_id="case_2",
                category="spam",
                expected_action="ABSTAIN_SPAM",
                actual_action="ABSTAIN_SPAM",
                task_success=True,
                correct_abstention=True,
                false_action=False,
                tool_accuracy=1.0,
                unsafe_action_attempted=False,
                duplicate_action_attempted=False,
                recovery_attempted=False,
                recovery_succeeded=False,
                steps_consumed=2,
                tool_calls_consumed=2,
            ),
            CaseEvalRecord(
                case_id="case_3",
                category="solved",
                expected_action="ABSTAIN_SOLVED",
                actual_action="CONTRIBUTE",
                task_success=False,
                correct_abstention=False,
                false_action=True,
                tool_accuracy=0.6,
                unsafe_action_attempted=False,
                duplicate_action_attempted=False,
                recovery_attempted=False,
                recovery_succeeded=False,
                steps_consumed=6,
                tool_calls_consumed=6,
            ),
        ]
        metrics = MetricsCalculator.compute(records)
        self.assertEqual(metrics.total_cases, 3)
        self.assertAlmostEqual(metrics.task_success_rate, 2 / 3, places=2)
        self.assertAlmostEqual(metrics.correct_abstention_rate, 0.5, places=2)
        self.assertAlmostEqual(metrics.false_action_rate, 1 / 3, places=2)
        self.assertEqual(metrics.unsafe_action_rate, 0.0)
        self.assertAlmostEqual(metrics.mean_steps_per_task, (5 + 2 + 6) / 3, places=2)

    def test_regression_reporter(self):
        """Verifies report generation for single run and comparative delta table."""
        record = CaseEvalRecord(
            case_id="c1",
            category="test",
            expected_action="CONTRIBUTE",
            actual_action="CONTRIBUTE",
            task_success=True,
            correct_abstention=None,
            false_action=False,
            tool_accuracy=1.0,
            unsafe_action_attempted=False,
            duplicate_action_attempted=False,
            recovery_attempted=False,
            recovery_succeeded=False,
            steps_consumed=4,
            tool_calls_consumed=4,
        )
        metrics_a = MetricsCalculator.compute([record])
        metrics_b = MetricsCalculator.compute([record])

        single_rep = RegressionReporter.format_single_run(metrics_a, "V1")
        self.assertIn("AGENT EVALUATION REPORT: V1", single_rep)
        self.assertIn("100.0%", single_rep)

        comp_rep = RegressionReporter.format_comparison(metrics_a, metrics_b, "V1", "V2")
        self.assertIn("REGRESSION COMPARISON", comp_rep)
        self.assertIn("V1", comp_rep)
        self.assertIn("V2", comp_rep)

    def test_eval_runner_frozen_benchmark(self):
        """Verifies EvalRunner loads the 20 frozen cases and executes properly."""
        cases_file = os.path.join(root_dir, "11-agent-evaluation", "eval_cases.json")
        runner = EvalRunner(cases_file)
        self.assertEqual(len(runner.cases), 20)

        # Verify case categories
        categories = {c["category"] for c in runner.cases}
        self.assertIn("relevant_clear_answer", categories)
        self.assertIn("marketing_spam_temptation", categories)
        self.assertIn("already_answered", categories)
        self.assertIn("tool_timeout", categories)
        self.assertIn("rate_limit", categories)


if __name__ == "__main__":
    unittest.main()
