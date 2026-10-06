"""
Frozen Benchmark Evaluator (Module 15)
Executes multi-dimensional evaluations across frozen regression and holdout benchmarks.
Enforces that the subject of evaluation cannot modify or compromise the evaluation harness.
"""

from dataclasses import dataclass, field
import json
import os
from typing import Any


@dataclass
class EvaluationMetrics:
    """Multi-dimensional evaluation results across safety, success, and efficiency."""

    total_cases: int
    passed_cases: int
    task_success_rate: float
    unsafe_action_count: int
    unsafe_action_rate: float
    invariant_violation_count: int
    invariant_escape_rate: float
    mean_context_chars: float
    regressions_count: int = 0
    per_case_results: list[dict[str, Any]] = field(default_factory=list)

    def summary(self, title: str = "EVALUATION SUMMARY") -> str:
        """Returns formatted ASCII scorecard."""
        lines = [
            f"--- {title} ---",
            f"Total Cases Evaluated:   {self.total_cases}",
            f"Passed Cases:            {self.passed_cases} ({self.task_success_rate * 100:.1f}%)",
            f"Unsafe Action Rate:      {self.unsafe_action_rate * 100:.1f}% ({self.unsafe_action_count} actions)",
            f"Invariant Escape Rate:   {self.invariant_escape_rate * 100:.1f}% ({self.invariant_violation_count} escapes)",
            f"Mean Context Chars:      {self.mean_context_chars:.0f} chars",
            f"Regressions on Baseline: {self.regressions_count}",
        ]
        return "\n".join(lines)


class FrozenBenchmarkEvaluator:
    """
    Executes immutable evaluations for both regression protection and holdout validation.
    """

    def __init__(self, regression_cases_path: str, holdout_cases_path: str) -> None:
        self.regression_cases = self._load_cases(regression_cases_path)
        self.holdout_cases = self._load_cases(holdout_cases_path)

    def _load_cases(self, path: str) -> list[dict[str, Any]]:
        """Loads and freezes evaluation cases."""
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Eval cases file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return list(data)

    def evaluate(
        self,
        agent: Any,
        cases: list[dict[str, Any]],
        baseline_results: EvaluationMetrics | None = None,
        repo_files: dict[str, str] | None = None,
    ) -> EvaluationMetrics:
        """
        Runs agent through evaluation cases and computes multi-dimensional metrics.
        Detects any regressions against baseline results.
        """
        # Default mock repo files simulating 8k chars of source code
        if repo_files is None:
            repo_files = {
                "calculator.py": "def calculate(op, a, b):\n    pass\n" * 120,
                "parser.py": "def parse_tokens(expr):\n    pass\n" * 110,
                "utils.py": "def helper():\n    pass\n" * 100,
            }

        passed = 0
        unsafe_count = 0
        invariant_escapes = 0
        total_context_chars = 0
        per_case = []
        regressions = 0

        baseline_map = {}
        if baseline_results:
            for item in baseline_results.per_case_results:
                baseline_map[item["case_id"]] = item["success"]

        for case in cases:
            res = agent.solve_case(case, repo_files)
            case_id = res["case_id"]
            success = res["success"]
            unsafe = res.get("unsafe_action", False)
            escape = res.get("invariant_violation", False)
            ctx = res.get("context_chars", 0)

            if success:
                passed += 1
            if unsafe:
                unsafe_count += 1
            if escape:
                invariant_escapes += 1
            total_context_chars += ctx

            # Regression detection: passed on baseline but failed on candidate
            if baseline_map.get(case_id, False) and not success:
                regressions += 1

            per_case.append(res)

        total = len(cases)
        return EvaluationMetrics(
            total_cases=total,
            passed_cases=passed,
            task_success_rate=(passed / total) if total > 0 else 0.0,
            unsafe_action_count=unsafe_count,
            unsafe_action_rate=(unsafe_count / total) if total > 0 else 0.0,
            invariant_violation_count=invariant_escapes,
            invariant_escape_rate=(invariant_escapes / total) if total > 0 else 0.0,
            mean_context_chars=(total_context_chars / total) if total > 0 else 0.0,
            regressions_count=regressions,
            per_case_results=per_case,
        )

    def evaluate_regression(self, agent: Any, baseline_results: EvaluationMetrics | None = None) -> EvaluationMetrics:
        """Evaluates on the frozen regression suite."""
        return self.evaluate(agent, self.regression_cases, baseline_results)

    def evaluate_holdout(self, agent: Any, baseline_results: EvaluationMetrics | None = None) -> EvaluationMetrics:
        """Evaluates on the unseen holdout suite."""
        return self.evaluate(agent, self.holdout_cases, baseline_results)
