"""
Regression Reporting (Module 11)
Formats side-by-side comparison tables between Agent Version A and Version B
across all evaluation dimensions.
"""

from examples.reddit_comment_agent.evals.metrics import EvaluationMetrics


class RegressionReporter:
    """Generates comparison reports between baseline and experimental agent versions."""

    @staticmethod
    def format_single_run(metrics: EvaluationMetrics, version_name: str = "V1") -> str:
        lines = [
            "=" * 70,
            f"AGENT EVALUATION REPORT: {version_name}",
            "=" * 70,
            f"Total Frozen Cases Evaluated    : {metrics.total_cases}",
            f"Overall Task Success Rate       : {metrics.task_success_rate * 100:.1f}%",
            f"Correct Abstention Rate         : {metrics.correct_abstention_rate * 100:.1f}%",
            f"False-Action Rate               : {metrics.false_action_rate * 100:.1f}%",
            f"Tool Selection Accuracy         : {metrics.tool_accuracy * 100:.1f}%",
            f"Unsafe Action Rate (Target=0.0%): {metrics.unsafe_action_rate * 100:.1f}%",
            f"Duplicate Action Rate           : {metrics.duplicate_action_rate * 100:.1f}%",
            f"Recovery Success Rate           : {metrics.recovery_success_rate * 100:.1f}%",
            f"Mean Steps Per Task             : {metrics.mean_steps_per_task:.2f}",
            f"Mean Tool Calls Per Task        : {metrics.mean_tool_calls_per_task:.2f}",
            "=" * 70,
        ]
        return "\n".join(lines)

    @staticmethod
    def format_comparison(
        metrics_a: EvaluationMetrics,
        metrics_b: EvaluationMetrics,
        name_a: str = "Version A (V1)",
        name_b: str = "Version B (V2)",
    ) -> str:
        def fmt_pct(val: float) -> str:
            return f"{val * 100:.1f}%"

        def fmt_delta_pct(v_a: float, v_b: float) -> str:
            d = (v_b - v_a) * 100
            sign = "+" if d > 0 else ""
            return f"{sign}{d:.1f}%"

        def fmt_delta_num(v_a: float, v_b: float) -> str:
            d = v_b - v_a
            pct = (d / v_a * 100) if v_a else 0.0
            sign = "+" if d > 0 else ""
            return f"{sign}{d:.2f} ({sign}{pct:.1f}%)"

        rows = [
            ("Overall Task Success Rate", fmt_pct(metrics_a.task_success_rate), fmt_pct(metrics_b.task_success_rate), fmt_delta_pct(metrics_a.task_success_rate, metrics_b.task_success_rate)),
            ("Correct Abstention Rate", fmt_pct(metrics_a.correct_abstention_rate), fmt_pct(metrics_b.correct_abstention_rate), fmt_delta_pct(metrics_a.correct_abstention_rate, metrics_b.correct_abstention_rate)),
            ("False-Action Rate", fmt_pct(metrics_a.false_action_rate), fmt_pct(metrics_b.false_action_rate), fmt_delta_pct(metrics_a.false_action_rate, metrics_b.false_action_rate)),
            ("Tool Selection Accuracy", fmt_pct(metrics_a.tool_accuracy), fmt_pct(metrics_b.tool_accuracy), fmt_delta_pct(metrics_a.tool_accuracy, metrics_b.tool_accuracy)),
            ("Unsafe Action Rate (Target=0)", fmt_pct(metrics_a.unsafe_action_rate), fmt_pct(metrics_b.unsafe_action_rate), fmt_delta_pct(metrics_a.unsafe_action_rate, metrics_b.unsafe_action_rate)),
            ("Duplicate Action Rate", fmt_pct(metrics_a.duplicate_action_rate), fmt_pct(metrics_b.duplicate_action_rate), fmt_delta_pct(metrics_a.duplicate_action_rate, metrics_b.duplicate_action_rate)),
            ("Failure Recovery Success", fmt_pct(metrics_a.recovery_success_rate), fmt_pct(metrics_b.recovery_success_rate), fmt_delta_pct(metrics_a.recovery_success_rate, metrics_b.recovery_success_rate)),
            ("Mean Steps Per Task", f"{metrics_a.mean_steps_per_task:.2f}", f"{metrics_b.mean_steps_per_task:.2f}", fmt_delta_num(metrics_a.mean_steps_per_task, metrics_b.mean_steps_per_task)),
            ("Mean Tool Calls Per Task", f"{metrics_a.mean_tool_calls_per_task:.2f}", f"{metrics_b.mean_tool_calls_per_task:.2f}", fmt_delta_num(metrics_a.mean_tool_calls_per_task, metrics_b.mean_tool_calls_per_task)),
        ]

        header = f"{'Metric':<30} | {name_a:<18} | {name_b:<18} | {'Delta':<18}"
        sep = "-" * len(header)
        table_lines = [header, sep]
        for metric, v1, v2, delta in rows:
            table_lines.append(f"{metric:<30} | {v1:<18} | {v2:<18} | {delta:<18}")

        output = [
            "=" * len(header),
            "AGENT EVALUATION BENCHMARK: REGRESSION COMPARISON",
            "=" * len(header),
            f"Frozen Eval Cases: {metrics_a.total_cases}",
            sep,
        ] + table_lines + ["=" * len(header)]
        return "\n".join(output)
