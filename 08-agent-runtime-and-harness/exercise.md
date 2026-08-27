# Exercise 08: Human-in-the-Loop Middleware Interceptor

## Goal
Implement a **Human-in-the-Loop (HITL)** approval middleware inside the Agent Harness for destructive or high-risk tool operations.

---

## The Challenge

1. Extend `AgentHarness` to support tool approval callbacks:
   ```python
   ApprovalCallback = Callable[[str, dict[str, Any]], bool]
   ```
2. When a tool has `permission_level="admin"` or `requires_approval=True`, the harness must invoke the approval callback before executing the function.
3. If the callback returns `False`, inject an observation stating:
   `"ActionRejected: Human supervisor denied approval for tool '{tool_name}'."`
4. If `True`, proceed with execution as normal.

---

## Starter Template

```python
def mock_human_approver(tool_name: str, args: dict[str, Any]) -> bool:
    print(f" [SUPERVISOR REVIEW REQUIRED] Approve '{tool_name}' with {args}? (Y/N)")
    # For automated tests, reject deletions:
    if "delete" in tool_name:
        return False
    return True
```

---

## Verification Check
1. Register a tool `format_disk(drive_letter: str)` requiring approval.
2. Run an agent trajectory attempting to call `format_disk`.
3. Verify that the harness prompts the callback, rejects execution, records the rejection in `harness.trajectory`, and finishes safely without running the tool.
