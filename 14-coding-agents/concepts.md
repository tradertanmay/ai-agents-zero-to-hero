# Module 14: Coding Agents (Concepts)

A coding agent is an autonomous agent whose environment is a software repository, whose actions mutate source code, and whose verifier is the test and build system.

Generic chat assistants produce code snippets in isolation without knowing whether they compile, pass tests, or break downstream dependencies. A true coding agent operates directly within a repository lifecycle: discovering files, navigating syntax trees, generating unified patches, testing modifications in sandboxes, and verifying zero regressions.

---

## 1. The Coding Agent Loop

The lifecycle of an autonomous software engineering agent follows an observe-hypothesize-edit-verify feedback loop:

```
+-------------------------------------------------------------------------+
|                        CODING AGENT ARCHITECTURE                        |
+-------------------------------------------------------------------------+
                                     |
               [1] Inspect Repository & Map Directory Tree
                                     |
                                     v
               [2] Run Baseline Test Suite (Isolated Sandbox)
                                     |
                       +-------------+-------------+
                       |                           |
                 (All Pass)                  (Failures Found)
                       |                           |
                       v                           v
                [Done / Clean]            [3] Localize Failure
                                           - Parse traceback
                                           - Identify test & symbol
                                                   |
                                                   v
                                          [4] Build AST Context
                                           - Grep / symbol lookup
                                           - Slice targeted function
                                                   |
                                                   v
                                          [5] Formulate Hypothesis
                                           - Targeted replacement
                                                   |
                                                   v
                                          [6] Invariant Safety Linter
                                           - Forbid editing tests
                                           - Enforce line budget
                                           - Validate syntax
                                                   |
                                                   v
                                          [7] Sandboxed Test Execution
                                           - Run targeted test
                                           - Run full regression suite
                                                   |
                             +---------------------+---------------------+
                             |                                           |
                       (Tests Pass)                                (Tests Fail)
                             |                                           |
                             v                                           v
                 [8] Review Unified Diff                         [Retry / Revise]
                             |                                   (within budget)
                             v
                 [9] Human Approval Gate
                             |
                             v
                 [10] Sync to Real Repository
```

---

## 2. Environment: The Software Repository

Unlike conversational agents whose environment consists of text chat threads, a coding agent perceives and acts upon a structured filesystem:

### Repository Inspection
- **Directory Traversal**: Recursively scans source files while pruning non-essential directories (`.git`, `__pycache__`, `venv`, `.tox`, `build`).
- **Language & Metric Profiling**: Computes file sizes, line counts, and detects programming languages via extension mappings.
- **Entrypoint & Test Detection**: Discovers candidate test suites (`test_*.py`, `*_test.py`, `tests/`) and application entrypoints (`main.py`, `app.py`, `cli.py`).

### Context Engineering via AST Slicing
Dumping entire source files into an LLM context window wastes tokens, degrades attention, and increases hallucination risks. 

Instead, context is engineered using the Python Abstract Syntax Tree (`ast` module):
1. Locate definition line (`node.lineno`) and completion line (`node.end_lineno`).
2. Extract only the target function or class definition.
3. Provide the model with exact line numbers and symbol signatures.

```
File: calculator.py (Total: 400 lines)
                     |
       [AST FunctionDef: calculate]
                     |
                     v
Extracted Context Slice: lines 6 to 22 (17 lines)
-> 95.75% reduction in prompt token consumption!
```

---

## 3. Patch Generation and Representation

Coding agents mutate code using structured patches rather than overwriting full files.

### Targeted Replacements
Edits are specified as targeted string or AST replacements:
- Must match target content uniquely (`count == 1`). If the target snippet occurs multiple times, replacement is rejected as ambiguous.
- Minimizes accidental regressions in unrelated functions.

### Unified Diffs
All modifications are tracked as standard Git-compatible unified diffs (`difflib.unified_diff`):

```diff
--- a/calculator.py
+++ b/calculator.py
@@ -18,3 +18,3 @@
     elif op == "^":
-        return float(int(a) ^ int(b))
+        return float(a ** b)
     else:
```

Unified diffs provide:
- Compact representation for logging and telemetry.
- Clear, readable changes for human-in-the-loop review.
- Direct calculation of patch statistics (lines added, lines removed).

---

## 4. Execution Sandbox & Isolation Invariants

A coding agent must **never** execute unverified edits directly in the user's working tree.

### The ExecutionSandbox Architecture
1. **Isolated Tempdir**: Clones repository source files into a temporary directory (`tempfile.mkdtemp`).
2. **Environment Isolation**: Configures `PYTHONPATH` to point to the sandbox so local module imports resolve to sandboxed files.
3. **Rollback Guarantee**: Any candidate edit that fails tests or causes regressions is reverted instantly (`sandbox.revert_file()`).
4. **Approval Gate**: Sandboxed files are only synced back to the real codebase (`sandbox.sync_all_to_repo()`) after passing all verification stages and receiving explicit human confirmation.

---

## 5. Invariant Safety Linter

A critical danger with autonomous coding agents is **test evasion**: modifying or deleting unit test assertions so that broken code appears to pass.

The `PatchSafetyLinter` enforces four invariants:

| Invariant | Rule | Rationale |
| :--- | :--- | :--- |
| **1. Test Immutability** | Modifying files in `tests/` or matching `test_*.py` is strictly forbidden. | The agent must fix the production code to satisfy specifications, never weaken tests. |
| **2. Non-Empty Mutation** | `modified_content != original_content` | Prevents infinite no-op loops. |
| **3. Diff Budget** | `abs(lines_changed) <= max_lines_changed` (default: 50 lines) | Prevents runaway refactorings, scope creep, and context degradation. |
| **4. Syntactic Validity** | `ast.parse(modified_content)` must succeed with zero SyntaxErrors. | Catches indentation, unclosed delimiters, and syntax mistakes before running tests. |

---

## 6. The Verification Triad

A coding agent verifies its work through three progressive gates:

1. **Syntax Gate**: Abstract syntax tree validation (`ast.parse`) ensures code compiles.
2. **Targeted Test Gate**: Runs the specific test that originally failed to establish immediate proof of fix.
3. **Full Regression Gate**: Runs the entire test suite across the repository to verify that the patch did not introduce unintended side effects.

---

## 7. The Coding Agent Scorecard

Every repair session records verifiable metrics:

```
============================================================
CODING AGENT SCORECARD: RESOLVED
============================================================
Initial Failures:         2
Final Failures:           0
Target Tests Passed:      True
Regressions Clean:        True
Files Modified:           calculator.py, parser.py
Lines Added / Removed:    +3 / -2
Iterations Consumed:      2
Syntax Errors Caught:     0
Safety Violations Blocked:0
Human Approval Granted:   True
============================================================
```

This telemetry enables quantitative evaluation across large benchmarks (such as SWE-bench): measuring resolve rate, token efficiency, iteration count, and safety compliance.
