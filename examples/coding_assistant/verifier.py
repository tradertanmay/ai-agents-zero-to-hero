"""
Test Verifier and Patch Safety Linter (Module 14)
Runs sandboxed test suites, parses test failures/tracebacks, and enforces patch safety invariants.
"""

from dataclasses import dataclass, field
import os
import re
import sys

from .patch import validate_patch_syntax
from .sandbox import ExecutionSandbox


@dataclass
class TestRunResult:
    """Represents the outcome of a test suite or targeted test execution."""

    passed: bool
    total_tests: int
    failed_tests: int
    errors: int
    output: str
    failures: list[str] = field(default_factory=list)
    tracebacks: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        """Returns True if all tests passed with zero failures or errors."""
        return self.passed and self.failed_tests == 0 and self.errors == 0


class TestVerifier:
    """Discovers, executes, and parses test results within the isolated sandbox."""

    def __init__(self, python_executable: str = sys.executable) -> None:
        self.python_executable = python_executable

    def _parse_unittest_output(self, stdout: str, stderr: str, returncode: int) -> TestRunResult:
        """Parses standard library unittest output from stdout and stderr."""
        combined = f"{stdout}\n{stderr}".strip()

        # Parse total tests count: "Ran 5 tests in 0.002s"
        total_match = re.search(r"Ran (\d+) test", combined)
        total_tests = int(total_match.group(1)) if total_match else 0

        # Parse failures and errors
        failures_count = 0
        errors_count = 0
        fail_match = re.search(r"failures=(\d+)", combined)
        if fail_match:
            failures_count = int(fail_match.group(1))
        err_match = re.search(r"errors=(\d+)", combined)
        if err_match:
            errors_count = int(err_match.group(1))

        # Check for OK line vs FAILED
        passed = (returncode == 0) and (failures_count == 0) and (errors_count == 0)
        if "FAILED" in combined and passed:
            passed = False

        # Extract failed test method names: "FAIL: test_power (test_calculator.TestCalculator)"
        failures = []
        for line in combined.splitlines():
            fail_line = re.match(r"^(FAIL|ERROR):\s+([a-zA-Z0-9_]+)\s+\((.+)\)", line)
            if fail_line:
                failures.append(f"{fail_line.group(3)}.{fail_line.group(2)}")

        # Extract tracebacks
        tracebacks = []
        sections = combined.split("======================================================================")
        if len(sections) > 1:
            for s in sections[1:]:
                tb = s.strip()
                if tb:
                    tracebacks.append(tb)

        return TestRunResult(
            passed=passed,
            total_tests=total_tests,
            failed_tests=failures_count,
            errors=errors_count,
            output=combined,
            failures=failures,
            tracebacks=tracebacks,
        )

    def run_targeted_test(
        self,
        sandbox: ExecutionSandbox,
        test_file: str,
        test_case: str | None = None,
        timeout: float = 10.0,
    ) -> TestRunResult:
        """
        Runs a specific test file or test case in the sandbox.
        Example: test_file="tests/test_calculator.py", test_case="TestCalculator.test_power"
        """
        cmd = [self.python_executable, "-m", "unittest"]
        target = test_file
        if test_case:
            target = f"{test_file} {test_case}"
            cmd.extend(target.split())
        else:
            cmd.append(test_file)

        proc = sandbox.run_command(cmd, timeout=timeout)
        return self._parse_unittest_output(proc.stdout, proc.stderr, proc.returncode)

    def run_full_test_suite(
        self,
        sandbox: ExecutionSandbox,
        start_dir: str = "tests",
        timeout: float = 20.0,
    ) -> TestRunResult:
        """Discovers and executes all tests in the sandbox to verify no regressions occurred."""
        # Check if tests directory exists in sandbox
        search_dir = start_dir if os.path.isdir(os.path.join(sandbox.sandbox_path, start_dir)) else "."
        cmd = [
            self.python_executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            search_dir,
            "-v",
        ]
        proc = sandbox.run_command(cmd, timeout=timeout)
        return self._parse_unittest_output(proc.stdout, proc.stderr, proc.returncode)


class PatchSafetyLinter:
    """
    Enforces strict safety invariants on candidate patches before applying or testing.
    Protects against test evasion, scope explosion, and invalid code syntax.
    """

    def __init__(self, max_lines_changed: int = 50) -> None:
        self.max_lines_changed = max_lines_changed

    def lint_patch(
        self,
        rel_path: str,
        original_content: str,
        modified_content: str,
    ) -> tuple[bool, list[str]]:
        """
        Verifies safety invariants:
        1. Modifying test files is forbidden (prevents test evasion).
        2. Content must actually differ (no empty edits).
        3. Line budget must not be exceeded.
        4. Python syntax must be valid.
        """
        violations: list[str] = []

        # Invariant 1: Forbid edits to test files
        normalized = rel_path.lower()
        if (
            normalized.startswith("test")
            or "/test" in normalized
            or "\\test" in normalized
            or normalized.endswith("_test.py")
        ):
            violations.append(
                f"Patch safety violation: Editing test file '{rel_path}' is forbidden. "
                "The agent must fix the implementation, not alter test assertions."
            )

        # Invariant 2: Non-empty modification
        if original_content == modified_content:
            violations.append("Patch safety violation: Modified content is identical to original content.")

        # Invariant 3: Line change budget
        orig_lines = original_content.splitlines()
        mod_lines = modified_content.splitlines()
        lines_changed = abs(len(mod_lines) - orig_lines_diff_count(orig_lines, mod_lines))
        if lines_changed > self.max_lines_changed:
            violations.append(
                f"Patch safety violation: Changed lines ({lines_changed}) exceeds limit of {self.max_lines_changed}."
            )

        # Invariant 4: Python syntax validation
        if rel_path.endswith(".py"):
            valid, err = validate_patch_syntax(rel_path, modified_content)
            if not valid and err:
                violations.append(f"Patch safety violation: {err}")

        is_valid = len(violations) == 0
        return is_valid, violations


def orig_lines_diff_count(orig: list[str], mod: list[str]) -> int:
    """Helper to compute approximate count of identical matching lines."""
    s_orig = set(orig)
    s_mod = set(mod)
    return len(s_orig.intersection(s_mod))
