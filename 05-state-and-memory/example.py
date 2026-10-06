"""
Module 05: State and Memory
Runnable Python Demonstration: Multi-Tiered Agent Memory and History Compaction

This script demonstrates the three core memory layers using standard Python 3.11+:
1. Working State (in-memory execution scratchpad)
2. Persistent Long-Term Memory (SQLite-backed entity store across sessions)
3. Conversation History Compaction (sliding-window summarization)
"""

from dataclasses import dataclass, field
from typing import Any, Callable
import sqlite3
import json
import time


# ============================================================================
# 1. Layer 1: Working State (Ephemeral Task Scratchpad)
# ============================================================================

@dataclass
class WorkingState:
    task_id: str
    user_id: str
    goal: str
    step: int = 0
    max_steps: int = 6
    is_finished: bool = False
    scratchpad: dict[str, Any] = field(default_factory=dict)
    final_answer: str | None = None


# ============================================================================
# 2. Layer 2: Conversation History & Automatic Compaction
# ============================================================================

@dataclass
class Message:
    role: str  # "user", "assistant", "tool", or "system"
    content: str
    tool_call: dict[str, Any] | None = None


class ConversationHistory:
    """
    Manages active turns with sliding-window compaction to prevent context window explosion.
    """
    def __init__(self, max_uncompacted_turns: int = 6) -> None:
        self.messages: list[Message] = []
        self.summary: str | None = None
        self.max_uncompacted_turns = max_uncompacted_turns

    def add_message(self, message: Message) -> None:
        self.messages.append(message)
        if len(self.messages) > self.max_uncompacted_turns:
            self.compact()

    def compact(self, keep_recent: int = 3) -> None:
        """
        Compacts older messages into a structured semantic summary,
        retaining the most recent N turns intact for conversational flow.
        """
        if len(self.messages) <= keep_recent:
            return

        to_compact = self.messages[:-keep_recent]
        recent = self.messages[-keep_recent:]

        # Extract semantic facts from turns being compacted
        facts = []
        for m in to_compact:
            if m.role == "user" and "prefer" in m.content.lower():
                facts.append(f"User stated: '{m.content}'")
            elif m.role == "tool":
                facts.append(f"Tool observation recorded: {m.content}")

        summary_text = "; ".join(facts) if facts else "Prior interaction context processed."
        if self.summary:
            self.summary = f"{self.summary} | {summary_text}"
        else:
            self.summary = summary_text

        # Reconstruct messages with updated summary at the top
        self.messages = [
            Message(role="system", content=f"Historical Summary: {self.summary}")
        ] + recent


# ============================================================================
# 3. Layer 3: Long-Term Persistent Memory (SQLite-Backed)
# ============================================================================

class PersistentMemoryStore:
    """
    SQLite-backed store that persists entity preferences and episodic session
    logs permanently across process restarts.
    """
    def __init__(self, db_path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self) -> None:
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS entity_memory (
                    user_id TEXT,
                    key TEXT,
                    value TEXT,
                    updated_at REAL,
                    PRIMARY KEY (user_id, key)
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS session_episodes (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    goal TEXT,
                    final_answer TEXT,
                    timestamp REAL
                )
            """)

    def set_preference(self, user_id: str, key: str, value: Any) -> None:
        with self.conn:
            self.conn.execute("""
                INSERT INTO entity_memory (user_id, key, value, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
            """, (user_id, key, json.dumps(value), time.time()))

    def get_preferences(self, user_id: str) -> dict[str, Any]:
        cursor = self.conn.execute(
            "SELECT key, value FROM entity_memory WHERE user_id = ?", (user_id,)
        )
        return {row[0]: json.loads(row[1]) for row in cursor.fetchall()}

    def record_episode(self, session_id: str, user_id: str, goal: str, answer: str) -> None:
        with self.conn:
            self.conn.execute("""
                INSERT INTO session_episodes (session_id, user_id, goal, final_answer, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, user_id, goal, answer, time.time()))

    def get_episodes(self, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
        cursor = self.conn.execute("""
            SELECT session_id, goal, final_answer FROM session_episodes
            WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?
        """, (user_id, limit))
        return [{"session_id": r[0], "goal": r[1], "answer": r[2]} for r in cursor.fetchall()]

    def close(self) -> None:
        self.conn.close()


# ============================================================================
# 4. Stateful Multi-Session Agent
# ============================================================================

class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, func: Callable[..., Any]) -> None:
        self._tools[func.__name__] = func

    def execute(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name not in self._tools:
            return {"status": "error", "error": f"Tool '{name}' not found."}
        try:
            return {"status": "success", "result": self._tools[name](**args)}
        except Exception as e:
            return {"status": "error", "error": str(e)}


class StatefulAgent:
    """
    Agent that accesses Working State for active tasks, Conversation History
    for dialog flow, and Long-Term Persistent Memory across independent sessions.
    """
    def __init__(self, memory_store: PersistentMemoryStore, registry: ToolRegistry) -> None:
        self.memory_store = memory_store
        self.registry = registry

    def run_session(self, session_id: str, user_id: str, goal: str) -> str:
        state = WorkingState(task_id=session_id, user_id=user_id, goal=goal)
        history = ConversationHistory(max_uncompacted_turns=4)

        # 1. Bootstrap State with Long-Term Memory
        known_prefs = self.memory_store.get_preferences(user_id)
        state.scratchpad["preferences"] = known_prefs
        currency = known_prefs.get("currency", "USD")

        history.add_message(Message(role="user", content=goal))

        # 2. Simulated Model Reasoning Loop
        # Check if user is setting a preference vs asking for a calculation
        if "prefer" in goal.lower() or "currency is" in goal.lower():
            # Preference declaration
            if "eur" in goal.lower():
                self.memory_store.set_preference(user_id, "currency", "EUR")
                state.final_answer = "Stored preference: Preferred currency set to EUR."
            elif "gbp" in goal.lower():
                self.memory_store.set_preference(user_id, "currency", "GBP")
                state.final_answer = "Stored preference: Preferred currency set to GBP."
            else:
                self.memory_store.set_preference(user_id, "currency", "USD")
                state.final_answer = "Stored preference: Preferred currency set to USD."
            
            state.is_finished = True
        else:
            # Multi-step task using remembered preferences
            state.step += 1
            # Step 1: Query price tool
            price_obs = self.registry.execute("get_item_price", {"item_id": "widget_a"})
            base_price = price_obs.get("result", 10.0)

            state.step += 1
            # Step 2: Multiply quantity (e.g. 5 units)
            total = base_price * 5.0

            # Step 3: Format with remembered currency
            symbol = "€" if currency == "EUR" else ("£" if currency == "GBP" else "$")
            state.final_answer = f"Total for 5 units of widget_a is {symbol}{total:.2f} ({currency})."
            state.is_finished = True

        # 3. Record episodic history in persistent memory
        self.memory_store.record_episode(session_id, user_id, goal, state.final_answer)

        return state.final_answer


# ============================================================================
# 5. Tools & Demonstration
# ============================================================================

def get_item_price(item_id: str) -> float:
    """Returns price of catalog item."""
    prices = {"widget_a": 12.50, "widget_b": 45.00}
    return prices.get(item_id, 10.0)


def main() -> None:
    print("=" * 65)
    print("DEMO: STATE, PERSISTENT MEMORY & COMPACTION")
    print("=" * 65)

    # Initialize Persistent Store & Tool Registry
    store = PersistentMemoryStore(db_path=":memory:")
    registry = ToolRegistry()
    registry.register(get_item_price)

    agent = StatefulAgent(memory_store=store, registry=registry)

    # ------------------------------------------------------------------------
    # Part 1: Session 1 — User establishes persistent preferences
    # ------------------------------------------------------------------------
    print("\n--- [SESSION 1] User Establishes Long-Term Preference ---")
    goal_1 = "My name is Alice and my preferred currency is EUR."
    print(f"User: '{goal_1}'")
    answer_1 = agent.run_session(session_id="sess_001", user_id="user_alice", goal=goal_1)
    print(f"Agent: {answer_1}")

    # Inspect persistent SQLite store
    stored = store.get_preferences("user_alice")
    print(f"SQLite Verified Stored Preferences: {stored}")

    # ------------------------------------------------------------------------
    # Part 2: Session 2 — New session recalls memory without being told again!
    # ------------------------------------------------------------------------
    print("\n--- [SESSION 2] New Session (Independent Memory Recall) ---")
    goal_2 = "Order 5 units of widget_a."
    print(f"User: '{goal_2}' (Notice: user does NOT re-state currency)")
    answer_2 = agent.run_session(session_id="sess_002", user_id="user_alice", goal=goal_2)
    print(f"Agent: {answer_2}")
    print("Result: The agent automatically priced the order in EUR using persistent memory!")

    # ------------------------------------------------------------------------
    # Part 3: Conversation History Compaction Demo
    # ------------------------------------------------------------------------
    print("\n--- [PART 3] Conversation History Compaction Demo ---")
    history = ConversationHistory(max_uncompacted_turns=4)

    print("Adding 6 conversation turns...")
    history.add_message(Message("user", "Hello! I am planning a project."))
    history.add_message(Message("assistant", "Glad to help! What is the budget?"))
    history.add_message(Message("user", "I prefer python over javascript."))
    history.add_message(Message("assistant", "Understood. Python it is."))
    history.add_message(Message("user", "Let us build an agent runtime."))
    history.add_message(Message("assistant", "Starting runtime scaffolding now."))

    print(f"Total messages after automatic compaction: {len(history.messages)}")
    for i, msg in enumerate(history.messages):
        print(f"  [{i+1}] ({msg.role.upper()}): {msg.content}")

    print("\nCompaction successfully condensed older messages into a summary while")
    print("preserving recent turns verbatim!")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
