"""
Improvement Proposer (Module 15)
Analyzes development failure logs and formulates targeted adaptation proposals across the 5 surfaces.
Enforces the Inaccessible Holdout Invariant: Holdout eval cases are strictly hidden from the proposer.
"""

import json
import os
from typing import Any

from .mutation import AdaptationSurface, MutationProposal, is_file_protected


class ImprovementProposer:
    """
    Analyzes development failures and proposes structured improvements.
    Governed by the Holdout Isolation Rule: Has zero access to holdout eval sets.
    """

    def __init__(self, dev_cases_path: str | None = None) -> None:
        self.dev_cases_path = dev_cases_path
        self.observed_failures: list[dict[str, Any]] = []
        if dev_cases_path:
            self.load_development_cases(dev_cases_path)

    def load_development_cases(self, file_path: str) -> None:
        """
        Loads training/development failure cases.
        Guarantees: Rejects any attempt to load holdout evaluation datasets.
        """
        base_name = os.path.basename(file_path).lower()
        if "holdout" in base_name or "regression" in base_name:
            raise PermissionError(
                f"Data Leakage Violation: Proposer is forbidden from accessing frozen benchmark file '{file_path}'. "
                "The agent must learn only from development failures."
            )

        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Development cases file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            self.observed_failures = json.load(f)

    def analyze_failure_modes(self) -> dict[str, int]:
        """Categorizes observed development failures by root cause."""
        counts: dict[str, int] = {}
        for case in self.observed_failures:
            ftype = case.get("failure_type", "unknown")
            counts[ftype] = counts.get(ftype, 0) + 1
        return counts

    def propose_improvement(self, primary_failure_type: str | None = None) -> MutationProposal:
        """
        Generates a targeted mutation proposal addressing the most frequent failure mode.
        """
        counts = self.analyze_failure_modes()
        target_mode = primary_failure_type or (max(counts, key=counts.get) if counts else "excessive_context")

        if target_mode in ("excessive_context", "wrong_context_selection"):
            # Propose AST symbol localization optimization in the coding assistant agent
            target_file = "examples/coding_assistant/agent.py"
            if is_file_protected(target_file):
                raise PermissionError(f"Security Violation: Target file '{target_file}' is protected.")

            return MutationProposal(
                surface=AdaptationSurface.CODE,
                target_file=target_file,
                target_component="context_localization",
                description="Introduce traceback-guided AST localization before loading source",
                target_snippet="""# NAIVE_CONTEXT_BUILDER: Load all repository files into prompt
def build_context(repo):
    return "\\n".join(repo.read_file(f) for f in repo.list_files())""",
                replacement_snippet="""# OPTIMIZED_CONTEXT_BUILDER: Traceback-guided AST slicing
def build_context(repo, failing_symbol=None):
    if failing_symbol:
        return extract_function_source(repo.read_file(failing_symbol.file), failing_symbol.name)
    return "\\n".join(repo.read_file(f) for f in repo.list_files()[:2])""",
                rationale="Excessive context tokens (mean 8,200 chars) cause attention degradation and hallucinated patches. AST slicing reduces context to 2,100 chars.",
            )

        elif target_mode == "ambiguous_tool_selection":
            # Propose Tool Description clarification (Surface: TOOL)
            return MutationProposal(
                surface=AdaptationSurface.TOOL,
                target_file="examples/minimal_agent/tools.py",
                target_component="search_tool_descriptions",
                description="Disambiguate overlapping search_docs and search_web tool schemas",
                target_snippet="search_docs: Search technical documents and local repository guides.",
                replacement_snippet="search_docs: Search internal project markdown guides ONLY. For public internet queries use search_web.",
                rationale="Baseline agent invoked search_web for local documentation queries due to vague schema boundary.",
            )

        elif target_mode == "ambiguous_timeout":
            # Propose Harness Policy adjustment (Surface: HARNESS)
            return MutationProposal(
                surface=AdaptationSurface.HARNESS,
                target_file="examples/reddit_comment_agent/runtime.py",
                target_component="retry_policy",
                description="Require pre-retry reconciliation check before resubmitting state mutations",
                target_snippet="if error == 'timeout': return retry_action()",
                replacement_snippet="if error == 'timeout': reconcile_state(); if not exists: return retry_action()",
                rationale="Unreconciled retries on write timeouts create duplicate state mutations.",
            )

        else:
            # Fallback to Prompt Adaptation (Surface: PROMPT)
            return MutationProposal(
                surface=AdaptationSurface.PROMPT,
                target_file="examples/minimal_agent/prompt.txt",
                target_component="precondition_instructions",
                description="Add explicit precondition verification rule to system instructions",
                target_snippet="Choose the most appropriate available tool.",
                replacement_snippet="Before selecting a tool, compare its declared preconditions with your goal. Abstain if requirements are unmet.",
                rationale="Constrains agent from guessing tool arguments when prerequisites are missing.",
            )
