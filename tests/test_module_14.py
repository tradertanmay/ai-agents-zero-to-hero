"""
Unit Tests for Module 14: Coding Agents
Tests repository inspection, AST navigation, patch generation, isolated sandbox execution,
safety invariants, verification, and end-to-end repair loops.
"""

import os
import shutil
import sys
import tempfile
import unittest

# Ensure project root is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from examples.coding_assistant.agent import CodingAgent, CodingAgentScorecard
from examples.coding_assistant.ast_tools import extract_function_source, extract_symbols, parse_file_ast
from examples.coding_assistant.patch import apply_targeted_replacement, create_unified_diff, validate_patch_syntax
from examples.coding_assistant.repo import Repository
from examples.coding_assistant.sandbox import ExecutionSandbox
from examples.coding_assistant.search import find_symbol_definition, search_code
from examples.coding_assistant.verifier import PatchSafetyLinter, TestRunResult, TestVerifier


class TestRepository(unittest.TestCase):
    def setUp(self):
        self.demo_dir = os.path.join(PROJECT_ROOT, "14-coding-agents", "demo_repo")
        self.repo = Repository(self.demo_dir)

    def test_list_files(self):
        files = self.repo.list_files()
        self.assertIn("calculator.py", files)
        self.assertIn("parser.py", files)
        self.assertIn("tests/test_calculator.py", files)
        # Verify cache and hidden dirs are excluded
        for f in files:
            self.assertFalse("__pycache__" in f)
            self.assertFalse(f.startswith("."))

    def test_file_info(self):
        info = self.repo.get_file_info("calculator.py")
        self.assertEqual(info["language"], "python")
        self.assertGreater(info["line_count"], 10)
        self.assertGreater(info["size_bytes"], 100)

    def test_read_file_slices(self):
        full = self.repo.read_file("calculator.py")
        self.assertIn("def calculate", full)

        sliced = self.repo.read_file("calculator.py", start_line=6, end_line=10)
        self.assertIn("def calculate", sliced)
        self.assertIn("6 |", sliced)

    def test_detect_entrypoints_and_tests(self):
        detected = self.repo.detect_entrypoints_and_tests()
        self.assertIn("tests/test_calculator.py", detected["test_files"])
        self.assertIn("calculator.py", detected["source_files"])


class TestASTTools(unittest.TestCase):
    def test_parse_valid_and_invalid_ast(self):
        tree = parse_file_ast("def add(a, b): return a + b")
        self.assertIsNotNone(tree)

        with self.assertRaises(SyntaxError):
            parse_file_ast("def broken(:")

    def test_extract_symbols(self):
        code = (
            "def calculate(op, a, b):\n"
            "    '''Do math.'''\n"
            "    return a + b\n\n"
            "class MathHelper:\n"
            "    def helper(self):\n"
            "        pass\n"
        )
        symbols = extract_symbols(code)
        names = [s["name"] for s in symbols]
        self.assertIn("calculate", names)
        self.assertIn("MathHelper", names)

        func_sym = [s for s in symbols if s["name"] == "calculate"][0]
        self.assertEqual(func_sym["type"], "function")
        self.assertEqual(func_sym["args"], ["op", "a", "b"])
        self.assertEqual(func_sym["docstring"], "Do math.")

    def test_extract_function_source(self):
        code = (
            "# Header comment\n"
            "def target_func(x):\n"
            "    return x * 2\n"
            "# Footer comment\n"
        )
        sliced = extract_function_source(code, "target_func")
        self.assertIsNotNone(sliced)
        self.assertIn("def target_func(x):", sliced)
        self.assertIn("return x * 2", sliced)
        self.assertNotIn("Header comment", sliced)


class TestPatchAndDiff(unittest.TestCase):
    def test_create_unified_diff(self):
        orig = "line 1\nline 2\nline 3\n"
        mod = "line 1\nline 2 modified\nline 3\n"
        diff = create_unified_diff(orig, mod, filename="test.txt")
        self.assertIn("--- a/test.txt", diff)
        self.assertIn("+++ b/test.txt", diff)
        self.assertIn("-line 2", diff)
        self.assertIn("+line 2 modified", diff)

    def test_targeted_replacement_success(self):
        orig = "def foo():\n    return 1\n"
        mod = apply_targeted_replacement(orig, "return 1", "return 2")
        self.assertEqual(mod, "def foo():\n    return 2\n")

    def test_targeted_replacement_failure_cases(self):
        orig = "def foo():\n    return 1\n    return 1\n"
        # Non-existent target
        with self.assertRaises(ValueError):
            apply_targeted_replacement(orig, "return 999", "return 2")
        # Ambiguous target (occurs multiple times)
        with self.assertRaises(ValueError):
            apply_targeted_replacement(orig, "return 1", "return 2")

    def test_validate_patch_syntax(self):
        valid, err = validate_patch_syntax("calc.py", "def add(x, y): return x + y")
        self.assertTrue(valid)
        self.assertIsNone(err)

        invalid, err = validate_patch_syntax("calc.py", "def add(x, y return")
        self.assertFalse(invalid)
        self.assertIn("SyntaxError", err)

        non_py, err = validate_patch_syntax("readme.md", "any random text (")
        self.assertTrue(non_py)


class TestExecutionSandbox(unittest.TestCase):
    def setUp(self):
        self.demo_dir = os.path.join(PROJECT_ROOT, "14-coding-agents", "demo_repo")
        self.repo = Repository(self.demo_dir)

    def test_sandbox_isolation_and_cleanup(self):
        sandbox = ExecutionSandbox(self.repo)
        sandbox_path = sandbox.sandbox_path
        self.assertTrue(os.path.isdir(sandbox_path))

        # Check files copied
        self.assertTrue(os.path.isfile(os.path.join(sandbox_path, "calculator.py")))

        # Write to sandbox
        sandbox.apply_patch("calculator.py", "# Modified in sandbox\n")
        self.assertIn("# Modified in sandbox", sandbox.read_file("calculator.py"))
        # Real repo is untouched
        self.assertNotIn("# Modified in sandbox", self.repo.read_file("calculator.py"))

        # Revert file
        sandbox.revert_file("calculator.py")
        self.assertNotIn("# Modified in sandbox", sandbox.read_file("calculator.py"))

        # Cleanup
        sandbox.cleanup()
        self.assertFalse(os.path.exists(sandbox_path))


class TestPatchSafetyLinter(unittest.TestCase):
    def setUp(self):
        self.linter = PatchSafetyLinter(max_lines_changed=10)

    def test_forbid_editing_test_files(self):
        is_safe, violations = self.linter.lint_patch(
            "tests/test_calculator.py",
            "self.assertEqual(1, 1)",
            "self.assertEqual(1, 2)",
        )
        self.assertFalse(is_safe)
        self.assertTrue(any("test file" in v for v in violations))

    def test_forbid_identical_patch(self):
        is_safe, violations = self.linter.lint_patch(
            "calculator.py",
            "return a + b",
            "return a + b",
        )
        self.assertFalse(is_safe)
        self.assertTrue(any("identical" in v for v in violations))

    def test_forbid_syntax_error(self):
        is_safe, violations = self.linter.lint_patch(
            "calculator.py",
            "return a + b",
            "return a +",
        )
        self.assertFalse(is_safe)
        self.assertTrue(any("SyntaxError" in v for v in violations))


class TestCodingAgentRepairLoop(unittest.TestCase):
    def setUp(self):
        self.demo_dir = os.path.join(PROJECT_ROOT, "14-coding-agents", "demo_repo")
        self.temp_workdir = tempfile.mkdtemp(prefix="test_module14_agent_")
        self.cloned_demo = os.path.join(self.temp_workdir, "demo_repo")
        shutil.copytree(self.demo_dir, self.cloned_demo)
        self.repo = Repository(self.cloned_demo)
        self.agent = CodingAgent(self.repo)

    def tearDown(self):
        if os.path.exists(self.temp_workdir):
            shutil.rmtree(self.temp_workdir, ignore_errors=True)

    def test_inspect_repo(self):
        info = self.agent.inspect_repo()
        self.assertIn("calculator.py", info["source_files"])
        self.assertIn("tests/test_calculator.py", info["test_files"])

    def test_baseline_has_failures(self):
        with ExecutionSandbox(self.repo) as sandbox:
            res = self.agent.verifier.run_full_test_suite(sandbox)
            self.assertFalse(res.passed)
            self.assertEqual(res.failed_tests + res.errors, 2)

    def test_full_repair_session_auto_approved(self):
        scorecard = self.agent.run_repair_session(auto_approve=True)

        self.assertTrue(scorecard.task_resolved)
        self.assertEqual(scorecard.initial_failures, 2)
        self.assertEqual(scorecard.final_failures, 0)
        self.assertTrue(scorecard.target_tests_passed)
        self.assertTrue(scorecard.regression_tests_passed)
        self.assertTrue(scorecard.approval_granted)
        self.assertIn("calculator.py", scorecard.files_modified)
        self.assertIn("parser.py", scorecard.files_modified)

        # Verify tests now pass on the working repo after sync
        with ExecutionSandbox(self.repo) as sandbox:
            post_sync = self.agent.verifier.run_full_test_suite(sandbox)
            self.assertTrue(post_sync.is_clean)

    def test_repair_session_without_approval_does_not_mutate_repo(self):
        scorecard = self.agent.run_repair_session(auto_approve=False)

        # In sandbox it succeeded, but approval was not granted so task_resolved is False and repo unmutated
        self.assertFalse(scorecard.approval_granted)
        self.assertFalse(scorecard.task_resolved)

        # Working repo files still contain original bugs
        calc_content = self.repo.read_file("calculator.py")
        self.assertIn("^", calc_content)
        self.assertIn("int(a) ^ int(b)", calc_content)


if __name__ == "__main__":
    unittest.main()
