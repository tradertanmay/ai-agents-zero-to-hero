# Exercise 05: Implement Memory Expiration (TTL) and User Deletion

## Goal
Extend the `PersistentMemoryStore` in Module 05 by implementing **Time-To-Live (TTL)** expiration and **GDPR user deletion** (`forget_user`) to prevent stale memory and comply with data privacy requirements.

---

## The Challenge

1. **Add Expiration to SQLite Schema**:
   Update `entity_memory` in `PersistentMemoryStore._init_db()` to store an `expires_at` timestamp:
   ```sql
   CREATE TABLE IF NOT EXISTS entity_memory (
       user_id TEXT,
       key TEXT,
       value TEXT,
       updated_at REAL,
       expires_at REAL,
       PRIMARY KEY (user_id, key)
   );
   ```

2. **Implement TTL in `set_preference`**:
   Add an optional `ttl_seconds: float | None = None` parameter:
   ```python
   def set_preference(self, user_id: str, key: str, value: Any, ttl_seconds: float | None = None) -> None:
       expires_at = time.time() + ttl_seconds if ttl_seconds is not None else None
       # INSERT or REPLACE into entity_memory
   ```

3. **Filter Expired Records in `get_preferences`**:
   Ensure `get_preferences` only returns rows where `expires_at IS NULL OR expires_at > ?` (current timestamp).

4. **Implement User Deletion (`forget_user`)**:
   Add a method that wipes all entity memories and session episodes for a given `user_id`:
   ```python
   def forget_user(self, user_id: str) -> None:
       """Deletes all persistent records associated with user_id."""
       with self.conn:
           self.conn.execute("DELETE FROM entity_memory WHERE user_id = ?", (user_id,))
           self.conn.execute("DELETE FROM session_episodes WHERE user_id = ?", (user_id,))
   ```

---

## Verification Check

Write a short verification test:
1. Store a preference with `ttl_seconds=0.1`.
2. Sleep for `0.2` seconds.
3. Call `get_preferences()` and verify the key is no longer returned!
4. Store another preference, call `forget_user()`, and verify the database is clean.
