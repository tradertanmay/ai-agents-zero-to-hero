"""
Execution Sandbox (Module 14)
Provides isolated filesystem copying, sandboxed execution, diff tracking, and repo syncing.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from .patch import create_unified_diff
from .repo import IGNORE_DIRS, Repository


class ExecutionSandbox:
    """
    Isolates repository modifications and command execution in a temporary directory.
    Guarantees that unverified trial edits never touch the real codebase.
    """

    def __init__(self, repo: Repository) -> None:
        self.repo = repo
        self.sandbox_path = os.path.realpath(tempfile.mkdtemp(prefix="coding_agent_sandbox_"))
        self.modified_files: set[str] = set()
        self._copy_repo_to_sandbox()

    def _copy_repo_to_sandbox(self) -> None:
        """Copies all non-ignored repository files to the sandbox directory."""
        for rel_path in self.repo.list_files():
            src = os.path.join(self.repo.root_path, rel_path)
            dst = os.path.join(self.sandbox_path, rel_path)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)

    def read_file(self, rel_path: str) -> str:
        """Reads a file from the sandbox."""
        abs_path = os.path.join(self.sandbox_path, rel_path)
        if not os.path.isfile(abs_path):
            raise FileNotFoundError(f"File '{rel_path}' does not exist in sandbox.")
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def write_file(self, rel_path: str, content: str) -> None:
        """Writes content to a sandboxed file, tracking modification."""
        abs_path = os.path.join(self.sandbox_path, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        self.modified_files.add(rel_path)

    def apply_patch(self, rel_path: str, new_content: str) -> None:
        """Applies updated content to a file in the sandbox."""
        self.write_file(rel_path, new_content)

    def revert_file(self, rel_path: str) -> None:
        """Reverts a sandboxed file to its original content from the source repository."""
        src = os.path.join(self.repo.root_path, rel_path)
        dst = os.path.join(self.sandbox_path, rel_path)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
        elif os.path.exists(dst):
            os.remove(dst)
        self.modified_files.discard(rel_path)

    def run_command(
        self,
        cmd: list[str],
        timeout: float = 10.0,
        env_vars: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess:
        """
        Executes a shell command inside the sandbox directory.
        Sets PYTHONPATH to include the sandbox directory so local modules resolve properly.
        """
        env = os.environ.copy()
        current_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{self.sandbox_path}{os.pathsep}{current_pythonpath}"
            if current_pythonpath
            else self.sandbox_path
        )
        if env_vars:
            env.update(env_vars)

        try:
            return subprocess.run(
                cmd,
                cwd=self.sandbox_path,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
        except subprocess.TimeoutExpired as e:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=-1,
                stdout=e.stdout or "",
                stderr=(e.stderr or "") + f"\nCommand timed out after {timeout} seconds.",
            )

    def get_diff(self, rel_path: str) -> str:
        """Computes unified diff between original repo file and sandboxed file."""
        orig_content = self.repo.read_file(rel_path)
        mod_content = self.read_file(rel_path)
        return create_unified_diff(orig_content, mod_content, filename=rel_path)

    def get_all_diffs(self) -> dict[str, str]:
        """Returns diffs for all modified files."""
        return {f: self.get_diff(f) for f in sorted(self.modified_files)}

    def sync_to_repo(self, rel_path: str) -> None:
        """Syncs an approved sandboxed file back to the original repository."""
        if rel_path not in self.modified_files:
            return
        content = self.read_file(rel_path)
        self.repo.write_file(rel_path, content)

    def sync_all_to_repo(self) -> list[str]:
        """Syncs all sandboxed modifications back to the original repository."""
        synced = []
        for rel_path in sorted(self.modified_files):
            self.sync_to_repo(rel_path)
            synced.append(rel_path)
        return synced

    def cleanup(self) -> None:
        """Removes the temporary sandbox directory."""
        if os.path.exists(self.sandbox_path):
            shutil.rmtree(self.sandbox_path, ignore_errors=True)

    def __enter__(self) -> "ExecutionSandbox":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.cleanup()
