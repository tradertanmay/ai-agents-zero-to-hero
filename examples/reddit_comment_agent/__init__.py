"""
Reddit Comment Agent Capstone
A production-grade, human-in-the-loop agent demonstrating Modules 01-09.
"""

from .agent import RedditCommentAgent
from .reddit import RedditClient, MockRedditClient
from .state import RedditAgentState
from .evaluator import CommentEvaluator, EvaluationResult
from .approval import ApprovalGate, ApprovalDecision
from .runtime import AgentRuntime, RuntimeBudget

__all__ = [
    "RedditCommentAgent",
    "RedditClient",
    "MockRedditClient",
    "RedditAgentState",
    "CommentEvaluator",
    "EvaluationResult",
    "ApprovalGate",
    "ApprovalDecision",
    "AgentRuntime",
    "RuntimeBudget",
]
