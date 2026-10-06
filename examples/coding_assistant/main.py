"""
Coding Assistant Demo Runner (Module 14)
Demonstrates the full autonomous coding agent loop on demo_repo:
Discovery -> Inspection -> Failure Localization -> AST Slicing -> Sandboxed Repair -> Verification -> Scorecard.
"""

import os
import shutil
import sys
import tempfile

from .agent import CodingAgent
from .ast_tools import extract_function_source, extract_symbols
from .patch import create_unified_diff
from .repo import Repository
from .sandbox import ExecutionSandbox
from .verifier import PatchSafetyLinter, TestVerifier


def run_demo(target_repo_path: str | None = None) -> None:
    """Runs a complete end-to-end coding agent session."""
    print("=" * 70)
    print("MODULE 14: AUTONOMOUS CODING AGENT DEMO")
    print("=" * 70)

    # Use specified path or copy demo_repo to a temporary working directory
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    default_demo = os.path.join(base_dir, "14-coding-agents", "demo_repo")

    if not target_repo_path:
        # Create a fresh working copy so the base demo_repo stays pristine for tests
        temp_workdir = tempfile.mkdtemp(prefix="coding_agent_demo_")
        target_path = os.path.join(temp_workdir, "demo_repo")
        shutil.copytree(default_demo, target_path)
        is_temp = True
    else:
        target_path = target_repo_path
        is_temp = False

    try:
        repo = Repository(target_path)
        print(f"\n[1] Target Repository: {target_path}")
        print("\n--- Repository Structure ---")
        print(repo.get_file_tree())

        # Inspect entrypoints and test files
        agent = CodingAgent(repo)
        meta = agent.inspect_repo()
        print(f"\nDiscovered {len(meta['files'])} files:")
        print(f"  Source files: {meta['source_files']}")
        print(f"  Test files:   {meta['test_files']}")

        # AST Inspection
        print("\n[2] AST Symbol Navigation:")
        for src in meta["source_files"]:
            content = repo.read_file(src)
            symbols = extract_symbols(content)
            for sym in symbols:
                print(f"  File '{src}' -> {sym['type']} '{sym['name']}' (lines {sym['start_line']}-{sym['end_line']})")

        # Run Repair Session
        print("\n[3] Executing Sandboxed Repair Loop...")
        scorecard = agent.run_repair_session(auto_approve=True)

        print("\n[4] Execution Log:")
        for log_msg in agent.log_messages:
            print(f"  * {log_msg}")

        print("\n[5] Generated Unified Diffs:")
        for file_path, diff_content in scorecard.diffs.items():
            print(f"\n--- Diff for {file_path} ---")
            print(diff_content)

        print("\n[6] Final Scorecard:")
        print(scorecard.summary())

    finally:
        if is_temp and os.path.exists(temp_workdir):
            shutil.rmtree(temp_workdir, ignore_errors=True)


if __name__ == "__main__":
    run_demo()
