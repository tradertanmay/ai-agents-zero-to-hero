"""
Adaptation Surfaces and Safety Invariants (Module 15)
Defines the five adaptation surfaces, their blast radius hierarchy, and protected verifier boundaries.
"""

from dataclasses import dataclass
from enum import Enum
import os


class AdaptationSurface(str, Enum):
    """
    Five discrete surfaces of agent self-adaptation ordered by risk and blast radius.
    """

    MEMORY = "memory"          # Change retrieved examples / dynamic memory (Lowest Risk)
    PROMPT = "prompt"          # Change instructions and guidelines (Moderate Risk)
    TOOL = "tool"              # Change tool schemas and descriptions (Higher Risk)
    HARNESS = "harness"        # Change control logic, retries, and policies (Higher Risk)
    CODE = "code"              # Change executable code behavior (Highest Risk)


SURFACE_RISK_HIERARCHY = {
    AdaptationSurface.MEMORY: {
        "level": 1,
        "risk": "Low",
        "description": "Updates few-shot examples or memory retrieval weights without modifying prompts or logic.",
    },
    AdaptationSurface.PROMPT: {
        "level": 2,
        "risk": "Moderate",
        "description": "Refines prompt instructions, constraints, or guidelines.",
    },
    AdaptationSurface.TOOL: {
        "level": 3,
        "risk": "Higher",
        "description": "Clarifies tool descriptions, input schemas, or invocation boundaries.",
    },
    AdaptationSurface.HARNESS: {
        "level": 4,
        "risk": "Higher",
        "description": "Modifies execution control flow, retry policies, reconciliation, or rate limits.",
    },
    AdaptationSurface.CODE: {
        "level": 5,
        "risk": "Highest",
        "description": "Mutates underlying executable source code files directly.",
    },
}


# Governed Invariant: The subject of evaluation must NOT control the evaluator.
PROTECTED_FILES = {
    "approval.py",
    "safety.py",
    "verifier.py",
    "evaluator.py",
    "promotion.py",
    "rollback.py",
    "versions.py",
    "cases.json",
    "regression_cases.json",
    "holdout_cases.json",
}


def is_file_protected(file_path: str) -> bool:
    """
    Checks if a target file is in the protected evaluation and governance boundary.
    Any attempt by a candidate agent to mutate a protected file is rejected immediately.
    """
    base = os.path.basename(file_path).lower()
    return base in PROTECTED_FILES or "evals" in file_path.lower()


@dataclass
class MutationProposal:
    """Represents a structured proposal for candidate self-adaptation."""

    surface: AdaptationSurface
    target_file: str
    target_component: str
    description: str
    target_snippet: str
    replacement_snippet: str
    rationale: str

    def summary(self) -> str:
        """Returns a formatted ASCII summary of the mutation proposal."""
        risk_info = SURFACE_RISK_HIERARCHY[self.surface]
        lines = [
            f"MUTATION PROPOSAL [{self.surface.value.upper()} - Risk: {risk_info['risk']}]",
            f"  Target File:      {self.target_file}",
            f"  Component:        {self.target_component}",
            f"  Description:      {self.description}",
            f"  Rationale:        {self.rationale}",
        ]
        return "\n".join(lines)
