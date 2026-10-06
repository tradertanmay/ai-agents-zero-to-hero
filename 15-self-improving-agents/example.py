"""
Module 15: Self-Improving Agents Example
Demonstrates the 5 adaptation surfaces, candidate isolation, multi-dimensional evaluation,
holdout generalization, human promotion gating, and rollback governance.
"""

import os
import sys

# Ensure project root is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from examples.self_improving_agent.baseline import BaselineCodingAgent, CandidateCodingAgent, UnsafeCandidateAgent
from examples.self_improving_agent.candidate import CandidateWorkspace
from examples.self_improving_agent.evaluator import FrozenBenchmarkEvaluator
from examples.self_improving_agent.mutation import AdaptationSurface, MutationProposal, SURFACE_RISK_HIERARCHY
from examples.self_improving_agent.promotion import PromotionGate
from examples.self_improving_agent.proposer import ImprovementProposer
from examples.self_improving_agent.rollback import RollbackManager
from examples.self_improving_agent.versions import VersionInfo, VersionRegistry


def main() -> None:
    print("=" * 70)
    print("MODULE 15: SELF-IMPROVEMENT WORKFLOW WALKTHROUGH")
    print("=" * 70)

    # 1. Review the 5 Adaptation Surfaces and Blast Radii
    print("\n--- 1. The 5 Adaptation Surfaces & Blast Radii ---")
    for surface, info in SURFACE_RISK_HIERARCHY.items():
        print(f"Level {info['level']}: {surface.value.upper():<10} (Risk: {info['risk']:<8}) -> {info['description']}")

    # 2. Version Registry Setup
    print("\n--- 2. Version Registry Initialization ---")
    v1_baseline = VersionInfo(
        version_id="v1.0",
        parent_version=None,
        surface=AdaptationSurface.CODE.value,
        change_summary="Baseline release with naive context assembly.",
    )
    registry = VersionRegistry(initial_version=v1_baseline)
    print(f"Active Production Version: {registry.get_active_version().version_id}")

    # 3. Development Failure Observation & Proposal
    print("\n--- 3. Development Failure Analysis ---")
    evals_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evals")
    dev_path = os.path.join(evals_dir, "development_cases.json")

    proposer = ImprovementProposer(dev_path)
    counts = proposer.analyze_failure_modes()
    for ftype, c in counts.items():
        print(f"  Observed Failure '{ftype}': {c} cases")

    proposal = proposer.propose_improvement()
    print(f"\nProposer formulated mutation proposal:")
    print(f"  Target: {proposal.target_file}")
    print(f"  Action: {proposal.description}")

    # 4. Prover Holdout Boundary Invariant
    print("\n--- 4. Enforcing Holdout Boundary Invariant ---")
    try:
        proposer.load_development_cases(os.path.join(evals_dir, "holdout_cases.json"))
        print("ERROR: Proposer loaded holdout cases!")
    except PermissionError as e:
        print(f"Verified Security Guard: {e}")

    # 5. Multi-Dimensional Evaluation (Baseline vs Candidate)
    print("\n--- 5. Frozen Benchmark Evaluation ---")
    reg_path = os.path.join(evals_dir, "regression_cases.json")
    hold_path = os.path.join(evals_dir, "holdout_cases.json")
    evaluator = FrozenBenchmarkEvaluator(reg_path, hold_path)

    baseline_agent = BaselineCodingAgent()
    candidate_agent = CandidateCodingAgent()

    base_reg = evaluator.evaluate_regression(baseline_agent)
    cand_reg = evaluator.evaluate_regression(candidate_agent, baseline_results=base_reg)

    base_hold = evaluator.evaluate_holdout(baseline_agent)
    cand_hold = evaluator.evaluate_holdout(candidate_agent, baseline_results=base_hold)

    print(f"Regression Success: Baseline={base_reg.task_success_rate*100:.1f}% -> Candidate={cand_reg.task_success_rate*100:.1f}%")
    print(f"Holdout Success:    Baseline={base_hold.task_success_rate*100:.1f}% -> Candidate={cand_hold.task_success_rate*100:.1f}%")
    print(f"Regressions:        {cand_reg.regressions_count}")
    print(f"Unsafe Rate:        {cand_reg.unsafe_action_rate*100:.1f}%")
    print(f"Mean Context:       {base_reg.mean_context_chars:.0f} chars -> {cand_reg.mean_context_chars:.0f} chars")

    # 6. Promotion Gate Decision
    print("\n--- 6. Promotion Gate Evaluation ---")
    gate = PromotionGate(registry)
    verdict = gate.evaluate_promotion(base_reg, cand_reg, base_hold, cand_hold)
    print(f"Verdict: {verdict.verdict} (Eligible: {verdict.eligible})")

    # 7. Promotion and Rollback Demonstration
    print("\n--- 7. Promotion and Rollback Execution ---")
    candidate_v11 = VersionInfo(
        version_id="v1.1-candidate",
        parent_version="v1.0",
        surface=AdaptationSurface.CODE.value,
        change_summary="Traceback AST localization.",
    )
    registry.register_version(candidate_v11)

    # Formal human promotion
    gate.promote("v1.1-candidate", approved_by="admin_lead", verdict=verdict)
    print(f"Promoted! Active Version is now: {registry.get_active_version().version_id}")

    # Rollback
    rollback = RollbackManager(registry)
    restored = rollback.rollback_to_parent(reason="Canary test regression trigger.")
    print(f"Rollback complete! Active Version restored to: {registry.get_active_version().version_id}")

    print("\n" + "=" * 70)
    print("A system should earn the right to change itself through evidence, not confidence.")
    print("=" * 70)


if __name__ == "__main__":
    main()
