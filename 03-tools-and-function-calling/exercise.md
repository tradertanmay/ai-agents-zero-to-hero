# Exercise 03: Build a Sandboxed Tool with Schema Validation

## Goal
Implement a custom tool function, register it with the `ToolRegistry`, and verify that type validation and error handling work as expected.

---

## The Challenge

Create a tool called `fetch_user_profile(user_id: int, include_emails: bool = False)` that:
1. Validates that `user_id` is a positive integer.
2. Returns mock profile data:
   - If `user_id == 1`: `{"name": "Alice", "role": "admin", "email": "alice@corp.com"}`
   - If `user_id == 2`: `{"name": "Bob", "role": "member", "email": "bob@corp.com"}`
   - If `user_id` not found: Raises a `KeyError(f"User ID {user_id} not found")`.
3. If `include_emails` is `False`, strips the `email` key from the return dictionary.

---

## Starter Template

```python
from typing import Any

def fetch_user_profile(user_id: int, include_emails: bool = False) -> dict[str, Any]:
    """
    Fetch a user's profile information by numeric user_id.
    """
    # Write your implementation here
    pass
```

---

## Verification Steps
1. Register `fetch_user_profile` in `ToolRegistry`.
2. Verify that `registry.get_schemas()` includes both `user_id` and `include_emails` with appropriate JSON types (`number` and `boolean`).
3. Call `registry.execute("fetch_user_profile", {"user_id": 1, "include_emails": True})` and verify the output contains the email.
4. Call `registry.execute("fetch_user_profile", {"user_id": 999})` and verify the runtime catches the error cleanly without crashing.
