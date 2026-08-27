# Module 14: Coding Agents

**Difficulty Level:** Level 5 — Research 
**Status:** Coming Soon

---

## What You Will Learn

1. Why software engineering agents (like Claude Code, SWE-bench solvers, and GitHub Copilot Workspace) are the most advanced real-world agent systems.
2. The core Coding Agent loop:
   $$\text{Repository Search} \to \text{File Reading} \to \text{Reasoning} \to \text{Code Editing} \to \text{Test Execution} \to \text{Test Failure Observation} \to \text{Refined Edit}$$
3. Repo navigation tools: Grep, file tree search, AST parsing, and symbol indexing.
4. Patch generation: Unified diffs vs. full file rewrites vs. targeted line replacements.
5. Automated test execution, error capture, and iterative debugging harnesses.

---

## Core Questions This Module Answers

- *Why do diff-based code edits often fail with LLMs, and how do modern harnesses fix this?*
- *How does an agent navigate a 1,000,000-line codebase without blowing its context window?*
- *How do automated SWE-bench benchmarks evaluate an agent's ability to resolve real GitHub issues?*

---

## Planned Example

`14-coding-agents/example.py` will demonstrate:
- A complete miniature Coding Agent equipped with `read_file`, `search_files`, `edit_file`, and `run_pytest` tools.
- Solving a real buggy Python module: locating the bug, reproducing it with a test, fixing the code, and validating that the test suite passes.

---

## Prerequisites

- Completed [04-build-your-first-agent](../04-build-your-first-agent/README.md) and [08-agent-runtime-and-harness](../08-agent-runtime-and-harness/README.md).
