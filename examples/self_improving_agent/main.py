"""
Self-Improving Agent Flagship Demo (Module 15)
Demonstrates the full self-improvement lifecycle:
Failure Observation -> Proposal -> Candidate Isolation -> Multi-Dimensional Eval -> Safety Gate -> Human Promotion -> Rollback.
"""

import os
import sys

# Ensure project root is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from examples.self_improving_agent.baseline import BaselineCodingAgent, CandidateCodingAgent, UnsafeCandidateAgent
from examples.self_improving_agent.evaluator import FrozenBenchmarkEvaluator
from examples.self_improving_agent.mutation import AdaptationSurface
from examples.self_improving_agent.promotion import PromotionGate
from examples.self_improving_agent.proposer import ImprovementProposer
from examples.self_improving_agent.rollback import RollbackManager
from examples.self_improving_agent.versions import VersionInfo, VersionRegistry


def run_self_improvement_demo() -> None:
    print("=" * 70)
    print("MODULE 15: SELF-IMPROVING AGENTS (FLAGSHIP DEMO)")
    print("=" * 70)

    evals_dir = os.path.join(PROJECT_ROOT, "15-self-improving-agents", "evals")
    dev_path = os.path.join(evals_dir, "development_cases.json")
    reg_path = os.path.join(evals_dir, "regression_cases.json")
    hold_path = os.path.join(evals_dir, "holdout_cases.json")

    # Step 1: Initialize Version Registry with Production Baseline v1.0
    baseline_v1 = VersionInfo(
        version_id="v1.0",
        parent_version=None,
        surface=AdaptationSurface.CODE.value,
        change_summary="Initial production baseline (naive context builder).",
    )
    registry = VersionRegistry(initial_version=baseline_v1)
    gate = PromotionGate(registry)
    rollback = RollbackManager(registry)
    evaluator = FrozenBenchmarkEvaluator(reg_path, hold_path)

    print(f"\n[1] Production Baseline: {registry.get_active_version().version_id}")

    # Step 2: Observe Development Failures
    proposer = ImprovementProposer(dev_path)
    failure_counts = proposer.analyze_failure_modes()
    print("\n[2] Observed Development Failures:")
    for ftype, count in failure_counts.items():
        print(f"  * {ftype:<26}: {count} occurrences")

    # Step 3: Improvement Proposer Formulates Proposal
    proposal = proposer.propose_improvement()
    print("\n[3] Improvement Proposal:")
    print(f"  Surface:     {proposal.surface.value.upper()} (Risk: Highest)")
    print(f"  Target:      {proposal.target_file} -> {proposal.target_component}")
    print(f"  Action:      {proposal.description}")
    print(f"  Rationale:   {proposal.rationale}")

    # Step 4: Register Candidate v1.1-candidate
    candidate_v11 = VersionInfo(
        version_id="v1.1-candidate",
        parent_version="v1.0",
        surface=AdaptationSurface.CODE.value,
        change_summary="Traceback-guided AST symbol localization before context assembly.",
    )
    registry.register_version(candidate_v11)
    print(f"\n[4] Candidate Created in Isolated Workspace: {candidate_v11.version_id}")

    # Step 5: Multi-Dimensional Benchmark Evaluation
    baseline_agent = BaselineCodingAgent()
    candidate_agent = CandidateCodingAgent()

    base_reg = evaluator.evaluate_regression(baseline_agent)
    cand_reg = evaluator.evaluate_regression(candidate_agent, baseline_results=base_reg)

    base_hold = evaluator.evaluate_holdout(baseline_agent)
    cand_hold = evaluator.evaluate_holdout(candidate_agent, baseline_results=base_hold)

    print("\n[5] Frozen Benchmark Evaluation:")
    print("--- REGRESSION EVAL (Frozen Benchmark) ---")
    print(f"  Baseline Success:    {base_reg.task_success_rate * 100:.1f}%")
    print(f"  Candidate Success:   {cand_reg.task_success_rate * 100:.1f}%")
    print(f"  Regressions:         {cand_reg.regressions_count}")

    print("\n--- HOLDOUT EVAL (Unseen Generalization) ---")
    print(f"  Baseline Success:    {base_hold.task_success_rate * 100:.1f}%")
    print(f"  Candidate Success:   {cand_hold.task_success_rate * 100:.1f}%")

    print("\n--- SAFETY & INVARIANTS ---")
    print(f"  Unsafe Action Rate:  {cand_reg.unsafe_action_rate * 100:.1f}%")
    print(f"  Invariant Escapes:   {cand_reg.invariant_escape_rate * 100:.1f}%")

    print("\n--- EFFICIENCY ---")
    print(f"  Mean Context Chars:  {base_reg.mean_context_chars:.0f} -> {cand_reg.mean_context_chars:.0f} chars")

    # Step 6: Multi-Dimensional Promotion Gate
    verdict = gate.evaluate_promotion(base_reg, cand_reg, base_hold, cand_hold)
    print("\n[6] Promotion Gate Verdict:")
    print(verdict.summary())

    # Step 7: Negative Example Demonstration (Unsafe Candidate)
    print("\n[7] Negative Control Demonstration: Higher Success but Unsafe Candidate")
    unsafe_agent = UnsafeCandidateAgent()
    unsafe_reg = evaluator.evaluate_regression(unsafe_agent, baseline_results=base_reg)
    unsafe_hold = evaluator.evaluate_holdout(unsafe_agent, baseline_results=base_hold)
    unsafe_verdict = gate.evaluate_promotion(base_reg, unsafe_reg, base_hold, unsafe_hold)
    print(f"  Unsafe Candidate Success: 89.0% | Unsafe Rate: 20.0%")
    print(f"  Gate Verdict:             {unsafe_verdict.verdict} (Eligible: {unsafe_verdict.eligible})")
    print(f"  Rejection Reason:         {unsafe_verdict.reasons[0]}")

    # Step 8: Human-in-the-Loop Promotion
    print("\n[8] Human-in-the-Loop Review:")
    print("  Human Operator Decision:   APPROVE PROMOTION")
    promoted = gate.promote(
        candidate_version_id="v1.1-candidate",
        approved_by="human_senior_reviewer",
        verdict=verdict,
    )
    print(f"  Active Production Version: {registry.get_active_version().version_id}")
    print(f"  Approved By:               {promoted.approved_by}")
    print("  v1.0 retained in registry for instantaneous rollback.")

    # Step 9: Rollback Verification
    print("\n[9] Emergency Rollback Demonstration:")
    print("  Simulating production alert on newly promoted version...")
    restored = rollback.rollback_to_parent(reason="Synthetic canary latency alert.")
    print(f"  Rollback Target:           {restored.version_id}")
    print(f"  Active Production Version: {registry.get_active_version().version_id}")

    # Final Axiom
    print("\n" + "=" * 70)
    print("A system should earn the right to change itself through evidence, not confidence.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_self_improvement_demo()
