"""
Repository Discovery and Inspection (Module 14)
Provides filesystem tree mapping, language detection, file reading, and test discovery.
"""

import os
from pathlib import Path
from typing import Any


IGNORE_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "venv",
    ".venv",
    "dist",
    "build",
    ".egg-info",
}

LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".md": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".sh": "bash",
    ".txt": "text",
}


class Repository:
    """Manages reading, listing, and writing files within a target software repository."""

    def __init__(self, root_path: str) -> None:
        self.root_path = os.path.realpath(os.path.abspath(root_path))
        if not os.path.isdir(self.root_path):
            raise FileNotFoundError(f"Repository directory does not exist: {self.root_path}")

    def list_files(self, subpath: str = "") -> list[str]:
        """Returns relative paths of all non-ignored files in the repository."""
        target_dir = os.path.join(self.root_path, subpath)
        results = []
        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
            for f in sorted(files):
                if f.startswith("."):
                    continue
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, self.root_path)
                results.append(rel_path)
        return sorted(results)

    def get_file_tree(self) -> str:
        """Returns an ASCII directory tree representation of the codebase."""
        lines = [os.path.basename(self.root_path) + "/"]
        files = self.list_files()

        # Group by directory structure
        for f in files:
            parts = Path(f).parts
            indent = "  " * len(parts)
            lines.append(f"{indent}|-- {parts[-1]}")
        return "\n".join(lines)

    def read_file(self, rel_path: str, start_line: int | None = None, end_line: int | None = None) -> str:
        """Reads full file or a specific line slice (1-indexed, inclusive)."""
        abs_path = os.path.join(self.root_path, rel_path)
        if not os.path.isfile(abs_path):
            raise FileNotFoundError(f"File '{rel_path}' does not exist in repository.")

        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        if start_line is not None or end_line is not None:
            s = (start_line - 1) if start_line and start_line > 0 else 0
            e = end_line if end_line and end_line <= len(lines) else len(lines)
            selected_lines = lines[s:e]
            # Return with line number prefixes for context readability
            numbered = []
            for i, line in enumerate(selected_lines, start=s + 1):
                numbered.append(f"{i:>4} | {line}")
            return "".join(numbered)

        return "".join(lines)

    def write_file(self, rel_path: str, content: str) -> None:
        """Writes content to a file, creating parent directories if needed."""
        abs_path = os.path.join(self.root_path, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)

    def get_file_info(self, rel_path: str) -> dict[str, Any]:
        """Returns metadata: language, line count, and byte size."""
        abs_path = os.path.join(self.root_path, rel_path)
        if not os.path.isfile(abs_path):
            raise FileNotFoundError(f"File '{rel_path}' not found.")

        ext = os.path.splitext(rel_path)[1].lower()
        size_bytes = os.path.getsize(abs_path)
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            line_count = sum(1 for _ in f)

        return {
            "path": rel_path,
            "language": LANGUAGE_EXTENSIONS.get(ext, "unknown"),
            "line_count": line_count,
            "size_bytes": size_bytes,
        }

    def detect_entrypoints_and_tests(self) -> dict[str, list[str]]:
        """Identifies test files and entrypoint candidates."""
        all_files = self.list_files()
        test_files = [f for f in all_files if f.startswith("test") or "/test" in f or f.endswith("_test.py")]
        entrypoints = [f for f in all_files if f in ("main.py", "app.py", "cli.py", "__main__.py")]
        return {
            "test_files": test_files,
            "entrypoints": entrypoints,
            "source_files": [f for f in all_files if f not in test_files and f.endswith(".py")],
        }
