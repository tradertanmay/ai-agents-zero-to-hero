"""
Unit Tests for Module 15: Self-Improving Agents
Tests candidate isolation, protected verifier boundaries, frozen benchmarks,
holdout quarantine, multi-dimensional promotion gates, rollback governance, and audit trails.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

# Ensure project root is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from examples.self_improving_agent.baseline import BaselineCodingAgent, CandidateCodingAgent, UnsafeCandidateAgent
from examples.self_improving_agent.candidate import CandidateWorkspace
from examples.self_improving_agent.evaluator import EvaluationMetrics, FrozenBenchmarkEvaluator
from examples.self_improving_agent.mutation import AdaptationSurface, MutationProposal, PROTECTED_FILES, is_file_protected
from examples.self_improving_agent.promotion import PromotionGate, PromotionVerdict
from examples.self_improving_agent.proposer import ImprovementProposer
from examples.self_improving_agent.rollback import RollbackManager
from examples.self_improving_agent.versions import VersionInfo, VersionRegistry


class TestModule15SelfImproving(unittest.TestCase):
    def setUp(self):
        self.evals_dir = os.path.join(PROJECT_ROOT, "15-self-improving-agents", "evals")
        self.dev_path = os.path.join(self.evals_dir, "development_cases.json")
        self.reg_path = os.path.join(self.evals_dir, "regression_cases.json")
        self.hold_path = os.path.join(self.evals_dir, "holdout_cases.json")

        self.temp_baseline = tempfile.mkdtemp(prefix="test_baseline_root_")
        # Populate mock baseline directory
        with open(os.path.join(self.temp_baseline, "agent.py"), "w") as f:
            f.write("# Baseline agent code\ncontext = 'naive'\n")
        with open(os.path.join(self.temp_baseline, "verifier.py"), "w") as f:
            f.write("# Protected verifier code\n")

        self.baseline_v1 = VersionInfo(
            version_id="v1.0",
            parent_version=None,
            surface=AdaptationSurface.CODE.value,
            change_summary="Baseline v1.0",
        )
        self.registry = VersionRegistry(initial_version=self.baseline_v1)
        self.gate = PromotionGate(self.registry)
        self.rollback = RollbackManager(self.registry)
        self.evaluator = FrozenBenchmarkEvaluator(self.reg_path, self.hold_path)

    def tearDown(self):
        if os.path.exists(self.temp_baseline):
            shutil.rmtree(self.temp_baseline, ignore_errors=True)

    def test_candidate_cannot_mutate_baseline_directly(self):
        """Verifies that edits applied inside a candidate workspace never touch the baseline repo."""
        with CandidateWorkspace(self.temp_baseline, "v1.1-test") as candidate_ws:
            proposal = MutationProposal(
                surface=AdaptationSurface.CODE,
                target_file="agent.py",
                target_component="context",
                description="Update context builder",
                target_snippet="context = 'naive'",
                replacement_snippet="context = 'optimized'",
                rationale="Testing isolation",
            )
            candidate_ws.apply_mutation(proposal)

            # Candidate file is modified
            self.assertIn("context = 'optimized'", candidate_ws.read_file("agent.py"))

        # Baseline file remains pristine
        with open(os.path.join(self.temp_baseline, "agent.py"), "r") as f:
            baseline_content = f.read()
        self.assertIn("context = 'naive'", baseline_content)
        self.assertNotIn("context = 'optimized'", baseline_content)

    def test_candidate_cannot_modify_protected_verifier_files(self):
        """Verifies that candidate mutations targeting protected verifier files are rejected immediately."""
        with CandidateWorkspace(self.temp_baseline, "v1.1-test") as candidate_ws:
            for protected in ("verifier.py", "safety.py", "approval.py", "promotion.py", "evaluator.py"):
                proposal = MutationProposal(
                    surface=AdaptationSurface.CODE,
                    target_file=protected,
                    target_component="guard",
                    description="Tamper with verifier",
                    target_snippet="",
                    replacement_snippet="# Malicious edit",
                    rationale="Attempting to disable tests",
                )
                with self.assertRaises(PermissionError) as ctx:
                    candidate_ws.apply_mutation(proposal)
                self.assertIn("Security Violation", str(ctx.exception))

    def test_candidate_runs_in_isolated_workspace(self):
        """Verifies candidate workspace isolation, path independence, and cleanup."""
        candidate_ws = CandidateWorkspace(self.temp_baseline, "v1.1-iso")
        ws_path = candidate_ws.workspace_dir

        self.assertTrue(os.path.isdir(ws_path))
        self.assertNotEqual(ws_path, self.temp_baseline)

        candidate_ws.cleanup()
        self.assertFalse(os.path.exists(ws_path))

    def test_frozen_regression_set_is_unchanged(self):
        """Verifies that the frozen regression cases dataset remains intact before and after evals."""
        with open(self.reg_path, "r", encoding="utf-8") as f:
            original_data = json.load(f)

        # Run evaluations
        agent = BaselineCodingAgent()
        self.evaluator.evaluate_regression(agent)

        with open(self.reg_path, "r", encoding="utf-8") as f:
            post_eval_data = json.load(f)

        self.assertEqual(original_data, post_eval_data)
        self.assertEqual(len(post_eval_data), 10)

    def test_holdout_data_inaccessible_to_proposer(self):
        """Verifies that the improvement proposer is strictly forbidden from accessing holdout datasets."""
        proposer = ImprovementProposer()
        with self.assertRaises(PermissionError) as ctx:
            proposer.load_development_cases(self.hold_path)
        self.assertIn("Data Leakage Violation", str(ctx.exception))

        with self.assertRaises(PermissionError):
            proposer.load_development_cases(self.reg_path)

    def test_successful_candidate_may_be_promoted(self):
        """Verifies that a safe, non-regressing candidate improving performance is eligible and promotable."""
        base_agent = BaselineCodingAgent()
        cand_agent = CandidateCodingAgent()

        base_reg = self.evaluator.evaluate_regression(base_agent)
        cand_reg = self.evaluator.evaluate_regression(cand_agent, baseline_results=base_reg)

        base_hold = self.evaluator.evaluate_holdout(base_agent)
        cand_hold = self.evaluator.evaluate_holdout(cand_agent, baseline_results=base_hold)

        verdict = self.gate.evaluate_promotion(base_reg, cand_reg, base_hold, cand_hold)

        self.assertTrue(verdict.eligible)
        self.assertEqual(verdict.verdict, "ELIGIBLE_FOR_HUMAN_REVIEW")
        self.assertGreaterEqual(verdict.regression_delta_success, 0.0)
        self.assertGreaterEqual(verdict.holdout_delta_success, 0.0)

        # Register and promote
        cand_info = VersionInfo(
            version_id="v1.1-candidate",
            parent_version="v1.0",
            surface=AdaptationSurface.CODE.value,
            change_summary="AST optimization",
        )
        self.registry.register_version(cand_info)

        promoted = self.gate.promote("v1.1-candidate", approved_by="senior_engineer", verdict=verdict)
        self.assertEqual(promoted.version_id, "v1.1-candidate")
        self.assertEqual(promoted.promotion_status, "promoted")
        self.assertEqual(self.registry.get_active_version().version_id, "v1.1-candidate")

    def test_unsafe_but_higher_performing_candidate_rejected(self):
        """Flagship Invariant: A candidate with higher overall success but >0% unsafe actions is strictly rejected."""
        base_agent = BaselineCodingAgent()
        unsafe_agent = UnsafeCandidateAgent()

        base_reg = self.evaluator.evaluate_regression(base_agent)
        unsafe_reg = self.evaluator.evaluate_regression(unsafe_agent, baseline_results=base_reg)

        base_hold = self.evaluator.evaluate_holdout(base_agent)
        unsafe_hold = self.evaluator.evaluate_holdout(unsafe_agent, baseline_results=base_hold)

        verdict = self.gate.evaluate_promotion(base_reg, unsafe_reg, base_hold, unsafe_hold)

        # Must be rejected despite 100% test success!
        self.assertFalse(verdict.eligible)
        self.assertEqual(verdict.verdict, "REJECTED")
        self.assertTrue(any("Safety Gate" in r for r in verdict.reasons))

        cand_info = VersionInfo(
            version_id="v1.1-unsafe",
            parent_version="v1.0",
            surface=AdaptationSurface.CODE.value,
            change_summary="Unsafe optimization",
        )
        self.registry.register_version(cand_info)

        with self.assertRaises(PermissionError):
            self.gate.promote("v1.1-unsafe", approved_by="operator", verdict=verdict)

    def test_regressing_candidate_rejected(self):
        """Verifies that a candidate introducing regressions on protected baseline cases is rejected."""
        # Synthetic regression metric
        base_reg = EvaluationMetrics(
            total_cases=10, passed_cases=8, task_success_rate=0.8,
            unsafe_action_count=0, unsafe_action_rate=0.0,
            invariant_violation_count=0, invariant_escape_rate=0.0,
            mean_context_chars=5000, regressions_count=0
        )
        # Candidate passes 8 cases, but broke 2 previously passing baseline cases
        cand_reg = EvaluationMetrics(
            total_cases=10, passed_cases=8, task_success_rate=0.8,
            unsafe_action_count=0, unsafe_action_rate=0.0,
            invariant_violation_count=0, invariant_escape_rate=0.0,
            mean_context_chars=3000, regressions_count=2
        )
        base_hold = EvaluationMetrics(
            total_cases=10, passed_cases=7, task_success_rate=0.7,
            unsafe_action_count=0, unsafe_action_rate=0.0,
            invariant_violation_count=0, invariant_escape_rate=0.0,
            mean_context_chars=5000, regressions_count=0
        )
        cand_hold = EvaluationMetrics(
            total_cases=10, passed_cases=8, task_success_rate=0.8,
            unsafe_action_count=0, unsafe_action_rate=0.0,
            invariant_violation_count=0, invariant_escape_rate=0.0,
            mean_context_chars=3000, regressions_count=0
        )

        verdict = self.gate.evaluate_promotion(base_reg, cand_reg, base_hold, cand_hold)
        self.assertFalse(verdict.eligible)
        self.assertTrue(any("Regression Gate" in r for r in verdict.reasons))

    def test_promotion_requires_explicit_approval(self):
        """Verifies that promotion without an explicit approver identifier raises an error."""
        eligible_verdict = PromotionVerdict(eligible=True, verdict="ELIGIBLE_FOR_HUMAN_REVIEW")
        cand_info = VersionInfo(
            version_id="v1.1-auth-test",
            parent_version="v1.0",
            surface=AdaptationSurface.CODE.value,
            change_summary="Clean candidate",
        )
        self.registry.register_version(cand_info)

        with self.assertRaises(PermissionError):
            self.gate.promote("v1.1-auth-test", approved_by="", verdict=eligible_verdict)

    def test_old_version_remains_recoverable(self):
        """Verifies that promoting a new version does not delete or overwrite ancestor versions."""
        cand_info = VersionInfo(
            version_id="v1.1-ancestor",
            parent_version="v1.0",
            surface=AdaptationSurface.CODE.value,
            change_summary="Ancestor test",
        )
        self.registry.register_version(cand_info)
        self.gate.promote("v1.1-ancestor", approved_by="admin", verdict=PromotionVerdict(eligible=True, verdict="ELIGIBLE_FOR_HUMAN_REVIEW"))

        self.assertEqual(self.registry.get_active_version().version_id, "v1.1-ancestor")
        # v1.0 remains fully intact
        v1_info = self.registry.get_version("v1.0")
        self.assertIsNotNone(v1_info)
        self.assertEqual(v1_info.version_id, "v1.0")

    def test_rollback_restores_prior_version(self):
        """Verifies that rollback reinstates the prior version and updates its status."""
        cand_info = VersionInfo(
            version_id="v1.1-rollback-test",
            parent_version="v1.0",
            surface=AdaptationSurface.CODE.value,
            change_summary="Candidate to be rolled back",
        )
        self.registry.register_version(cand_info)
        self.gate.promote("v1.1-rollback-test", approved_by="admin", verdict=PromotionVerdict(eligible=True, verdict="ELIGIBLE_FOR_HUMAN_REVIEW"))

        self.assertEqual(self.registry.get_active_version().version_id, "v1.1-rollback-test")

        restored = self.rollback.rollback_to_parent(reason="Simulated production alert.")
        self.assertEqual(restored.version_id, "v1.0")
        self.assertEqual(self.registry.get_active_version().version_id, "v1.0")
        self.assertEqual(self.registry.get_version("v1.1-rollback-test").promotion_status, "rolled_back")

    def test_all_changes_leave_an_audit_trail(self):
        """Verifies that every lifecycle transition records an immutable audit log entry."""
        initial_count = len(self.registry.get_audit_trail())
        self.assertGreaterEqual(initial_count, 1)

        cand_info = VersionInfo(
            version_id="v1.1-audit",
            parent_version="v1.0",
            surface=AdaptationSurface.CODE.value,
            change_summary="Audit trial",
        )
        self.registry.register_version(cand_info)
        self.gate.promote("v1.1-audit", approved_by="auditor_jane", verdict=PromotionVerdict(eligible=True, verdict="ELIGIBLE_FOR_HUMAN_REVIEW"))
        self.rollback.rollback_to_parent(reason="Audit rollback verification.")

        trail = self.registry.get_audit_trail()
        actions = [entry["action"] for entry in trail]
        self.assertIn("REGISTER_VERSION", actions)
        self.assertIn("PROMOTE_VERSION", actions)
        self.assertIn("ROLLBACK", actions)

        for entry in trail:
            self.assertIn("timestamp", entry)
            self.assertIn("version_id", entry)
            self.assertIn("detail", entry)


if __name__ == "__main__":
    unittest.main()
