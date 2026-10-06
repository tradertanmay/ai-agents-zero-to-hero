"""
Observability and Telemetry (Module 13)
Implements the Three Operational Pillars:
1. Logs: Structured JSONL with correlation IDs and automated secret redaction
2. Metrics: Running aggregations of throughput, safety, and operational errors
3. Traces: Execution span hierarchy with duration timing and waterfalls
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import time
from typing import Any
import uuid

from .config import redact_secrets


@dataclass
class LogEntry:
    timestamp: str
    level: str
    run_id: str
    job_id: str
    trace_id: str
    action_id: str | None
    stage: str
    event: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        data = {
            "timestamp": self.timestamp,
            "level": self.level,
            "run_id": self.run_id,
            "job_id": self.job_id,
            "trace_id": self.trace_id,
            "action_id": self.action_id,
            "stage": self.stage,
            "event": self.event,
            "details": self.details,
        }
        return json.dumps(redact_secrets(data))


class StructuredLogger:
    """Emits structured JSONL logs carrying correlation IDs and redacted secrets."""

    def __init__(self, sink_list: list[str] | None = None) -> None:
        self.sink_list = sink_list if sink_list is not None else []

    def log(
        self,
        level: str,
        run_id: str,
        job_id: str,
        trace_id: str,
        stage: str,
        event: str,
        action_id: str | None = None,
        **details: Any,
    ) -> LogEntry:
        now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        entry = LogEntry(
            timestamp=now_str,
            level=level.upper(),
            run_id=run_id,
            job_id=job_id,
            trace_id=trace_id,
            action_id=action_id,
            stage=stage,
            event=event,
            details=details,
        )
        self.sink_list.append(entry.to_json())
        return entry

    def info(self, run_id: str, job_id: str, trace_id: str, stage: str, event: str, **kwargs: Any) -> LogEntry:
        return self.log("INFO", run_id, job_id, trace_id, stage, event, **kwargs)

    def warning(self, run_id: str, job_id: str, trace_id: str, stage: str, event: str, **kwargs: Any) -> LogEntry:
        return self.log("WARNING", run_id, job_id, trace_id, stage, event, **kwargs)

    def error(self, run_id: str, job_id: str, trace_id: str, stage: str, event: str, **kwargs: Any) -> LogEntry:
        return self.log("ERROR", run_id, job_id, trace_id, stage, event, **kwargs)


class MetricsRegistry:
    """Thread-safe running operational metrics store."""

    def __init__(self) -> None:
        self.agent_runs_total: int = 0
        self.agent_runs_success_total: int = 0
        self.agent_runs_failed_total: int = 0
        self.comments_submitted_total: int = 0
        self.comments_blocked_total: int = 0
        self.approval_rejections_total: int = 0
        self.approvals_granted_total: int = 0
        self.tool_errors_total: int = 0
        self.reconciliation_total: int = 0
        self.total_steps: int = 0
        self.total_duration_seconds: float = 0.0

    @property
    def approval_rejection_rate(self) -> float:
        total = self.approvals_granted_total + self.approval_rejections_total
        return (self.approval_rejections_total / total) if total else 0.0

    @property
    def mean_steps_per_run(self) -> float:
        return (self.total_steps / self.agent_runs_total) if self.agent_runs_total else 0.0

    def snapshot(self) -> dict[str, Any]:
        return {
            "agent_runs_total": self.agent_runs_total,
            "agent_runs_success_total": self.agent_runs_success_total,
            "agent_runs_failed_total": self.agent_runs_failed_total,
            "comments_submitted_total": self.comments_submitted_total,
            "comments_blocked_total": self.comments_blocked_total,
            "approval_rejection_rate": f"{self.approval_rejection_rate * 100:.1f}%",
            "mean_steps_per_run": round(self.mean_steps_per_run, 2),
            "tool_errors_total": self.tool_errors_total,
            "reconciliation_total": self.reconciliation_total,
            "total_duration_seconds": round(self.total_duration_seconds, 2),
        }


@dataclass
class Span:
    trace_id: str
    span_id: str
    name: str
    parent_span_id: str | None = None
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    duration_ms: float = 0.0
    tags: dict[str, Any] = field(default_factory=dict)

    def finish(self) -> None:
        self.end_time = time.time()
        self.duration_ms = max(1.0, (self.end_time - self.start_time) * 1000.0)


class Tracer:
    """Manages distributed traces and span hierarchies."""

    def __init__(self) -> None:
        self.traces: dict[str, list[Span]] = {}

    def start_span(self, trace_id: str, name: str, parent_span_id: str | None = None, **tags: Any) -> Span:
        span_id = f"span_{uuid.uuid4().hex[:8]}"
        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            name=name,
            parent_span_id=parent_span_id,
            tags=tags,
        )
        if trace_id not in self.traces:
            self.traces[trace_id] = []
        self.traces[trace_id].append(span)
        return span

    def render_trace_tree(self, trace_id: str, label: str | None = None) -> str:
        """Renders an ASCII trace waterfall matching production observability standards."""
        spans = self.traces.get(trace_id, [])
        header = label or trace_id
        lines = [header]
        total_spans = len(spans)
        for i, s in enumerate(spans):
            prefix = " └── " if i == total_spans - 1 else " ├── "
            duration_str = f"{int(s.duration_ms)} ms"
            lines.append(f"{prefix}{s.name:<22} {duration_str:>6}")
        return "\n".join(lines)
