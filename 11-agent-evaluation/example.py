"""
Module 11: Advanced Agent Evaluation
Runnable Python Demonstration: Frozen Benchmark Regression Testing & Trajectory Analysis

Demonstrates:
1. Running a 20-case frozen benchmark across two agent iterations (Version A vs. Version B).
2. Generating a side-by-side regression scorecard with outcome, trajectory, safety, and efficiency deltas.
3. Human calibration of LLM-as-a-Judge evaluators to verify agreement before deployment.
"""

import os
import sys
import time

# Ensure project root is in sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from examples.reddit_comment_agent.evals.runner import EvalRunner
from examples.reddit_comment_agent.evals.report import RegressionReporter
from examples.reddit_comment_agent.evals.judges import LLMJudge
from examples.reddit_comment_agent.agent import RedditCommentAgent
import importlib.util

spec = importlib.util.spec_from_file_location(
    "m10_example",
    os.path.join(root_dir, "10-agent-failures", "example.py")
)
m10 = importlib.util.module_from_spec(spec)
sys.modules["m10_example"] = m10
spec.loader.exec_module(m10)

FaultInjectingRedditClient = m10.FaultInjectingRedditClient
ResilientRedditAgent = m10.ResilientRedditAgent


# ============================================================================
# 1. Agent Version Definitions
# ============================================================================

class NaiveBaselineAgent(RedditCommentAgent):
    """
    Version A (Baseline):
    Lacks sophisticated failure handling, does not reconcile ambiguous timeouts,
    and has permissive filtering (attempts to comment on low-value/spam posts).
    """

    def should_contribute(self, post: dict, existing_comments: list) -> tuple[bool, str]:
        # Naive: Only filters extreme spam, tries to answer already-solved posts
        title = post.get("title", "").lower()
        if "10,000%" in title:
            return False, "Skipped spam."
        return True, "Proceed: Naive agent attempts to answer everything."


def agent_v1_factory(client, state, approval_gate, runtime):
    return NaiveBaselineAgent(client, state, approval_gate=approval_gate, runtime=runtime)


class OptimizedResilientAgent(RedditCommentAgent):
    """
    Version B (Optimized & Resilient):
    Features rate-limit backoff, ambiguous write reconciliation, semantic drift checks,
    and disciplined filtering (correctly abstaining from spam and solved posts).
    """

    def __init__(self, client, state, approval_gate, runtime):
        super().__init__(client, state, approval_gate=approval_gate, runtime=runtime)
        self.resilient_core = ResilientRedditAgent(client, state, approval_gate, runtime)

    def process_post(self, post_summary: dict) -> dict:
        post_id = post_summary["post_id"]
        step = 1

        # Duplicate Prevention Check
        if self.state.has_commented(post_id):
            self.runtime.log_step(step, post_id, "check_state", {}, "skipped", "Already commented on this post.")
            return {"post_id": post_id, "status": "skipped", "reason": "Already commented on this post."}

        # Step 1: Read Post with Bounded Retry
        post = None
        for _ in range(2):
            try:
                post = self.client.get_post(post_id)
                break
            except TimeoutError:
                time.sleep(0.01)

        self.runtime.log_step(step, post_id, "read_post", {"post_id": post_id}, "success" if post else "failed", "Fetched post details")
        if not post:
            return {"post_id": post_id, "status": "aborted", "reason": "Post deleted"}

        # Step 2: Read Comments with Bounded Retry
        step += 1
        comments = []
        for _ in range(2):
            try:
                comments = self.client.get_comments(post_id, limit=3)
                break
            except TimeoutError:
                time.sleep(0.01)
        self.runtime.log_step(step, post_id, "read_comments", {"post_id": post_id}, "success", f"Fetched {len(comments)} comments")

        # Step 3: Decide Whether to Contribute
        step += 1
        can_help, rationale = self.should_contribute(post, comments)
        self.runtime.log_step(step, post_id, "decide_to_contribute", {}, "success" if can_help else "skipped", rationale)
        if not can_help:
            return {"post_id": post_id, "status": "skipped", "reason": rationale}

        # Step 4: Draft Comment
        step += 1
        draft = self.synthesize_draft(post, [], comments)
        self.runtime.log_step(step, post_id, "draft_comment", {}, "success", "Drafted technical comment")

        eval_res = self.evaluator.evaluate(post, [], comments, draft)
        if not eval_res.passed:
            return {"post_id": post_id, "status": "rejected_by_evaluator", "evaluation": eval_res}

        # Step 5: Human Approval Gate
        step += 1
        approval = self.approval_gate.request_approval(post, draft, eval_res.total_score, eval_res.summary)
        self.runtime.log_step(step, post_id, "human_approval_gate", {}, "success" if approval.approved else "denied", approval.reason)
        if not approval.approved:
            return {"post_id": post_id, "status": "rejected_by_human", "reason": approval.reason}

        # Step 6: Resilient Submission with Reconciliation
        step += 1
        success, result = self.resilient_core.execute_resilient_comment(post_id, post, draft, approval.approval_token)
        self.runtime.log_step(step, post_id, "submit_comment", {}, "success" if success else "failed", str(result))
        if success:
            return {"post_id": post_id, "status": "published", "comment_id": result}
        else:
            return {"post_id": post_id, "status": "submission_error", "error": result}


def agent_v2_factory(client, state, approval_gate, runtime):
    return OptimizedResilientAgent(client, state, approval_gate, runtime)


def client_factory(env):
    return FaultInjectingRedditClient(env)


# ============================================================================
# 2. Benchmark Execution & Regression Comparison
# ============================================================================

def main() -> None:
    print("=" * 75)
    print("MODULE 11: ADVANCED AGENT EVALUATION & REGRESSION BENCHMARK")
    print("=" * 75)

    cases_path = os.path.join(root_dir, "11-agent-evaluation", "eval_cases.json")
    runner = EvalRunner(cases_path=cases_path)

    print(f"\nLoaded {len(runner.cases)} frozen evaluation benchmark cases.")
    print("Running evaluation suite against Version A (Naive Baseline)...")
    metrics_v1 = runner.run_benchmark(agent_v1_factory, client_factory, "Version A (V1)")

    print("Running evaluation suite against Version B (Optimized & Resilient)...")
    metrics_v2 = runner.run_benchmark(agent_v2_factory, client_factory, "Version B (V2)")

    # Generate Side-by-Side Comparison Report
    print("\n")
    report = RegressionReporter.format_comparison(
        metrics_a=metrics_v1,
        metrics_b=metrics_v2,
        name_a="Version A (V1)",
        name_b="Version B (V2)",
    )
    print(report)

    # ------------------------------------------------------------------------
    # 3. Human Calibration of LLM-as-a-Judge Demonstration
    # ------------------------------------------------------------------------
    print("\n" + "=" * 75)
    print("DEMO: HUMAN CALIBRATION OF LLM-AS-A-JUDGE")
    print("=" * 75)
    print("Before relying on an LLM Judge for semantic evaluation, you must")
    print("calibrate its scores against a human-annotated baseline sample.")
    print("-" * 75)

    # 10 sample outputs labeled by human expert (0.0 to 1.0)
    human_labels = [0.9, 0.2, 0.8, 0.1, 0.9, 0.3, 0.8, 0.0, 0.7, 0.9]
    # Simulated LLM Judge scores on the same 10 samples
    judge_scores = [0.9, 0.3, 0.8, 0.1, 0.8, 0.5, 0.8, 0.1, 0.7, 0.9]

    agreement = LLMJudge.calibrate_agreement(human_labels, judge_scores, tolerance=0.2)
    print(f"Human Sample Size          : {len(human_labels)} cases")
    print(f"Judge Agreement Percentage : {agreement * 100:.1f}% (Tolerance: +/-0.2)")
    print(f"Calibration Verdict        : {'HIGH AGREEMENT ON CALIBRATION SET (Sample size too small for general reliability)' if agreement >= 0.8 else 'NEEDS RUBRIC REVISION'}")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
