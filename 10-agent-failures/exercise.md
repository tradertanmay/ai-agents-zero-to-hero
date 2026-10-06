# Exercise 10: Implement Client-Side Idempotency Keys and Write Deduplication

## Goal
Extend the Reddit Comment Agent with **Client-Side Idempotency Keys** to make write operations strictly idempotent at the protocol level, even in high-concurrency environments.

---

## The Challenge

1. **Add Idempotency Keys to Submission Interface**:
   Update `submit_comment` in `RedditClient` and `RedditToolRegistry` to accept an `idempotency_key: str`:
   ```python
   def submit_comment(self, post_id: str, body: str, idempotency_key: str) -> dict[str, Any]:
       # Format: f"idemp_{post_id}_{hashlib.sha256(body.encode()).hexdigest()[:12]}"
       pass
   ```

2. **Implement Server-Side Deduplication Cache in `MockRedditEnvironment`**:
   In `MockRedditEnvironment`, maintain a table or dictionary of processed idempotency keys:
   ```python
   class MockRedditEnvironment:
       def __init__(self):
           ...
           self.idempotency_records: dict[str, dict[str, Any]] = {}
   ```
   If a request arrives with an already-seen `idempotency_key`:
   - Return the previously generated `comment_id` with `status: "success"` and `cached: True`.
   - Do NOT append a duplicate comment to `self.posts[post_id].comments`.

3. **Wire Idempotency into `ResilientRedditAgent`**:
   Ensure `execute_resilient_comment` calculates the key deterministically from the approved draft before making network calls.

---

## Verification Check

Write a short verification test:
1. Dispatch two consecutive calls to `submit_comment()` with the exact same `idempotency_key`.
2. Verify that both calls return `status="success"` and the same `comment_id`.
3. Inspect `mock_env.get_comments(post_id)` and verify that the comment count only increased by **exactly 1**.
