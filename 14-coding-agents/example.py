"""
Module 14: Coding Agents Example
Demonstrates repository discovery, AST slicing, patch generation, safety linting,
isolated sandbox execution, and test-driven repair loops.
"""

import os
import shutil
import sys
import tempfile

# Ensure project root is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from examples.coding_assistant.agent import CodingAgent
from examples.coding_assistant.ast_tools import extract_function_source, extract_symbols
from examples.coding_assistant.patch import apply_targeted_replacement, create_unified_diff, validate_patch_syntax
from examples.coding_assistant.repo import Repository
from examples.coding_assistant.sandbox import ExecutionSandbox
from examples.coding_assistant.search import find_symbol_definition, search_code
from examples.coding_assistant.verifier import PatchSafetyLinter, TestVerifier


def main() -> None:
    print("=" * 70)
    print("MODULE 14: CODING AGENT COMPONENT WALKTHROUGH")
    print("=" * 70)

    demo_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_repo")
    repo = Repository(demo_dir)

    # 1. Repository Discovery & Tree Mapping
    print("\n--- 1. Repository Discovery ---")
    print(repo.get_file_tree())
    file_info = repo.get_file_info("calculator.py")
    print(f"File info (calculator.py): language={file_info['language']}, lines={file_info['line_count']}")

    # 2. Code Search and Symbol Lookups
    print("\n--- 2. Code Search & Grep ---")
    matches = search_code(repo, "def calculate", is_regex=False)
    for m in matches:
        print(f"Match found in {m['file']}:{m['line_number']} -> {m['line_text']}")

    defs = find_symbol_definition(repo, "calculate")
    print(f"Found {len(defs)} definition site(s) for 'calculate'")

    # 3. Context Engineering via AST Slicing
    print("\n--- 3. AST Slicing (Targeted Context Extraction) ---")
    calc_content = repo.read_file("calculator.py")
    symbols = extract_symbols(calc_content)
    for s in symbols:
        print(f"Symbol: {s['type']} '{s['name']}' on lines {s['start_line']}-{s['end_line']}")

    # Extract ONLY calculate() source, omitting full file context
    func_source = extract_function_source(calc_content, "calculate")
    print(f"Extracted function slice ({len(func_source.splitlines()) if func_source else 0} lines):")
    print(func_source)

    # 4. Patch Safety Linter Invariants
    print("\n--- 4. Patch Safety Linter Invariants ---")
    linter = PatchSafetyLinter(max_lines_changed=20)

    # Test Invariant 1: Forbid editing test files
    is_safe, violations = linter.lint_patch("tests/test_calculator.py", "orig", "mod")
    print(f"Edit to test file allowed? {is_safe} -> Violations: {violations}")

    # Test Invariant 4: Syntax validation
    bad_syntax = "def broken(\n  return 123"
    is_safe, violations = linter.lint_patch("calculator.py", calc_content, bad_syntax)
    print(f"Invalid syntax allowed? {is_safe} -> Violations: {violations}")

    # 5. Sandboxed Repair Loop & Human Approval Gate
    print("\n--- 5. Sandboxed Repair Loop ---")
    # Use temporary working clone so demo_repo remains pristine
    temp_workdir = tempfile.mkdtemp(prefix="module14_example_")
    cloned_demo = os.path.join(temp_workdir, "demo_repo")
    shutil.copytree(demo_dir, cloned_demo)

    try:
        work_repo = Repository(cloned_demo)
        agent = CodingAgent(work_repo)

        # Execute automated repair session
        scorecard = agent.run_repair_session(auto_approve=True)

        print("\n--- 6. Scorecard & Diffs ---")
        print(scorecard.summary())

        for filename, diff in scorecard.diffs.items():
            print(f"\nUnified Diff for {filename}:")
            print(diff)

    finally:
        if os.path.exists(temp_workdir):
            shutil.rmtree(temp_workdir, ignore_errors=True)

    print("\nWalkthrough completed successfully.")


if __name__ == "__main__":
    main()
