"""
Comment Evaluator (Module 04 & 09 Application)
Automated 5-criterion quality scorecard that evaluates drafts BEFORE
they reach the human approval gate, preventing low-quality spam or rule breaches.
"""

from dataclasses import dataclass, field
import re
from typing import Any


@dataclass
class EvaluationCriterion:
    name: str
    score: float  # 0.0 to 2.0
    max_score: float = 2.0
    passed: bool = True
    feedback: str = ""


@dataclass
class EvaluationResult:
    post_id: str
    total_score: float  # 0.0 to 10.0
    passed: bool
    verdict: str  # "APPROVED_FOR_REVIEW" or "REJECTED"
    criteria: list[EvaluationCriterion] = field(default_factory=list)
    summary: str = ""


class CommentEvaluator:
    """Evaluates proposed comments against quality, safety, and community guidelines."""

    PASSING_THRESHOLD = 7.0

    def evaluate(
        self,
        post: dict[str, Any],
        rules: list[str],
        existing_comments: list[dict[str, Any]],
        draft_comment: str,
    ) -> EvaluationResult:
        criteria: list[EvaluationCriterion] = []
        post_title = post.get("title", "")
        post_body = post.get("selftext", "")
        combined_post = (post_title + " " + post_body).lower()
        draft_lower = draft_comment.lower()

        # 1. Relevance: Checks if draft addresses key technical terms from post
        relevance_score = 2.0
        relevance_feedback = "Draft directly addresses core technical inquiry."
        # If post asks about dict/nested and draft mentions neither, penalize
        if "nested" in combined_post or "dict" in combined_post:
            if not any(k in draft_lower for k in ["dict", "nested", "get", "key", "json"]):
                relevance_score = 0.5
                relevance_feedback = "Draft lacks core terminology requested in the post."
        criteria.append(EvaluationCriterion("relevance", relevance_score, 2.0, relevance_score >= 1.5, relevance_feedback))

        # 2. Rule Compliance: Check for markdown code formatting and absence of spam
        rule_score = 2.0
        rule_feedback = "Complies with subreddit rules and guidelines."
        
        # Check spam / marketing patterns
        spam_pattern = re.compile(r"(guaranteed|download now|telegram|dm me|100% free|crypto|buy now)", re.IGNORECASE)
        if spam_pattern.search(draft_comment):
            rule_score = 0.0
            rule_feedback = "VIOLATION: Promotional, spam, or high-risk marketing phrases detected."
        elif "```" not in draft_comment and "def " in draft_comment:
            # Contains code but not in code blocks
            rule_score = 1.0
            rule_feedback = "WARNING: Code snippet is not properly enclosed in markdown code fences."
        criteria.append(EvaluationCriterion("rule_compliance", rule_score, 2.0, rule_score >= 1.5, rule_feedback))

        # 3. Value-Add: Ensure comment is not an exact duplicate of existing comments
        value_score = 2.0
        value_feedback = "Provides novel, complementary technical insight."
        for c in existing_comments:
            body = c.get("body", "").lower()
            if len(body) > 20 and body[:40] in draft_lower:
                value_score = 0.5
                value_feedback = "Draft substantially duplicates an existing comment."
                break
        criteria.append(EvaluationCriterion("value_add", value_score, 2.0, value_score >= 1.5, value_feedback))

        # 4. Tone and Clarity: Constructive, polite, and explanatory
        tone_score = 2.0
        tone_feedback = "Tone is respectful, constructive, and concise."
        if len(draft_comment.strip()) < 30:
            tone_score = 0.5
            tone_feedback = "Draft is too terse/low-effort to provide substantial value."
        elif len(draft_comment.splitlines()) > 50:
            tone_score = 1.0
            tone_feedback = "Draft is overly verbose and may overwhelm reader."
        criteria.append(EvaluationCriterion("tone_and_clarity", tone_score, 2.0, tone_score >= 1.5, tone_feedback))

        # 5. Accuracy & Actionability: Contains concrete example or rationale
        acc_score = 2.0
        acc_feedback = "Contains concrete code pattern or actionable guidance."
        if "```python" in draft_comment or "```" in draft_comment or "example:" in draft_lower:
            acc_score = 2.0
        else:
            acc_score = 1.5
            acc_feedback = "Actionable explanation provided without explicit code block."
        criteria.append(EvaluationCriterion("accuracy_actionability", acc_score, 2.0, acc_score >= 1.5, acc_feedback))

        total_score = sum(c.score for c in criteria)
        passed = total_score >= self.PASSING_THRESHOLD and all(c.score > 0 for c in criteria)
        verdict = "APPROVED_FOR_REVIEW" if passed else "REJECTED"

        summary_lines = [f"{c.name}: {c.score:.1f}/{c.max_score:.1f} ({c.feedback})" for c in criteria]
        summary = f"Score: {total_score:.1f}/10.0 | Verdict: {verdict}\n" + "\n".join(f"  - {line}" for line in summary_lines)

        return EvaluationResult(
            post_id=post.get("post_id", "unknown"),
            total_score=total_score,
            passed=passed,
            verdict=verdict,
            criteria=criteria,
            summary=summary,
        )
