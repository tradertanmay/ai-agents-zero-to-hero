"""
Evaluation Benchmark Runner (Module 11)
Executes a frozen test suite against an agent version and collects
multi-dimensional trajectory telemetry.
"""

import json
import os
from typing import Any, Callable
from examples.reddit_comment_agent.mock_reddit import MockRedditEnvironment
from examples.reddit_comment_agent.state import RedditAgentState
from examples.reddit_comment_agent.approval import ApprovalGate, ApprovalDecision
from examples.reddit_comment_agent.runtime import AgentRuntime, RuntimeBudget
from examples.reddit_comment_agent.evals.metrics import CaseEvalRecord, EvaluationMetrics, MetricsCalculator
from examples.reddit_comment_agent.evals.judges import DeterministicJudge, HeuristicJudge, LLMJudge


class EvalRunner:
    """Runs a test suite of cases against an agent and evaluates trajectories."""

    def __init__(self, cases_path: str | None = None) -> None:
        if cases_path is None:
            cases_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cases.json")
        with open(cases_path, "r", encoding="utf-8") as f:
            self.cases: list[dict[str, Any]] = json.load(f)

        self.deterministic_judge = DeterministicJudge()
        self.heuristic_judge = HeuristicJudge()
        self.llm_judge = LLMJudge()

    def run_benchmark(
        self,
        agent_factory: Callable[[Any, Any, Any, Any], Any],
        client_factory: Callable[[MockRedditEnvironment], Any],
        agent_version_name: str = "V1_Baseline",
    ) -> EvaluationMetrics:
        """
        Runs the full frozen benchmark suite against an agent instantiated
        via agent_factory and client_factory.
        """
        records: list[CaseEvalRecord] = []

        for case in self.cases:
            case_id = case["case_id"]
            category = case["category"]
            expected_action = case["expected_action"]
            fault_mode = case.get("fault_mode")
            simulate_approval = case.get("simulate_approval", True)

            # 1. Setup isolated mock environment for case
            env = MockRedditEnvironment()
            p_data = case["post"]
            post_id = p_data["post_id"]
            
            # Populate post in mock env
            from examples.reddit_comment_agent.mock_reddit import MockPost, MockComment
            post_obj = MockPost(
                post_id=post_id,
                subreddit=p_data.get("subreddit", case.get("subreddit", "r/Python")),
                author=p_data.get("author", "u/anon"),
                title=p_data.get("title", ""),
                selftext=p_data.get("selftext", ""),
                upvotes=p_data.get("upvotes", 1),
                comments=[
                    MockComment(
                        comment_id=c.get("comment_id", f"c_{i}"),
                        post_id=post_id,
                        author=c.get("author", "u/commenter"),
                        body=c.get("body", ""),
                        upvotes=c.get("upvotes", 1),
                    )
                    for i, c in enumerate(case.get("existing_comments", []))
                ]
            )
            env.posts[post_id] = post_obj

            client = client_factory(env)
            if fault_mode and hasattr(client, "set_fault"):
                client.set_fault(fault_mode)

            state = RedditAgentState(":memory:")
            if "pre_existing_comment" in case:
                state.record_submitted_comment(post_id, "c_prev", case["pre_existing_comment"])

            approval_gate = ApprovalGate(
                interactive=False,
                approval_callback=lambda req, approved=simulate_approval: ApprovalDecision(
                    approved=approved,
                    reason="Benchmarker automated sign-off" if approved else "Denied by benchmark test case",
                )
            )

            runtime = AgentRuntime(RuntimeBudget(max_steps_per_post=8))
            agent = agent_factory(client, state, approval_gate, runtime)

            # 2. Execute agent on post
            outcome = agent.process_post({"post_id": post_id, "title": post_obj.title, "subreddit": post_obj.subreddit})
            status = outcome.get("status", "unknown")

            # Determine actual high-level action taken
            if status == "published":
                actual_action = "CONTRIBUTE"
            elif status in ["skipped", "rejected_by_evaluator", "rejected_by_human"]:
                actual_action = "ABSTAIN"
            elif status in ["aborted", "failed", "submission_error"]:
                actual_action = "ABORT"
            else:
                actual_action = status.upper()

            # 3. Judges & Evaluation
            trajectory = [
                {
                    "action_name": s.action_name,
                    "result_status": s.result_status,
                    "details": s.details,
                }
                for s in runtime.trajectory
            ]

            safety_verdict = self.deterministic_judge.verify_safety_and_permissions(trajectory)
            dup_verdict = self.deterministic_judge.verify_duplicate_avoidance(
                post_id=post_id,
                was_already_commented="pre_existing_comment" in case,
                actual_action=actual_action,
            )

            # Task Success logic:
            if "CONTRIBUTE" in expected_action:
                task_success = (actual_action == "CONTRIBUTE" and status == "published")
            elif "ABSTAIN" in expected_action or "ABORT" in expected_action or "HALT" in expected_action:
                task_success = (actual_action in ["ABSTAIN", "ABORT"])
            elif "BLOCK" in expected_action:
                task_success = (status in ["rejected_by_human", "submission_error", "aborted"])
            else:
                task_success = (actual_action == expected_action)

            correct_abstention = None
            if "ABSTAIN" in expected_action or "ABORT" in expected_action:
                correct_abstention = (actual_action in ["ABSTAIN", "ABORT"])

            false_action = (("ABSTAIN" in expected_action or "ABORT" in expected_action) and actual_action == "CONTRIBUTE")

            # Tool Accuracy
            expected_seq = case.get("expected_tool_sequence")
            if expected_seq:
                actual_tools = [s.action_name for s in runtime.trajectory]
                matches = sum(1 for t in actual_tools if t in expected_seq)
                tool_accuracy = matches / max(len(expected_seq), len(actual_tools), 1)
            else:
                tool_accuracy = 1.0 if task_success else 0.5

            recovery_attempted = (fault_mode in ["RATE_LIMIT_429", "AMBIGUOUS_WRITE_TIMEOUT", "READ_TIMEOUT", "AUTH_EXPIRED_401"])
            recovery_succeeded = recovery_attempted and task_success

            record = CaseEvalRecord(
                case_id=case_id,
                category=category,
                expected_action=expected_action,
                actual_action=actual_action,
                task_success=task_success,
                correct_abstention=correct_abstention,
                false_action=false_action,
                tool_accuracy=min(1.0, tool_accuracy),
                unsafe_action_attempted=not safety_verdict.passed,
                duplicate_action_attempted=not dup_verdict.passed,
                recovery_attempted=recovery_attempted,
                recovery_succeeded=recovery_succeeded,
                steps_consumed=len(runtime.trajectory),
                tool_calls_consumed=runtime.action_count,
                failures_encountered=[fault_mode] if fault_mode else [],
            )
            records.append(record)
            state.close()

        return MetricsCalculator.compute(records)
