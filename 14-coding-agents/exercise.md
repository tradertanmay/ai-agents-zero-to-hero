# Exercise: Hardening Autonomous Coding Agents

## Objective
Extend the `examples/coding_assistant` subsystem to implement AST call-graph extraction, a security-hardened patch policy, and automated repair for an arithmetic expansion in `demo_repo`.

---

## Scenario
A team deployed an autonomous coding agent to resolve customer bug tickets. While attempting to resolve an issue, the agent hallucinated a fix that passed the local test suite by using `os.system("kill -9 ...")` to terminate a flaky daemon, and in another ticket, modified `tests/test_calculator.py` to delete failing assertion statements.

Your task is to harden the agent against test tampering and security violations while adding AST call-graph capabilities.

---

## Requirements

### 1. AST Call-Graph Extraction (`ast_tools.py`)
Extend `ast_tools.py` with `extract_function_calls(content: str, function_name: str) -> list[str]`:
- Use `ast.walk()` over the target function AST node.
- Identify all `ast.Call` nodes.
- Extract the names of invoked functions (e.g. `re.findall`, `float`, `int`).
- Return a sorted list of unique function/method call names.

### 2. Forbidden-Pattern Security Invariant (`verifier.py`)
Enhance `PatchSafetyLinter`:
- Add a set of forbidden call names and modules:
  `{"eval", "exec", "os.system", "subprocess.Popen", "shutil.rmtree", "__import__"}`
- When linting a Python patch, inspect its AST for calls matching forbidden symbols.
- If a forbidden call is detected, reject the patch immediately:
  `"Patch safety violation: Forbidden call detected: <symbol>"`

### 3. Modulo Operator & Negative Numbers in `demo_repo`
Add a new feature and repair workflow:
- In `demo_repo/tests/test_calculator.py`, add `test_modulo`:
  `self.assertEqual(calculate("%", 10, 3), 1.0)`
- In `demo_repo/tests/test_parser.py`, add support for `%`:
  `self.assertEqual(parse_tokens("10 % 3"), ["10", "%", "3"])`
- Update `CodingAgent.formulate_repair_hypothesis` to support the modulo operator `%` when detected in failing tests.
- Verify that the agent successfully repairs the modulo feature in the sandbox, passes both targeted tests and the full regression suite, and achieves a clean scorecard.

### 4. Patch Budget & Complexity Gate
- Add cyclomatic complexity or max line delta enforcement (e.g., maximum 30 modified lines per patch).
- Ensure that candidate patches modifying more lines than the budget are rejected and forced into smaller, targeted diffs.

---

## Verification Test Checklist

Write tests to verify the following cases:
1. [ ] Candidate patch attempting to import `os.system` or `eval` -> **REJECTED by Safety Linter**.
2. [ ] Candidate patch attempting to modify `tests/test_calculator.py` -> **BLOCKED by Safety Linter**.
3. [ ] `extract_function_calls` correctly extracts all calls inside `calculate()` -> **PASSED**.
4. [ ] Sandboxed repair loop resolves `test_modulo` without manual intervention -> **RESOLVED**.
5. [ ] Full regression test suite executes with 0 failures after repairs -> **PASSED**.
6. [ ] Working tree remains clean; no changes committed without explicit approval -> **VERIFIED**.
