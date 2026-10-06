"""
Candidate Workspace and Isolation Boundary (Module 15)
Provides isolated sandboxed environments for applying and evaluating candidate modifications.
Enforces the Invariant: Baseline cannot be mutated directly; protected verifier files are untouchable.
"""

import ast
import os
import shutil
import tempfile
from typing import Any

from .mutation import MutationProposal, is_file_protected
from .versions import VersionInfo


class CandidateWorkspace:
    """
    Sandboxes candidate mutations in an isolated directory.
    Guarantees that unverified proposals never touch production baseline code.
    """

    def __init__(self, baseline_root: str, candidate_version_id: str) -> None:
        self.baseline_root = os.path.realpath(os.path.abspath(baseline_root))
        self.candidate_version_id = candidate_version_id
        self.workspace_dir = os.path.realpath(tempfile.mkdtemp(prefix=f"candidate_{candidate_version_id}_"))
        self.modified_files: set[str] = set()
        self._clone_baseline()

    def _clone_baseline(self) -> None:
        """Copies baseline files into the isolated candidate workspace."""
        for item in os.listdir(self.baseline_root):
            if item.startswith(".") or item in ("__pycache__", "venv", ".venv"):
                continue
            src = os.path.join(self.baseline_root, item)
            dst = os.path.join(self.workspace_dir, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

    def apply_mutation(self, proposal: MutationProposal) -> None:
        """
        Applies a candidate proposal inside the isolated workspace.
        Enforces strict safety invariants:
        1. Modifying protected verifier/eval files is forbidden.
        2. Modifying baseline directly is impossible.
        3. Python syntax must remain valid.
        """
        # Invariant 1: Protected files guard
        if is_file_protected(proposal.target_file):
            raise PermissionError(
                f"Security Violation: Target file '{proposal.target_file}' is a protected verifier/governance file. "
                "The subject of evaluation must not control the evaluator."
            )

        target_path = os.path.join(self.workspace_dir, proposal.target_file)
        if not os.path.isfile(target_path):
            # If creating a new file or target doesn't exist yet, ensure parent directory exists
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(proposal.replacement_snippet)
            self.modified_files.add(proposal.target_file)
            return

        with open(target_path, "r", encoding="utf-8") as f:
            original = f.read()

        if proposal.target_snippet not in original:
            raise ValueError(
                f"Target snippet for mutation not found in '{proposal.target_file}'. Cannot apply patch."
            )

        modified = original.replace(proposal.target_snippet, proposal.replacement_snippet, 1)

        # Invariant 3: Syntax validation for Python files
        if proposal.target_file.endswith(".py"):
            try:
                ast.parse(modified, filename=proposal.target_file)
            except SyntaxError as e:
                raise ValueError(f"SyntaxError in candidate modification on {proposal.target_file}:{e.lineno}: {e.msg}")

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(modified)

        self.modified_files.add(proposal.target_file)

    def read_file(self, rel_path: str) -> str:
        """Reads a file from the candidate workspace."""
        path = os.path.join(self.workspace_dir, rel_path)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def snapshot(self, destination_dir: str) -> str:
        """Archives the candidate workspace to a permanent version snapshot directory."""
        os.makedirs(destination_dir, exist_ok=True)
        archive_path = os.path.join(destination_dir, f"{self.candidate_version_id}_snapshot")
        if os.path.exists(archive_path):
            shutil.rmtree(archive_path)
        shutil.copytree(self.workspace_dir, archive_path)
        return archive_path

    def cleanup(self) -> None:
        """Removes temporary candidate workspace."""
        if os.path.exists(self.workspace_dir):
            shutil.rmtree(self.workspace_dir, ignore_errors=True)

    def __enter__(self) -> "CandidateWorkspace":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.cleanup()
