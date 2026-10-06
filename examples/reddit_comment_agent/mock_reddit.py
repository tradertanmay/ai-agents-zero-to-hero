"""
Mock Reddit Environment (Offline Simulator)
Provides realistic Reddit data structures, subreddits, rules, and threads
without requiring Reddit API credentials or network access.
"""

from dataclasses import dataclass, field
import time
from typing import Any


@dataclass
class MockComment:
    comment_id: str
    post_id: str
    author: str
    body: str
    upvotes: int
    created_utc: float = field(default_factory=time.time)


@dataclass
class MockPost:
    post_id: str
    subreddit: str
    author: str
    title: str
    selftext: str
    upvotes: int
    comments: list[MockComment] = field(default_factory=list)
    created_utc: float = field(default_factory=time.time)


class MockRedditEnvironment:
    """In-memory realistic simulator for Reddit subreddits and threads."""

    def __init__(self) -> None:
        self.rules: dict[str, list[str]] = {
            "r/Python": [
                "Rule 1: All code snippets must be properly formatted in code blocks.",
                "Rule 2: No spam, self-promotion, or unsolicited marketing links.",
                "Rule 3: Answers must be polite, constructive, and explain the rationale.",
                "Rule 4: Do not post low-effort or generic boilerplate responses.",
            ],
            "r/MachineLearning": [
                "Rule 1: Submissions must focus on research, theory, or production ML systems.",
                "Rule 2: Beginner questions must be directed to the weekly Megathread.",
                "Rule 3: Claims must cite academic papers or open-source benchmarks.",
            ],
        }

        self.posts: dict[str, MockPost] = {
            "post_py_101": MockPost(
                post_id="post_py_101",
                subreddit="r/Python",
                author="u/python_builder",
                title="What is the cleanest standard library way to safely query nested dicts?",
                selftext=(
                    "I frequently parse API payloads with shapes like data['user']['profile']['address']['zip']. "
                    "Sometimes an intermediate key is missing or set to None, raising KeyError or TypeError. "
                    "Writing 5 nested .get() calls gets ugly fast. "
                    "Is there a clean, zero-dependency pattern in Python 3.10+ standard library to handle this?"
                ),
                upvotes=58,
                comments=[
                    MockComment(
                        comment_id="c_201",
                        post_id="post_py_101",
                        author="u/syntax_fan",
                        body="You could write a recursive function or try/except block.",
                        upvotes=4,
                    )
                ],
            ),
            "post_py_102": MockPost(
                post_id="post_py_102",
                subreddit="r/Python",
                author="u/crypto_moon_dev",
                title="GUARANTEED 10,000% APY Crypto Arbitrage Bot in Python! DOWNLOAD NOW!",
                selftext="DM me on telegram to get the source code. Limited slots available!",
                upvotes=0,
                comments=[],
            ),
            "post_py_103": MockPost(
                post_id="post_py_103",
                subreddit="r/Python",
                author="u/fresh_coder",
                title="How to reverse a list in Python?",
                selftext="I have a list `[1, 2, 3]` and want `[3, 2, 1]`. What is the syntax?",
                upvotes=12,
                comments=[
                    MockComment(
                        comment_id="c_301",
                        post_id="post_py_103",
                        author="u/python_pro",
                        body="Use `my_list.reverse()` for in-place reversal, or `my_list[::-1]` / `list(reversed(my_list))` for a new list.",
                        upvotes=45,
                    ),
                    MockComment(
                        comment_id="c_302",
                        post_id="post_py_103",
                        author="u/clean_code_guru",
                        body="`my_list[::-1]` is the most idiomatic slicing syntax for copies.",
                        upvotes=22,
                    ),
                ],
            ),
        }

        self.submitted_comments: list[dict[str, Any]] = []

    def get_rules(self, subreddit: str) -> list[str]:
        return self.rules.get(subreddit, ["Be respectful and follow standard community guidelines."])

    def list_posts(self, subreddit: str, limit: int = 5) -> list[dict[str, Any]]:
        matching = [
            {
                "post_id": p.post_id,
                "subreddit": p.subreddit,
                "author": p.author,
                "title": p.title,
                "upvotes": p.upvotes,
                "num_comments": len(p.comments),
                "created_utc": p.created_utc,
            }
            for p in self.posts.values()
            if p.subreddit.lower() == subreddit.lower()
        ]
        return matching[:limit]

    def get_post(self, post_id: str) -> dict[str, Any] | None:
        p = self.posts.get(post_id)
        if not p:
            return None
        return {
            "post_id": p.post_id,
            "subreddit": p.subreddit,
            "author": p.author,
            "title": p.title,
            "selftext": p.selftext,
            "upvotes": p.upvotes,
            "num_comments": len(p.comments),
            "created_utc": p.created_utc,
        }

    def get_comments(self, post_id: str, limit: int = 3) -> list[dict[str, Any]]:
        p = self.posts.get(post_id)
        if not p:
            return []
        sorted_comments = sorted(p.comments, key=lambda c: c.upvotes, reverse=True)
        return [
            {
                "comment_id": c.comment_id,
                "post_id": c.post_id,
                "author": c.author,
                "body": c.body,
                "upvotes": c.upvotes,
                "created_utc": c.created_utc,
            }
            for c in sorted_comments[:limit]
        ]

    def submit_comment(self, post_id: str, body: str) -> dict[str, Any]:
        if post_id not in self.posts:
            return {"status": "error", "error": f"Post '{post_id}' not found."}

        new_id = f"c_gen_{len(self.submitted_comments) + 1}"
        comment = MockComment(
            comment_id=new_id,
            post_id=post_id,
            author="u/HeroAgentBot",
            body=body,
            upvotes=1,
        )
        self.posts[post_id].comments.append(comment)

        record = {
            "comment_id": new_id,
            "post_id": post_id,
            "body": body,
            "status": "success",
            "timestamp": time.time(),
        }
        self.submitted_comments.append(record)
        return record
