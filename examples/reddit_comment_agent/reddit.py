"""
Reddit Client Interfaces
Provides a unified abstract interface for Reddit access with an offline
Mock implementation (default) and an optional real PRAW adapter.
"""

from abc import ABC, abstractmethod
from typing import Any
from .mock_reddit import MockRedditEnvironment


class RedditClient(ABC):
    """Abstract interface for Reddit operations."""

    @abstractmethod
    def get_subreddit_rules(self, subreddit: str) -> list[str]:
        """Fetches the official posting and commenting rules for a subreddit."""
        pass

    @abstractmethod
    def list_posts(self, subreddit: str, limit: int = 5) -> list[dict[str, Any]]:
        """Lists recent or top posts from a subreddit."""
        pass

    @abstractmethod
    def get_post(self, post_id: str) -> dict[str, Any] | None:
        """Retrieves full post title, body text, author, and metadata."""
        pass

    @abstractmethod
    def get_comments(self, post_id: str, limit: int = 3) -> list[dict[str, Any]]:
        """Retrieves top comments for a given post."""
        pass

    @abstractmethod
    def submit_comment(self, post_id: str, body: str) -> dict[str, Any]:
        """Publishes a new comment to a specified post."""
        pass


class MockRedditClient(RedditClient):
    """Offline deterministic Reddit client powered by MockRedditEnvironment."""

    def __init__(self, env: MockRedditEnvironment | None = None) -> None:
        self.env = env or MockRedditEnvironment()

    def get_subreddit_rules(self, subreddit: str) -> list[str]:
        return self.env.get_rules(subreddit)

    def list_posts(self, subreddit: str, limit: int = 5) -> list[dict[str, Any]]:
        return self.env.list_posts(subreddit, limit=limit)

    def get_post(self, post_id: str) -> dict[str, Any] | None:
        return self.env.get_post(post_id)

    def get_comments(self, post_id: str, limit: int = 3) -> list[dict[str, Any]]:
        return self.env.get_comments(post_id, limit=limit)

    def submit_comment(self, post_id: str, body: str) -> dict[str, Any]:
        return self.env.submit_comment(post_id, body)


class PRAWRedditClient(RedditClient):
    """
    Optional production adapter using the official PRAW (Python Reddit API Wrapper) library.
    Requires third-party 'praw' package and Reddit API developer credentials.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        username: str,
        password: str,
    ) -> None:
        try:
            import praw  # type: ignore
        except ImportError as e:
            raise ImportError(
                "PRAW is not installed. To use real Reddit integration, install 'praw' via:\n"
                "  pip install praw\n"
                "Or continue using MockRedditClient for 100% offline learning."
            ) from e

        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            username=username,
            password=password,
        )

    def get_subreddit_rules(self, subreddit: str) -> list[str]:
        sub = self.reddit.subreddit(subreddit.replace("r/", ""))
        return [r.short_name for r in sub.rules]

    def list_posts(self, subreddit: str, limit: int = 5) -> list[dict[str, Any]]:
        sub = self.reddit.subreddit(subreddit.replace("r/", ""))
        posts = []
        for p in sub.hot(limit=limit):
            posts.append({
                "post_id": p.id,
                "subreddit": f"r/{sub.display_name}",
                "author": str(p.author),
                "title": p.title,
                "upvotes": p.score,
                "num_comments": p.num_comments,
                "created_utc": p.created_utc,
            })
        return posts

    def get_post(self, post_id: str) -> dict[str, Any] | None:
        subm = self.reddit.submission(id=post_id)
        return {
            "post_id": subm.id,
            "subreddit": f"r/{subm.subreddit.display_name}",
            "author": str(subm.author),
            "title": subm.title,
            "selftext": subm.selftext,
            "upvotes": subm.score,
            "num_comments": subm.num_comments,
            "created_utc": subm.created_utc,
        }

    def get_comments(self, post_id: str, limit: int = 3) -> list[dict[str, Any]]:
        subm = self.reddit.submission(id=post_id)
        subm.comments.replace_more(limit=0)
        comments = []
        for c in subm.comments[:limit]:
            comments.append({
                "comment_id": c.id,
                "post_id": post_id,
                "author": str(c.author),
                "body": c.body,
                "upvotes": c.score,
                "created_utc": c.created_utc,
            })
        return comments

    def submit_comment(self, post_id: str, body: str) -> dict[str, Any]:
        subm = self.reddit.submission(id=post_id)
        comment = subm.reply(body)
        return {
            "comment_id": comment.id,
            "post_id": post_id,
            "body": body,
            "status": "success",
        }
