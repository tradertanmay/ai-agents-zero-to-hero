"""
Coding Agent Core Loop & Scorecard (Module 14)
Implements: Inspect -> Context Build -> Hypothesize -> Edit -> Sandboxed Test -> Observe -> Verify -> Human Approval.
"""

import ast
from dataclasses import dataclass, field
import os
import re
from typing import Any, Callable

from .ast_tools import extract_function_source, extract_symbols
from .patch import apply_targeted_replacement, create_unified_diff, validate_patch_syntax
from .repo import Repository
from .sandbox import ExecutionSandbox
from .search import find_symbol_definition, search_code
from .verifier import PatchSafetyLinter, TestRunResult, TestVerifier


@dataclass
class CodingAgentScorecard:
    """Summary metrics of a coding agent repair session."""

    task_resolved: bool
    initial_failures: int
    final_failures: int
    target_tests_passed: bool
    regression_tests_passed: bool
    files_modified: list[str] = field(default_factory=list)
    lines_added: int = 0
    lines_removed: int = 0
    iterations_used: int = 0
    syntax_errors_caught: int = 0
    safety_violations_caught: int = 0
    approval_granted: bool = False
    diffs: dict[str, str] = field(default_factory=dict)

    def summary(self) -> str:
        """Returns clean ASCII scorecard output."""
        status = "RESOLVED" if self.task_resolved else "UNRESOLVED"
        lines = [
            "=" * 60,
            f"CODING AGENT SCORECARD: {status}",
            "=" * 60,
            f"Initial Failures:         {self.initial_failures}",
            f"Final Failures:           {self.final_failures}",
            f"Target Tests Passed:      {self.target_tests_passed}",
            f"Regressions Clean:        {self.regression_tests_passed}",
            f"Files Modified:           {', '.join(self.files_modified) if self.files_modified else 'None'}",
            f"Lines Added / Removed:    +{self.lines_added} / -{self.lines_removed}",
            f"Iterations Consumed:      {self.iterations_used}",
            f"Syntax Errors Caught:     {self.syntax_errors_caught}",
            f"Safety Violations Blocked:{self.safety_violations_caught}",
            f"Human Approval Granted:   {self.approval_granted}",
            "=" * 60,
        ]
        return "\n".join(lines)


class CodingAgent:
    """
    Autonomous Coding Agent operating on a repository environment.
    Follows strict test-driven development and sandbox-isolated execution.
    """

    def __init__(
        self,
        repo: Repository,
        verifier: TestVerifier | None = None,
        linter: PatchSafetyLinter | None = None,
        max_iterations: int = 4,
    ) -> None:
        self.repo = repo
        self.verifier = verifier or TestVerifier()
        self.linter = linter or PatchSafetyLinter()
        self.max_iterations = max_iterations
        self.log_messages: list[str] = []

    def log(self, message: str) -> None:
        """Records a timestamped trace message."""
        self.log_messages.append(message)

    def inspect_repo(self) -> dict[str, Any]:
        """Explores codebase layout, tests, and entrypoints."""
        files = self.repo.list_files()
        info = self.repo.detect_entrypoints_and_tests()
        tree = self.repo.get_file_tree()
        self.log(f"Repository inspected: {len(files)} files discovered.")
        return {
            "files": files,
            "test_files": info["test_files"],
            "source_files": info["source_files"],
            "tree": tree,
        }

    def _locate_source_for_test(self, test_name: str, failure_output: str) -> tuple[str, str] | None:
        """
        Infers the source file and target symbol from a test failure name or test imports.
        Example: test_power in test_calculator -> ('calculator.py', 'calculate')
        """
        parts = test_name.split(".")
        test_mod = parts[0] if parts else ""
        test_method = parts[-1] if parts else ""

        # Find corresponding test file in repository
        test_file = None
        for f in self.repo.list_files():
            base = os.path.splitext(os.path.basename(f))[0]
            if base == test_mod or f.endswith(f"/{test_mod}.py"):
                test_file = f
                break

        # Inspect AST of test file to identify imported project symbols
        if test_file:
            try:
                test_content = self.repo.read_file(test_file)
                tree = ast.parse(test_content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module:
                        mod_file = f"{node.module}.py"
                        for src_file in self.repo.list_files():
                            if src_file == mod_file or src_file.endswith(f"/{mod_file}"):
                                for alias in node.names:
                                    return src_file, alias.name
            except Exception:
                pass

        # Fallback heuristic based on module naming convention
        if "calculator" in test_name:
            return "calculator.py", "calculate"
        if "parser" in test_name:
            return "parser.py", "parse_tokens"

        return None

    def formulate_repair_hypothesis(
        self,
        rel_path: str,
        symbol_name: str,
        current_content: str,
        failure_trace: str,
    ) -> tuple[str, str]:
        """
        Analyzes the failure pattern and proposes an exact targeted replacement.
        Demonstrates the hypothesis formation step of the coding loop.
        """
        # Case 1: Exponentiation bitwise XOR bug in calculator
        if "calculate" in symbol_name and "^" in current_content:
            target = "        return float(int(a) ^ int(b))"
            replacement = "        return float(a ** b)"
            if target in current_content:
                return target, replacement

        # Case 2: Naive whitespace tokenization in parser
        if "parse_tokens" in symbol_name and "expression.split()" in current_content:
            target = "    raw_tokens = expression.split()"
            replacement = (
                "    import re\n"
                "    raw_tokens = re.findall(r\"\\d+|[+\\-*/^()]\", expression)"
            )
            if target in current_content:
                return target, replacement

        raise ValueError(f"Could not automatically formulate a repair hypothesis for {rel_path}:{symbol_name}")

    def run_repair_session(
        self,
        target_test_file: str | None = None,
        auto_approve: bool = False,
    ) -> CodingAgentScorecard:
        """
        Runs the full coding agent loop:
        1. Sandbox creation & baseline test run.
        2. Iterative targeted repair & linting.
        3. Regression verification.
        4. Human approval gate.
        5. Sync back to repository on approval.
        """
        self.log("Starting coding agent repair session.")

        with ExecutionSandbox(self.repo) as sandbox:
            # Step 1: Run baseline test suite
            baseline_res = self.verifier.run_full_test_suite(sandbox)
            initial_failures = baseline_res.failed_tests + baseline_res.errors
            self.log(f"Baseline run: {baseline_res.total_tests} tests, {initial_failures} failures.")

            if initial_failures == 0:
                self.log("Baseline is completely clean. No repair required.")
                return CodingAgentScorecard(
                    task_resolved=True,
                    initial_failures=0,
                    final_failures=0,
                    target_tests_passed=True,
                    regression_tests_passed=True,
                    iterations_used=0,
                    approval_granted=True,
                )

            syntax_errors = 0
            safety_violations = 0
            iteration = 0

            # Step 2: Loop through failures and apply repairs
            target_failures = baseline_res.failures
            for fail_info in target_failures:
                if iteration >= self.max_iterations:
                    self.log("Maximum repair iterations reached.")
                    break

                iteration += 1
                self.log(f"Iteration {iteration}: Investigating failure '{fail_info}'")

                # Match failure to source file
                loc = self._locate_source_for_test(fail_info, baseline_res.output)
                if not loc:
                    self.log(f"Could not locate source for failure: {fail_info}")
                    continue

                source_file, symbol_name = loc
                current_source = sandbox.read_file(source_file)

                # Context Building: AST slice extraction
                func_code = extract_function_source(current_source, symbol_name)
                self.log(f"Context built: Extracted {len(func_code.splitlines()) if func_code else 0} lines for {symbol_name}()")

                # Formulate hypothesis
                try:
                    target_chunk, replacement_chunk = self.formulate_repair_hypothesis(
                        source_file, symbol_name, current_source, baseline_res.output
                    )
                except ValueError as e:
                    self.log(f"Hypothesis failure: {e}")
                    continue

                # Edit code via targeted replacement
                try:
                    modified_source = apply_targeted_replacement(current_source, target_chunk, replacement_chunk)
                except ValueError as e:
                    self.log(f"Replacement failed: {e}")
                    continue

                # Invariant Safety Linting
                is_safe, lint_errs = self.linter.lint_patch(source_file, current_source, modified_source)
                if not is_safe:
                    safety_violations += len(lint_errs)
                    self.log(f"Safety linter rejected patch on {source_file}: {lint_errs}")
                    continue

                # Syntax Validation
                is_syntax_valid, syntax_err = validate_patch_syntax(source_file, modified_source)
                if not is_syntax_valid:
                    syntax_errors += 1
                    self.log(f"Syntax validation failed on {source_file}: {syntax_err}")
                    continue

                # Apply to sandbox
                sandbox.apply_patch(source_file, modified_source)
                self.log(f"Applied candidate patch to sandbox for {source_file}")

                # Test verification
                post_test = self.verifier.run_full_test_suite(sandbox)
                if post_test.failed_tests + post_test.errors < initial_failures:
                    self.log(f"Patch improved test suite: {post_test.failed_tests + post_test.errors} failures remaining.")
                else:
                    self.log(f"Patch did not resolve failure or caused regressions. Reverting {source_file}.")
                    sandbox.revert_file(source_file)

            # Step 3: Final verification
            final_res = self.verifier.run_full_test_suite(sandbox)
            final_failures = final_res.failed_tests + final_res.errors
            target_passed = (final_failures == 0)
            regression_clean = (final_failures == 0)

            diffs = sandbox.get_all_diffs()
            files_modified = list(sandbox.modified_files)

            # Compute line statistics
            lines_added = 0
            lines_removed = 0
            for diff_text in diffs.values():
                for line in diff_text.splitlines():
                    if line.startswith("+") and not line.startswith("+++"):
                        lines_added += 1
                    elif line.startswith("-") and not line.startswith("---"):
                        lines_removed += 1

            # Step 4: Human-in-the-loop approval gate
            approval_granted = False
            task_resolved = target_passed and regression_clean and len(files_modified) > 0

            if task_resolved:
                if auto_approve:
                    approval_granted = True
                    sandbox.sync_all_to_repo()
                    self.log("Auto-approval enabled: Patches committed to repository.")
                else:
                    self.log("Awaiting human approval before applying patches to repository.")

            return CodingAgentScorecard(
                task_resolved=task_resolved and approval_granted,
                initial_failures=initial_failures,
                final_failures=final_failures,
                target_tests_passed=target_passed,
                regression_tests_passed=regression_clean,
                files_modified=files_modified,
                lines_added=lines_added,
                lines_removed=lines_removed,
                iterations_used=iteration,
                syntax_errors_caught=syntax_errors,
                safety_violations_caught=safety_violations,
                approval_granted=approval_granted,
                diffs=diffs,
            )
