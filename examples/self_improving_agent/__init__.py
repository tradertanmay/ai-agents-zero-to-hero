"""
Self-Improving Agent Subsystem (Module 15)
Provides versioned self-improvement, isolated candidate evaluation,
safety-gated promotion, and rollback governance.
"""

from .versions import VersionInfo, VersionRegistry
from .mutation import AdaptationSurface, PROTECTED_FILES, MutationProposal
from .proposer import ImprovementProposer
from .candidate import CandidateWorkspace
from .evaluator import FrozenBenchmarkEvaluator, EvaluationMetrics
from .promotion import PromotionGate, PromotionVerdict
from .rollback import RollbackManager
from .baseline import BaselineCodingAgent, CandidateCodingAgent

__all__ = [
    "VersionInfo",
    "VersionRegistry",
    "AdaptationSurface",
    "PROTECTED_FILES",
    "MutationProposal",
    "ImprovementProposer",
    "CandidateWorkspace",
    "FrozenBenchmarkEvaluator",
    "EvaluationMetrics",
    "PromotionGate",
    "PromotionVerdict",
    "RollbackManager",
    "BaselineCodingAgent",
    "CandidateCodingAgent",
]
