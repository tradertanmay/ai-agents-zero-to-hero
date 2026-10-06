"""
Version Registry and Audit Trail (Module 15)
Tracks immutable agent version lineages, promotion statuses, and audit histories.
Guarantees: 'Self-improvement without versioning and rollback is mutation, not controlled evolution.'
"""

from dataclasses import dataclass, field
import time
from typing import Any


@dataclass
class VersionInfo:
    """Represents a discrete, versioned release or candidate of an agent system."""

    version_id: str
    parent_version: str | None
    surface: str
    change_summary: str
    created_at: float = field(default_factory=time.time)
    eval_results: dict[str, Any] = field(default_factory=dict)
    promotion_status: str = "candidate"  # "candidate", "promoted", "rejected", "rolled_back"
    approved_by: str | None = None
    promoted_at: float | None = None
    snapshot_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serializes version metadata."""
        return {
            "version_id": self.version_id,
            "parent_version": self.parent_version,
            "surface": self.surface,
            "change_summary": self.change_summary,
            "created_at": self.created_at,
            "eval_results": self.eval_results,
            "promotion_status": self.promotion_status,
            "approved_by": self.approved_by,
            "promoted_at": self.promoted_at,
            "snapshot_path": self.snapshot_path,
        }


class VersionRegistry:
    """
    Manages active production versions, candidate releases, and complete audit history.
    Enforces immutable history: versions cannot be overwritten, only transitioned or rolled back.
    """

    def __init__(self, initial_version: VersionInfo | None = None) -> None:
        self.versions: dict[str, VersionInfo] = {}
        self.audit_trail: list[dict[str, Any]] = []
        self.active_version_id: str = ""

        if initial_version:
            initial_version.promotion_status = "promoted"
            initial_version.promoted_at = time.time()
            initial_version.approved_by = "system_init"
            self.register_version(initial_version)
            self.active_version_id = initial_version.version_id
            self._log_audit("INITIALIZE_PRODUCTION", initial_version.version_id, "Baseline v1.0 initialized.")

    def _log_audit(self, action: str, version_id: str, detail: str) -> None:
        """Records an immutable audit event."""
        entry = {
            "timestamp": time.time(),
            "action": action,
            "version_id": version_id,
            "detail": detail,
            "active_version": self.active_version_id,
        }
        self.audit_trail.append(entry)

    def register_version(self, version: VersionInfo) -> None:
        """Registers a new candidate or baseline version."""
        if version.version_id in self.versions:
            raise ValueError(f"Version '{version.version_id}' is already registered and cannot be overwritten.")
        self.versions[version.version_id] = version
        self._log_audit("REGISTER_VERSION", version.version_id, f"Registered on surface '{version.surface}'")

    def get_version(self, version_id: str) -> VersionInfo | None:
        """Retrieves metadata for a specific version."""
        return self.versions.get(version_id)

    def get_active_version(self) -> VersionInfo:
        """Returns the current production active version."""
        if not self.active_version_id or self.active_version_id not in self.versions:
            raise RuntimeError("No active production version is configured in registry.")
        return self.versions[self.active_version_id]

    def promote_version(self, version_id: str, approved_by: str) -> VersionInfo:
        """
        Promotes an eligible candidate version to active production status.
        Requires explicit approver identification.
        """
        version = self.versions.get(version_id)
        if not version:
            raise KeyError(f"Version '{version_id}' does not exist.")
        if version.promotion_status not in ("candidate", "eligible"):
            raise ValueError(f"Cannot promote version with status '{version.promotion_status}'.")

        version.promotion_status = "promoted"
        version.approved_by = approved_by
        version.promoted_at = time.time()
        self.active_version_id = version.version_id

        self._log_audit("PROMOTE_VERSION", version_id, f"Promoted to active production by {approved_by}.")
        return version

    def reject_version(self, version_id: str, reason: str) -> VersionInfo:
        """Marks a candidate version as rejected."""
        version = self.versions.get(version_id)
        if not version:
            raise KeyError(f"Version '{version_id}' does not exist.")

        version.promotion_status = "rejected"
        self._log_audit("REJECT_VERSION", version_id, f"Rejected: {reason}")
        return version

    def rollback_to(self, target_version_id: str, reason: str) -> VersionInfo:
        """
        Reverts active production version to an earlier promoted ancestor version.
        Retains both the demoted version and target version in audit history.
        """
        target = self.versions.get(target_version_id)
        if not target:
            raise KeyError(f"Rollback target version '{target_version_id}' does not exist.")
        if target.promotion_status not in ("promoted", "rolled_back"):
            raise ValueError(f"Cannot rollback to unpromoted version '{target_version_id}'.")

        prior_active = self.active_version_id
        if prior_active in self.versions:
            self.versions[prior_active].promotion_status = "rolled_back"

        self.active_version_id = target_version_id
        self._log_audit(
            "ROLLBACK",
            target_version_id,
            f"Rolled back from '{prior_active}' to '{target_version_id}'. Reason: {reason}",
        )
        return target

    def list_versions(self) -> list[VersionInfo]:
        """Lists all registered versions in chronological order."""
        return sorted(self.versions.values(), key=lambda v: v.created_at)

    def get_audit_trail(self) -> list[dict[str, Any]]:
        """Returns the full immutable audit trail."""
        return list(self.audit_trail)
