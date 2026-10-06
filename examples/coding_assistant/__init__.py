"""
Coding Assistant Package (Module 14)
Provides repository exploration, AST navigation, sandboxed test execution,
patch generation, and test-driven repair loops.
"""

from .repo import Repository
from .search import search_code, find_symbol_definition
from .ast_tools import parse_file_ast, extract_symbols, extract_function_source
from .patch import create_unified_diff, apply_targeted_replacement, validate_patch_syntax
from .sandbox import ExecutionSandbox
from .verifier import TestVerifier, PatchSafetyLinter, TestRunResult
from .agent import CodingAgent, CodingAgentScorecard

__all__ = [
    "Repository",
    "search_code",
    "find_symbol_definition",
    "parse_file_ast",
    "extract_symbols",
    "extract_function_source",
    "create_unified_diff",
    "apply_targeted_replacement",
    "validate_patch_syntax",
    "ExecutionSandbox",
    "TestVerifier",
    "PatchSafetyLinter",
    "TestRunResult",
    "CodingAgent",
    "CodingAgentScorecard",
]
