"""
Code Navigation & Search (Module 14)
Provides fast text, regex grep, and symbol definition lookups across repository files.
"""

import fnmatch
import os
import re
from typing import Any

from .repo import Repository


def search_code(
    repo: Repository,
    query: str,
    is_regex: bool = False,
    file_pattern: str | None = None,
) -> list[dict[str, Any]]:
    """
    Searches file contents across the repository for matching query text or regex patterns.
    Returns list of matches: [{"file": rel_path, "line_number": n, "line_text": line}].
    """
    matches = []
    pattern = re.compile(query if is_regex else re.escape(query), re.IGNORECASE)

    for rel_path in repo.list_files():
        if file_pattern and not fnmatch.fnmatch(os.path.basename(rel_path), file_pattern):
            continue

        abs_path = os.path.join(repo.root_path, rel_path)
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                for line_no, line in enumerate(f, start=1):
                    if pattern.search(line):
                        matches.append({
                            "file": rel_path,
                            "line_number": line_no,
                            "line_text": line.rstrip("\r\n"),
                        })
        except (IOError, UnicodeDecodeError):
            continue

    return matches


def find_symbol_definition(repo: Repository, symbol_name: str) -> list[dict[str, Any]]:
    """
    Finds definition sites of functions or classes matching symbol_name.
    """
    regex = rf"^\s*(def|class)\s+{re.escape(symbol_name)}\b"
    return search_code(repo, regex, is_regex=True, file_pattern="*.py")
