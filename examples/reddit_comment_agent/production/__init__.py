"""
Production Agent Subsystem (Module 13)
Provides durable execution, state machine transitions, distributed worker leases,
crash recovery, telemetry, and health check endpoints.
"""

from .config import AgentConfig, redact_secrets
from .jobs import JobStatus, JobStage, JobRecord, InvalidStateTransitionError
from .checkpoints import DurableJobQueue
from .telemetry import StructuredLogger, MetricsRegistry, Tracer, Span
from .health import HealthCheckHandler, HealthServer
from .recovery import RecoveryManager
from .worker import AgentWorker

__all__ = [
    "AgentConfig",
    "redact_secrets",
    "JobStatus",
    "JobStage",
    "JobRecord",
    "InvalidStateTransitionError",
    "DurableJobQueue",
    "StructuredLogger",
    "MetricsRegistry",
    "Tracer",
    "Span",
    "HealthCheckHandler",
    "HealthServer",
    "RecoveryManager",
    "AgentWorker",
]
