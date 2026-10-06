"""
Rollback Governance and Restoration (Module 15)
Provides instant, verified rollback to previous stable agent versions upon production degradation.
Axiom: 'Self-improvement without versioning and rollback is mutation, not controlled evolution.'
"""

from typing import Any

from .versions import VersionInfo, VersionRegistry


class RollbackManager:
    """
    Manages production rollback procedures and safety verifications.
    """

    def __init__(self, registry: VersionRegistry) -> None:
        self.registry = registry

    def execute_rollback(self, target_version_id: str, reason: str) -> VersionInfo:
        """
        Executes a controlled rollback to a designated stable ancestor version.
        Guarantees that both the demoted version and the restored version are logged.
        """
        active = self.registry.get_active_version()
        if active.version_id == target_version_id:
            raise ValueError(f"Version '{target_version_id}' is already the active production version.")

        restored = self.registry.rollback_to(target_version_id, reason=reason)
        return restored

    def rollback_to_parent(self, reason: str) -> VersionInfo:
        """
        Convenience method to rollback the active version to its direct parent.
        """
        active = self.registry.get_active_version()
        if not active.parent_version:
            raise ValueError(f"Active version '{active.version_id}' has no recorded parent version.")

        return self.execute_rollback(active.parent_version, reason=reason)
