"""
Mock GitHub API Environment (Applied Agent Systems: A2)
Provides an in-memory, deterministic simulation of GitHub repository interactions:
- Issues and Pull Requests state tracking
- Comments, labels, and workflow status
- Idempotency key support for write operations
- Crash/fault injection hook for recovery verification
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class GitHubComment:
    comment_id: int
    author: str
    body: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class GitHubIssue:
    number: int
    title: str
    body: str
    author: str
    state: str = "open"  # 'open' or 'closed'
    labels: list[str] = field(default_factory=list)
    comments: list[GitHubComment] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    closed_at: str | None = None


@dataclass
class GitHubPR:
    number: int
    title: str
    body: str
    author: str
    state: str = "open"  # 'open', 'merged', 'closed'
    labels: list[str] = field(default_factory=list)
    comments: list[GitHubComment] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    merged: bool = False
    merged_at: str | None = None


class MockGitHubAPI:
    """
    Stateful GitHub API simulator.
    Supports idempotency keys to ensure at-most-once delivery across agent restarts.
    """

    def __init__(self, repo_name: str = "acme/awesome-agent"):
        self.repo_name = repo_name
        self.is_archived: bool = False
        self.issues: dict[int, GitHubIssue] = {}
        self.pull_requests: dict[int, GitHubPR] = {}
        self.workflow_runs: list[dict[str, Any]] = [
            {"id": 101, "name": "CI Tests", "status": "completed", "conclusion": "success"}
        ]
        self._next_comment_id = 1
        self._next_issue_number = 1
        self._next_pr_number = 100

        # Idempotency cache: maps idempotency_key -> result dict
        self._idempotency_records: dict[str, dict[str, Any]] = {}

        # Fault injection
        self.crash_on_next_write: bool = False
        self.crash_error_message: str = "Simulated Network/Process Crash During GitHub Write"

    def get_repo_info(self) -> dict[str, Any]:
        """Fetch general repository status."""
        return {
            "full_name": self.repo_name,
            "is_archived": self.is_archived,
            "open_issues_count": len([i for i in self.issues.values() if i.state == "open"]),
            "open_pr_count": len([p for p in self.pull_requests.values() if p.state == "open"]),
            "workflow_runs": list(self.workflow_runs),
        }

    def create_issue(
        self,
        title: str,
        body: str,
        author: str = "contributor",
        labels: list[str] | None = None,
    ) -> GitHubIssue:
        issue_num = self._next_issue_number
        self._next_issue_number += 1
        issue = GitHubIssue(
            number=issue_num,
            title=title,
            body=body,
            author=author,
            labels=labels or [],
        )
        self.issues[issue_num] = issue
        return issue

    def create_pull_request(
        self,
        title: str,
        body: str,
        author: str = "contributor",
        labels: list[str] | None = None,
    ) -> GitHubPR:
        pr_num = self._next_pr_number
        self._next_pr_number += 1
        pr = GitHubPR(
            number=pr_num,
            title=title,
            body=body,
            author=author,
            labels=labels or [],
        )
        self.pull_requests[pr_num] = pr
        return pr

    def list_issues(self, state: str = "open") -> list[dict[str, Any]]:
        """List repository issues by state."""
        return [
            {
                "number": i.number,
                "title": i.title,
                "body": i.body,
                "author": i.author,
                "state": i.state,
                "labels": list(i.labels),
                "comments_count": len(i.comments),
                "created_at": i.created_at,
            }
            for i in self.issues.values()
            if state == "all" or i.state == state
        ]

    def list_pull_requests(self, state: str = "open") -> list[dict[str, Any]]:
        """List repository pull requests by state."""
        return [
            {
                "number": p.number,
                "title": p.title,
                "body": p.body,
                "author": p.author,
                "state": p.state,
                "labels": list(p.labels),
                "comments_count": len(p.comments),
                "created_at": p.created_at,
                "merged": p.merged,
            }
            for p in self.pull_requests.values()
            if state == "all" or p.state == state
        ]

    def post_issue_comment(
        self,
        issue_number: int,
        body: str,
        author: str = "agent[bot]",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Post a comment to an issue with idempotency protection."""
        if idempotency_key and idempotency_key in self._idempotency_records:
            return self._idempotency_records[idempotency_key]

        if self.crash_on_next_write:
            self.crash_on_next_write = False
            raise RuntimeError(self.crash_error_message)

        if issue_number not in self.issues and issue_number not in self.pull_requests:
            raise ValueError(f"Issue or Pull Request #{issue_number} not found.")

        comment = GitHubComment(
            comment_id=self._next_comment_id,
            author=author,
            body=body,
        )
        self._next_comment_id += 1
        target = self.issues.get(issue_number) or self.pull_requests.get(issue_number)
        target.comments.append(comment)

        result = {
            "status": "success",
            "comment_id": comment.comment_id,
            "issue_number": issue_number,
            "body": comment.body,
            "created_at": comment.created_at,
        }
        if idempotency_key:
            self._idempotency_records[idempotency_key] = result
        return result

    def close_issue(
        self,
        issue_number: int,
        reason: str = "completed",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Close an issue with idempotency protection."""
        if idempotency_key and idempotency_key in self._idempotency_records:
            return self._idempotency_records[idempotency_key]

        if self.crash_on_next_write:
            self.crash_on_next_write = False
            raise RuntimeError(self.crash_error_message)

        if issue_number not in self.issues:
            raise ValueError(f"Issue #{issue_number} not found.")

        issue = self.issues[issue_number]
        issue.state = "closed"
        issue.closed_at = datetime.now(timezone.utc).isoformat()

        result = {
            "status": "success",
            "issue_number": issue_number,
            "state": "closed",
            "reason": reason,
        }
        if idempotency_key:
            self._idempotency_records[idempotency_key] = result
        return result

    def add_label(
        self,
        issue_number: int,
        label: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Add a label to an issue or pull request with idempotency protection."""
        if idempotency_key and idempotency_key in self._idempotency_records:
            return self._idempotency_records[idempotency_key]

        if self.crash_on_next_write:
            self.crash_on_next_write = False
            raise RuntimeError(self.crash_error_message)

        if issue_number not in self.issues and issue_number not in self.pull_requests:
            raise ValueError(f"Issue or Pull Request #{issue_number} not found.")

        target = self.issues.get(issue_number) or self.pull_requests.get(issue_number)
        if label not in target.labels:
            target.labels.append(label)

        result = {
            "status": "success",
            "issue_number": issue_number,
            "labels": list(target.labels),
        }
        if idempotency_key:
            self._idempotency_records[idempotency_key] = result
        return result

    def merge_pull_request(
        self,
        pr_number: int,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Merge a pull request with idempotency protection."""
        if idempotency_key and idempotency_key in self._idempotency_records:
            return self._idempotency_records[idempotency_key]

        if self.crash_on_next_write:
            self.crash_on_next_write = False
            raise RuntimeError(self.crash_error_message)

        if pr_number not in self.pull_requests:
            raise ValueError(f"Pull request #{pr_number} not found.")

        pr = self.pull_requests[pr_number]
        pr.state = "merged"
        pr.merged = True
        pr.merged_at = datetime.now(timezone.utc).isoformat()

        result = {
            "status": "success",
            "pr_number": pr_number,
            "state": "merged",
            "merged": True,
        }
        if idempotency_key:
            self._idempotency_records[idempotency_key] = result
        return result

    def has_idempotency_record(self, key: str) -> bool:
        """Check if an action with this key has already executed."""
        return key in self._idempotency_records
