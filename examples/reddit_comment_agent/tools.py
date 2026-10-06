"""
Reddit Tool Registry & Permission-Gated Actions (Modules 03 & 08 Application)
Provides schema-validated tool calling for Reddit operations, with mandatory
cryptographic approval token verification on all write actions.
"""

from dataclasses import dataclass
import inspect
from typing import Any, Callable
from .reddit import RedditClient
from .state import RedditAgentState
from .approval import ApprovalGate


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., Any]
    requires_approval: bool = False


class RedditToolRegistry:
    """Manages Reddit tools and enforces permission boundaries."""

    def __init__(
        self,
        client: RedditClient,
        state: RedditAgentState,
        approval_gate: ApprovalGate,
    ) -> None:
        self.client = client
        self.state = state
        self.approval_gate = approval_gate
        self.tools: dict[str, ToolDefinition] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        self.register(
            name="read_posts",
            description="Lists recent posts from a specified subreddit.",
            parameters={
                "type": "object",
                "properties": {
                    "subreddit": {"type": "string", "description": "e.g. 'r/Python'"},
                    "limit": {"type": "integer", "description": "Max posts to fetch"},
                },
                "required": ["subreddit"],
            },
            func=self._tool_read_posts,
            requires_approval=False,
        )

        self.register(
            name="read_post",
            description="Retrieves full title, body text, and author of a specific post.",
            parameters={
                "type": "object",
                "properties": {
                    "post_id": {"type": "string", "description": "Unique post ID"},
                },
                "required": ["post_id"],
            },
            func=self._tool_read_post,
            requires_approval=False,
        )

        self.register(
            name="read_comments",
            description="Retrieves top comments for a given post.",
            parameters={
                "type": "object",
                "properties": {
                    "post_id": {"type": "string", "description": "Unique post ID"},
                    "limit": {"type": "integer", "description": "Max comments to fetch"},
                },
                "required": ["post_id"],
            },
            func=self._tool_read_comments,
            requires_approval=False,
        )

        self.register(
            name="read_rules",
            description="Retrieves official community guidelines and rules for a subreddit.",
            parameters={
                "type": "object",
                "properties": {
                    "subreddit": {"type": "string", "description": "Subreddit name"},
                },
                "required": ["subreddit"],
            },
            func=self._tool_read_rules,
            requires_approval=False,
        )

        self.register(
            name="draft_comment",
            description="Stages a proposed response in working memory without publishing.",
            parameters={
                "type": "object",
                "properties": {
                    "post_id": {"type": "string", "description": "Target post ID"},
                    "comment_text": {"type": "string", "description": "Draft markdown content"},
                },
                "required": ["post_id", "comment_text"],
            },
            func=self._tool_draft_comment,
            requires_approval=False,
        )

        self.register(
            name="submit_comment",
            description="Publishes a comment to Reddit. Strictly requires human approval token!",
            parameters={
                "type": "object",
                "properties": {
                    "post_id": {"type": "string", "description": "Target post ID"},
                    "comment_text": {"type": "string", "description": "Final comment markdown content"},
                    "approval_token": {"type": "string", "description": "HMAC token from ApprovalGate"},
                },
                "required": ["post_id", "comment_text", "approval_token"],
            },
            func=self._tool_submit_comment,
            requires_approval=True,
        )

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        func: Callable[..., Any],
        requires_approval: bool = False,
    ) -> None:
        self.tools[name] = ToolDefinition(name, description, parameters, func, requires_approval)

    def execute(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        tool = self.tools.get(name)
        if not tool:
            return {"status": "error", "error": f"Tool '{name}' is not registered."}

        try:
            return tool.func(**args)
        except Exception as e:
            return {"status": "error", "error": f"Tool execution failed: {type(e).__name__}: {str(e)}"}

    # ------------------------------------------------------------------------
    # Tool Implementations
    # ------------------------------------------------------------------------

    def _tool_read_posts(self, subreddit: str, limit: int = 5) -> dict[str, Any]:
        posts = self.client.list_posts(subreddit, limit=limit)
        return {"status": "success", "subreddit": subreddit, "count": len(posts), "posts": posts}

    def _tool_read_post(self, post_id: str) -> dict[str, Any]:
        post = self.client.get_post(post_id)
        if not post:
            return {"status": "error", "error": f"Post '{post_id}' not found."}
        self.state.mark_post_seen(post_id, post["subreddit"], post["title"], post["author"])
        return {"status": "success", "post": post}

    def _tool_read_comments(self, post_id: str, limit: int = 3) -> dict[str, Any]:
        comments = self.client.get_comments(post_id, limit=limit)
        return {"status": "success", "post_id": post_id, "count": len(comments), "comments": comments}

    def _tool_read_rules(self, subreddit: str) -> dict[str, Any]:
        rules = self.client.get_subreddit_rules(subreddit)
        return {"status": "success", "subreddit": subreddit, "rules": rules}

    def _tool_draft_comment(self, post_id: str, comment_text: str) -> dict[str, Any]:
        self.state.working.proposed_draft = comment_text
        return {"status": "success", "post_id": post_id, "staged": True}

    def _tool_submit_comment(self, post_id: str, comment_text: str, approval_token: str) -> dict[str, Any]:
        # Duplicate Prevention
        if self.state.has_commented(post_id):
            return {
                "status": "error",
                "error": f"DuplicateCommentError: Agent has already commented on post '{post_id}'.",
            }

        # Permission Gate Verification
        if not self.approval_gate.verify_token(post_id, comment_text, approval_token):
            return {
                "status": "error",
                "error": "PermissionDeniedError: submit_comment requires a valid approval token from ApprovalGate.",
            }

        # Dispatch write to Reddit client
        res = self.client.submit_comment(post_id, comment_text)
        if res.get("status") == "success":
            comment_id = res.get("comment_id", "c_unknown")
            self.state.record_submitted_comment(post_id, comment_id, comment_text)

        return res
