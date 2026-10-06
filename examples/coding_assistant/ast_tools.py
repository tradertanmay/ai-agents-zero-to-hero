"""
AST Navigation & Inspection Tools (Module 14)
Provides Python syntax tree parsing, symbol extraction, and function source slicing.
"""

import ast
from typing import Any


def parse_file_ast(content: str) -> ast.AST:
    """Parses Python source code string into an Abstract Syntax Tree."""
    return ast.parse(content)


def extract_symbols(content: str) -> list[dict[str, Any]]:
    """
    Extracts all top-level and method definitions (functions, classes) from source.
    Returns list of dicts with: name, type, start_line, end_line, docstring, args.
    """
    tree = parse_file_ast(content)
    symbols: list[dict[str, Any]] = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node) or ""
            args = [arg.arg for arg in node.args.args]
            symbols.append({
                "name": node.name,
                "type": "function",
                "start_line": node.lineno,
                "end_line": getattr(node, "end_lineno", node.lineno),
                "docstring": doc.strip(),
                "args": args,
            })
        elif isinstance(node, ast.ClassDef):
            class_doc = ast.get_docstring(node) or ""
            methods = []
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    m_doc = ast.get_docstring(child) or ""
                    m_args = [arg.arg for arg in child.args.args]
                    methods.append({
                        "name": child.name,
                        "type": "method",
                        "start_line": child.lineno,
                        "end_line": getattr(child, "end_lineno", child.lineno),
                        "docstring": m_doc.strip(),
                        "args": m_args,
                    })
            symbols.append({
                "name": node.name,
                "type": "class",
                "start_line": node.lineno,
                "end_line": getattr(node, "end_lineno", node.lineno),
                "docstring": class_doc.strip(),
                "methods": methods,
            })

    return symbols


def extract_function_source(content: str, function_name: str) -> str | None:
    """
    Finds a function definition by name and extracts its exact source lines.
    Enables targeted context building without loading entire files into model context.
    """
    tree = parse_file_ast(content)
    lines = content.splitlines(keepends=True)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            start = node.lineno - 1
            end = getattr(node, "end_lineno", len(lines))
            return "".join(lines[start:end])

    return None
