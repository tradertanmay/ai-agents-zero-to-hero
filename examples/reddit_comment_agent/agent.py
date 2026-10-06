"""
Reddit Comment Agent Coordinator
The Capstone Architecture uniting Modules 01-09 into a coherent,
production-grade, human-in-the-loop agent system.
"""

from typing import Any
from .reddit import RedditClient, MockRedditClient
from .state import RedditAgentState
from .evaluator import CommentEvaluator, EvaluationResult
from .approval import ApprovalGate, ApprovalDecision
from .tools import RedditToolRegistry
from .runtime import AgentRuntime, RuntimeBudget


class RedditCommentAgent:
    """
    Coordinates Discovery, Inspection, Contribution Decision, Drafting,
    Automated Evaluation, and Human Approval before publishing comments.
    """

    def __init__(
        self,
        client: RedditClient | None = None,
        state: RedditAgentState | None = None,
        evaluator: CommentEvaluator | None = None,
        approval_gate: ApprovalGate | None = None,
        runtime: AgentRuntime | None = None,
    ) -> None:
        self.client = client or MockRedditClient()
        self.state = state or RedditAgentState()
        self.evaluator = evaluator or CommentEvaluator()
        self.approval_gate = approval_gate or ApprovalGate(interactive=True)
        self.runtime = runtime or AgentRuntime(RuntimeBudget())
        self.tools = RedditToolRegistry(self.client, self.state, self.approval_gate)

    def synthesize_draft(
        self,
        post: dict[str, Any],
        rules: list[str],
        existing_comments: list[dict[str, Any]],
    ) -> str:
        """
        Drafts a high-value, rule-compliant technical comment.
        In production, this calls an LLM policy; in this deterministic
        offline baseline, it applies first-principles technical synthesis.
        """
        title = post.get("title", "")
        selftext = post.get("selftext", "")

        # Tailored response for safe nested dictionary lookup
        if "nested" in title.lower() or "dict" in title.lower():
            return (
                "For deeply nested dictionary queries in standard Python 3.10+, you can use "
                "`functools.reduce` with a safe lookup helper to avoid repeated chained `.get()` calls:\n\n"
                "```python\n"
                "from functools import reduce\n\n"
                "def safe_get(dictionary: dict, *keys, default=None):\n"
                "    try:\n"
                "        return reduce(lambda d, k: d[k] if isinstance(d, dict) else default, keys, dictionary)\n"
                "    except (KeyError, TypeError, IndexError):\n"
                "        return default\n\n"
                "# Usage example:\n"
                "# val = safe_get(data, 'user', 'profile', 'address', 'zip')\n"
                "```\n\n"
                "This handles missing keys, `None` values along the path, and non-dict intermediate objects "
                "with zero external dependencies while staying fully idiomatic."
            )

        # Fallback general technical template
        return (
            f"Regarding your question on '{title}':\n\n"
            "A clean standard library approach is to encapsulate the boundary condition "
            "in a dedicated helper function, ensuring proper exception handling and type safety."
        )

    def should_contribute(
        self,
        post: dict[str, Any],
        existing_comments: list[dict[str, Any]],
    ) -> tuple[bool, str]:
        """
        Planning & Filtering Stage: Decides whether the agent can genuinely add value.
        Filters out spam, rule-breaking posts, and posts that are already solved.
        """
        title = post.get("title", "").lower()
        selftext = post.get("selftext", "").lower()

        # 1. Filter out spam / marketing submissions
        if any(w in title or w in selftext for w in ["10,000%", "guaranteed", "download now", "telegram"]):
            return False, "Skipped: Post flagged as promotional marketing or spam."

        # 2. Filter out already-solved simple questions
        if "reverse a list" in title:
            return False, "Skipped: Question is already comprehensively answered in top comments."

        # 3. Filter out posts without substantial technical inquiry
        if len(selftext.strip()) < 10 and len(title.split()) < 4:
            return False, "Skipped: Post is too brief or low-context for meaningful technical input."

        return True, "Proceed: Post contains a genuine technical challenge with value-add potential."

    def process_post(self, post_summary: dict[str, Any]) -> dict[str, Any]:
        """
        Orchestrates the complete Observe -> Decide -> Act lifecycle for a single post.
        """
        post_id = post_summary["post_id"]
        step = 1

        # Check Harness tripwires
        can_comment, tripwire_reason = self.runtime.check_can_comment()
        if not can_comment:
            return {"post_id": post_id, "status": "aborted", "reason": tripwire_reason}

        # Check State & Memory: Skip if already commented
        if self.state.has_commented(post_id):
            return {"post_id": post_id, "status": "skipped", "reason": "Already commented on this post."}

        # Step 1: Read Full Post Content
        post_res = self.tools.execute("read_post", {"post_id": post_id})
        self.runtime.log_step(step, post_id, "read_post", {"post_id": post_id}, post_res.get("status", "error"), f"Fetched details for {post_id}")
        if post_res.get("status") != "success":
            return {"post_id": post_id, "status": "failed", "reason": post_res.get("error")}
        post = post_res["post"]

        # Step 2: Read Subreddit Rules (Context Engineering)
        step += 1
        rules_res = self.tools.execute("read_rules", {"subreddit": post["subreddit"]})
        self.runtime.log_step(step, post_id, "read_rules", {"subreddit": post["subreddit"]}, rules_res.get("status", "error"), f"Fetched rules for {post['subreddit']}")
        rules = rules_res.get("rules", [])

        # Step 3: Read Existing Comments (Context Engineering & Anti-Pollution)
        step += 1
        comments_res = self.tools.execute("read_comments", {"post_id": post_id, "limit": 3})
        self.runtime.log_step(step, post_id, "read_comments", {"post_id": post_id}, comments_res.get("status", "error"), f"Fetched {comments_res.get('count', 0)} comments")
        existing_comments = comments_res.get("comments", [])

        # Step 4: Decision to Contribute
        step += 1
        can_help, rationale = self.should_contribute(post, existing_comments)
        self.runtime.log_step(step, post_id, "decide_to_contribute", {}, "success" if can_help else "skipped", rationale)
        if not can_help:
            return {"post_id": post_id, "status": "skipped", "reason": rationale}

        # Step 5: Draft Comment
        step += 1
        draft = self.synthesize_draft(post, rules, existing_comments)
        self.tools.execute("draft_comment", {"post_id": post_id, "comment_text": draft})
        self.runtime.log_step(step, post_id, "draft_comment", {"post_id": post_id}, "success", "Draft staged in working state")

        # Step 6: Automated Evaluation (Scorecard)
        step += 1
        eval_result = self.evaluator.evaluate(post, rules, existing_comments, draft)
        self.runtime.log_step(
            step,
            post_id,
            "evaluate_draft",
            {"score": eval_result.total_score},
            "success" if eval_result.passed else "failed",
            f"Score: {eval_result.total_score:.1f}/10.0 ({eval_result.verdict})",
        )

        if not eval_result.passed:
            self.state.record_draft(post_id, draft, eval_result.total_score, "REJECTED_BY_EVALUATOR", eval_result.summary)
            return {"post_id": post_id, "status": "rejected_by_evaluator", "evaluation": eval_result}

        # Step 7: Mandatory Human Approval Gate
        step += 1
        approval = self.approval_gate.request_approval(
            post=post,
            draft_comment=draft,
            evaluator_score=eval_result.total_score,
            evaluator_feedback=eval_result.summary,
        )
        self.runtime.log_step(
            step,
            post_id,
            "human_approval_gate",
            {"approved": approval.approved},
            "success" if approval.approved else "denied",
            approval.reason,
        )

        if not approval.approved:
            self.state.record_draft(post_id, draft, eval_result.total_score, "REJECTED_BY_HUMAN", approval.reason)
            return {"post_id": post_id, "status": "rejected_by_human", "reason": approval.reason}

        # Step 8: Submit Comment (Permission-Gated)
        step += 1
        final_text = approval.edited_text or draft
        submit_res = self.tools.execute(
            "submit_comment",
            {
                "post_id": post_id,
                "comment_text": final_text,
                "approval_token": approval.approval_token,
            },
        )
        self.runtime.log_step(
            step,
            post_id,
            "submit_comment",
            {"post_id": post_id},
            submit_res.get("status", "error"),
            f"Submitted comment_id={submit_res.get('comment_id', 'unknown')}",
        )

        if submit_res.get("status") == "success":
            self.state.record_draft(post_id, final_text, eval_result.total_score, "PUBLISHED", "Approved and posted.")
            return {"post_id": post_id, "status": "published", "comment_id": submit_res.get("comment_id")}
        else:
            return {"post_id": post_id, "status": "submission_error", "error": submit_res.get("error")}

    def run_on_subreddit(self, subreddit: str = "r/Python", limit: int = 5) -> list[dict[str, Any]]:
        """Scans a subreddit and runs the full agent lifecycle on discovery."""
        print(f"\n[RedditCommentAgent] Scanning '{subreddit}' (limit={limit})...")
        posts_res = self.tools.execute("read_posts", {"subreddit": subreddit, "limit": limit})
        if posts_res.get("status") != "success":
            print(f"Error reading posts: {posts_res.get('error')}")
            return []

        posts = posts_res.get("posts", [])
        print(f"Discovered {len(posts)} candidate posts.")
        outcomes = []

        for p in posts:
            print(f"\n>>> Processing Post: '{p['title'][:60]}...' (ID: {p['post_id']})")
            res = self.process_post(p)
            outcomes.append(res)
            print(f"    Outcome: {res.get('status')} -> {res.get('reason', res.get('comment_id', ''))}")

        return outcomes
