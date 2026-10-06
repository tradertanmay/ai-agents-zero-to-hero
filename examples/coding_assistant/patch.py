"""
Patch Generation and Validation (Module 14)
Provides unified diff generation, targeted replacements, and syntax validation.
"""

import ast
import difflib


def create_unified_diff(original: str, modified: str, filename: str = "file") -> str:
    """
    Generates standard Git-style unified diff comparing original to modified.
    """
    orig_lines = original.splitlines(keepends=True)
    mod_lines = modified.splitlines(keepends=True)

    diff = difflib.unified_diff(
        orig_lines,
        mod_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
    )
    return "".join(diff)


def apply_targeted_replacement(original: str, target: str, replacement: str) -> str:
    """
    Replaces an exact chunk of code within the original text.
    Ensures targeted edit is unambiguous (occurs exactly once).
    Raises ValueError if target is missing or ambiguous.
    """
    occurrences = original.count(target)
    if occurrences == 0:
        raise ValueError("Target content not found in original text.")
    if occurrences > 1:
        raise ValueError(
            f"Target content found {occurrences} times in original text; replacement is ambiguous."
        )

    return original.replace(target, replacement, 1)


def validate_patch_syntax(filename: str, new_content: str) -> tuple[bool, str | None]:
    """
    Validates Python syntax before applying a patch or writing to disk.
    Returns (True, None) if syntax is valid, or (False, error_message) on syntax error.
    """
    if not filename.endswith(".py"):
        return True, None

    try:
        ast.parse(new_content, filename=filename)
        return True, None
    except SyntaxError as e:
        return False, f"SyntaxError in {filename}:{e.lineno}: {e.msg}"
