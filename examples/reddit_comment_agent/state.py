"""
Reddit Agent State & Memory (Module 05 Application)
Provides short-term working state and long-term SQLite persistent memory
to prevent duplicate comments and maintain historical audit logs.
"""

from dataclasses import dataclass, field
import sqlite3
import time
from typing import Any


@dataclass
class WorkingMemory:
    """Ephemeral scratchpad for the active post being processed."""
    active_post_id: str | None = None
    active_post_title: str | None = None
    active_subreddit: str | None = None
    active_selftext: str | None = None
    active_rules: list[str] = field(default_factory=list)
    existing_comments: list[dict[str, Any]] = field(default_factory=list)
    proposed_draft: str | None = None
    evaluator_feedback: str | None = None
    evaluator_score: float = 0.0
    approval_token: str | None = None
    step_count: int = 0

    def reset(self) -> None:
        self.active_post_id = None
        self.active_post_title = None
        self.active_subreddit = None
        self.active_selftext = None
        self.active_rules.clear()
        self.existing_comments.clear()
        self.proposed_draft = None
        self.evaluator_feedback = None
        self.evaluator_score = 0.0
        self.approval_token = None
        self.step_count = 0


class RedditAgentState:
    """
    Persistent state manager backed by SQLite.
    Prevents duplicate comments across multiple script executions.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.working = WorkingMemory()
        self._init_db()

    def _init_db(self) -> None:
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS seen_posts (
                    post_id TEXT PRIMARY KEY,
                    subreddit TEXT,
                    title TEXT,
                    author TEXT,
                    seen_at REAL
                );
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS commented_posts (
                    post_id TEXT PRIMARY KEY,
                    comment_id TEXT,
                    comment_text TEXT,
                    submitted_at REAL
                );
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS draft_history (
                    draft_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id TEXT,
                    draft_text TEXT,
                    evaluator_score REAL,
                    approval_status TEXT,
                    reason TEXT,
                    created_at REAL
                );
            """)

    def is_post_seen(self, post_id: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM seen_posts WHERE post_id = ?", (post_id,))
        return cursor.fetchone() is not None

    def mark_post_seen(self, post_id: str, subreddit: str, title: str, author: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO seen_posts (post_id, subreddit, title, author, seen_at) VALUES (?, ?, ?, ?, ?)",
                (post_id, subreddit, title, author, time.time()),
            )

    def has_commented(self, post_id: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM commented_posts WHERE post_id = ?", (post_id,))
        return cursor.fetchone() is not None

    def record_submitted_comment(self, post_id: str, comment_id: str, comment_text: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO commented_posts (post_id, comment_id, comment_text, submitted_at) VALUES (?, ?, ?, ?)",
                (post_id, comment_id, comment_text, time.time()),
            )

    def record_draft(
        self,
        post_id: str,
        draft_text: str,
        score: float,
        status: str,
        reason: str,
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO draft_history (post_id, draft_text, evaluator_score, approval_status, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (post_id, draft_text, score, status, reason, time.time()),
            )

    def get_commented_count(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM commented_posts")
        row = cursor.fetchone()
        return row[0] if row else 0

    def get_seen_count(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM seen_posts")
        row = cursor.fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        self.conn.close()
