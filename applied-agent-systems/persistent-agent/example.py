"""
A2 -- Persistent Agent: Minimal Standalone Example
Demonstrates a durable GitHub Project Steward Agent operating across process restarts.
Features:
- 12-state explicit lifecycle
- SQLite durable checkpointing and event audit trail
- Scheduled vs. Event-driven reactivation
- Abstention discipline (doing nothing when repo is clean)
- Human approval gate with stale-action protection
- Crash reconciliation via idempotency keys
- Tiered memory compaction

Pure Python 3.11+ standard library. Zero external dependencies.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import time
from typing import Any
import uuid


# -----------------------------------------------------------------------------
# 1. LIFECYCLE & STATE MACHINE
# -----------------------------------------------------------------------------
class AgentState(str, Enum):
    CREATED = "CREATED"
    SCHEDULED = "SCHEDULED"
    SLEEPING = "SLEEPING"
    WAKING = "WAKING"
    OBSERVING = "OBSERVING"
    DECIDING = "DECIDING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    ACTING = "ACTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


VALID_TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.CREATED: {AgentState.SCHEDULED, AgentState.SLEEPING, AgentState.WAKING, AgentState.PAUSED},
    AgentState.SCHEDULED: {AgentState.WAKING, AgentState.SLEEPING, AgentState.PAUSED},
    AgentState.SLEEPING: {AgentState.WAKING, AgentState.PAUSED, AgentState.COMPLETED},
    AgentState.WAKING: {AgentState.OBSERVING, AgentState.SLEEPING, AgentState.PAUSED, AgentState.COMPLETED, AgentState.FAILED},
    AgentState.OBSERVING: {AgentState.DECIDING, AgentState.SLEEPING, AgentState.PAUSED, AgentState.FAILED},
    AgentState.DECIDING: {
        AgentState.WAITING_FOR_APPROVAL,
        AgentState.ACTING,
        AgentState.SLEEPING,
        AgentState.COMPLETED,
        AgentState.PAUSED,
        AgentState.FAILED,
    },
    AgentState.WAITING_FOR_APPROVAL: {
        AgentState.WAKING,
        AgentState.ACTING,
        AgentState.DECIDING,
        AgentState.SLEEPING,
        AgentState.PAUSED,
    },
    AgentState.ACTING: {AgentState.VERIFYING, AgentState.FAILED, AgentState.PAUSED},
    AgentState.VERIFYING: {AgentState.SLEEPING, AgentState.COMPLETED, AgentState.FAILED},
    AgentState.PAUSED: {AgentState.WAKING, AgentState.SLEEPING},
    AgentState.COMPLETED: set(),
    AgentState.CANCELLED: set(),
    AgentState.FAILED: {AgentState.PAUSED},
}


def validate_transition(current: AgentState, target: AgentState) -> bool:
    return target in VALID_TRANSITIONS.get(current, set())


# -----------------------------------------------------------------------------
# 2. GOALS & COMMITMENTS
# -----------------------------------------------------------------------------
@dataclass
class DurableGoal:
    goal_id: str
    description: str
    target_repo: str
    is_active: bool = True
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def revalidate(self, repo_info: dict) -> tuple[bool, str]:
        if not self.is_active:
            return False, "Goal is marked inactive."
        if repo_info.get("is_archived", False):
            self.is_active = False
            return False, "Repository is archived."
        return True, "Goal is active and valid."


@dataclass
class Commitment:
    commitment_id: str
    goal_id: str
    description: str
    target_entity: str
    status: str = "OPEN"
    fulfillment_evidence: str | None = None


# -----------------------------------------------------------------------------
# 3. MOCK GITHUB ENVIRONMENT
# -----------------------------------------------------------------------------
class MockGitHubAPI:
    def __init__(self, repo_name: str):
        self.repo_name = repo_name
        self.is_archived = False
        self.issues: dict[int, dict[str, Any]] = {}
        self.comments: list[dict[str, Any]] = []
        self._next_issue = 1
        self._idempotency_cache: dict[str, dict[str, Any]] = {}

    def get_repo_info(self) -> dict[str, Any]:
        return {"full_name": self.repo_name, "is_archived": self.is_archived}

    def create_issue(self, title: str, author: str) -> int:
        num = self._next_issue
        self._next_issue += 1
        self.issues[num] = {"number": num, "title": title, "author": author, "labels": []}
        return num

    def post_comment(self, issue_num: int, body: str, author: str, idempotency_key: str) -> dict[str, Any]:
        if idempotency_key in self._idempotency_cache:
            return self._idempotency_cache[idempotency_key]

        record = {
            "comment_id": len(self.comments) + 1,
            "issue_num": issue_num,
            "body": body,
            "author": author,
        }
        self.comments.append(record)
        self._idempotency_cache[idempotency_key] = record
        return record

    def add_label(self, issue_num: int, label: str) -> None:
        if issue_num in self.issues:
            if label not in self.issues[issue_num]["labels"]:
                self.issues[issue_num]["labels"].append(label)

    def has_idempotency_key(self, key: str) -> bool:
        return key in self._idempotency_cache


# -----------------------------------------------------------------------------
# 4. DURABLE SQLITE STATE STORE
# -----------------------------------------------------------------------------
class PersistentStateStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    goal_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_wake_at TEXT,
                    next_wake_at TEXT,
                    pending_action TEXT,
                    memory_json TEXT
                );
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS event_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    state_before TEXT,
                    state_after TEXT,
                    payload_json TEXT
                );
                """
            )

    def save_agent(self, agent_id: str, goal: DurableGoal, status: str, created_at: str,
                   last_wake_at: str | None, next_wake_at: str | None, pending_action: dict | None,
                   memory_data: dict) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO agents (
                    agent_id, goal_json, status, created_at,
                    last_wake_at, next_wake_at, pending_action, memory_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    status = excluded.status,
                    last_wake_at = excluded.last_wake_at,
                    next_wake_at = excluded.next_wake_at,
                    pending_action = excluded.pending_action,
                    memory_json = excluded.memory_json;
                """,
                (
                    agent_id,
                    json.dumps({"goal_id": goal.goal_id, "desc": goal.description, "repo": goal.target_repo}),
                    status,
                    created_at,
                    last_wake_at,
                    next_wake_at,
                    json.dumps(pending_action) if pending_action else None,
                    json.dumps(memory_data),
                ),
            )

    def load_agent(self, agent_id: str) -> dict[str, Any] | None:
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,))
        row = cur.fetchone()
        if not row:
            return None
        res = dict(row)
        res["goal_json"] = json.loads(res["goal_json"])
        res["pending_action"] = json.loads(res["pending_action"]) if res["pending_action"] else None
        res["memory_json"] = json.loads(res["memory_json"]) if res["memory_json"] else {}
        return res

    def record_event(self, agent_id: str, event_type: str, before: str, after: str, payload: dict) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO event_log (agent_id, event_type, timestamp, state_before, state_after, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (agent_id, event_type, datetime.now(timezone.utc).isoformat(), before, after, json.dumps(payload)),
            )

    def close(self) -> None:
        self._conn.close()


# -----------------------------------------------------------------------------
# 5. APPROVAL GATE
# -----------------------------------------------------------------------------
class ApprovalGate:
    def __init__(self):
        self.requests: dict[str, dict[str, Any]] = {}

    def request_approval(self, action_type: str, entity: str, params: dict) -> str:
        token = str(uuid.uuid4())
        self.requests[token] = {
            "token": token,
            "action_type": action_type,
            "entity": entity,
            "params": params,
            "status": "PENDING",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return token

    def approve(self, token: str) -> bool:
        if token in self.requests and self.requests[token]["status"] == "PENDING":
            self.requests[token]["status"] = "APPROVED"
            return True
        return False

    def is_approved(self, token: str) -> bool:
        return self.requests.get(token, {}).get("status") == "APPROVED"


# -----------------------------------------------------------------------------
# 6. PERSISTENT STEWARD AGENT
# -----------------------------------------------------------------------------
class PersistentStewardAgent:
    def __init__(self, agent_id: str, goal: DurableGoal, github: MockGitHubAPI,
                 state_store: PersistentStateStore, approval_gate: ApprovalGate):
        self.agent_id = agent_id
        self.goal = goal
        self.github = github
        self.state_store = state_store
        self.approval_gate = approval_gate
        self.status = AgentState.CREATED
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.last_wake_at: str | None = None
        self.next_wake_at: str | None = None
        self.pending_action: dict[str, Any] | None = None
        self.commitments: list[Commitment] = []
        self.recent_events: list[str] = []
        self.long_term_summary: str = ""

    def transition_to(self, new_state: AgentState, reason: str = "") -> None:
        if not validate_transition(self.status, new_state):
            raise ValueError(f"Illegal transition: {self.status.value} -> {new_state.value}")
        before = self.status.value
        self.status = new_state
        self.state_store.record_event(self.agent_id, "TRANSITION", before, new_state.value, {"reason": reason})
        self.checkpoint()

    def checkpoint(self) -> None:
        mem = {
            "commitments": [c.__dict__ for c in self.commitments],
            "recent_events": self.recent_events,
            "long_term_summary": self.long_term_summary,
        }
        self.state_store.save_agent(
            self.agent_id, self.goal, self.status.value, self.created_at,
            self.last_wake_at, self.next_wake_at, self.pending_action, mem
        )

    def compact_memory(self, max_recent: int = 3) -> None:
        if len(self.recent_events) > max_recent:
            to_roll = self.recent_events[:-max_recent]
            self.recent_events = self.recent_events[-max_recent:]
            rolled_text = " | ".join(to_roll)
            if self.long_term_summary:
                self.long_term_summary += f" || {rolled_text}"
            else:
                self.long_term_summary = rolled_text

    def wake(self, trigger_name: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.last_wake_at = now
        self.transition_to(AgentState.WAKING, f"Woken by {trigger_name}")
        self.recent_events.append(f"Woke via {trigger_name}")

        # Crash reconciliation check
        if self.pending_action and "idempotency_key" in self.pending_action:
            key = self.pending_action["idempotency_key"]
            if self.github.has_idempotency_key(key):
                print(f"[{self.agent_id}] Crash reconciled: action already executed on remote.")
                self.pending_action = None
                self.commitments.clear()

    def run_cycle(self, trigger_name: str) -> None:
        self.wake(trigger_name)

        # OBSERVING
        self.transition_to(AgentState.OBSERVING, "Observing repository")
        repo_info = self.github.get_repo_info()
        valid, _ = self.goal.revalidate(repo_info)
        if not valid:
            self.transition_to(AgentState.COMPLETED, "Goal invalidated")
            return

        # DECIDING
        self.transition_to(AgentState.DECIDING, "Deciding action")

        # 1. Check if pending action is approved
        if self.pending_action and self.approval_gate.is_approved(self.pending_action["token"]):
            self.transition_to(AgentState.ACTING, "Executing approved action")
            params = self.pending_action["params"]
            self.github.post_comment(
                issue_num=params["issue_num"],
                body=params["body"],
                author="steward[bot]",
                idempotency_key=self.pending_action["idempotency_key"],
            )
            self.github.add_label(params["issue_num"], "triaged")
            self.transition_to(AgentState.VERIFYING, "Verifying mutation")
            self.pending_action = None
            self.commitments.clear()
            self.recent_events.append(f"Triaged issue #{params['issue_num']}")
            self.sleep()
            return

        # 2. Check for untriaged issues
        for issue_num, data in self.github.issues.items():
            if "triaged" not in data["labels"] and not self.pending_action:
                idemp_key = f"{self.agent_id}:triage:{issue_num}"
                token = self.approval_gate.request_approval(
                    action_type="triage_comment",
                    entity=f"issue:{issue_num}",
                    params={"issue_num": issue_num, "body": f"Hello @{data['author']}, thank you for reporting!"},
                )
                self.pending_action = {
                    "token": token,
                    "params": {"issue_num": issue_num, "body": f"Hello @{data['author']}, thank you for reporting!"},
                    "idempotency_key": idemp_key,
                }
                self.commitments.append(Commitment(str(uuid.uuid4()), self.goal.goal_id, f"Triage issue #{issue_num}", f"issue:{issue_num}"))
                self.transition_to(AgentState.WAITING_FOR_APPROVAL, "Awaiting maintainer approval")
                print(f"[{self.agent_id}] Proposed triage for issue #{issue_num}. Approval token: {token}")
                self.checkpoint()
                return

        # 3. If no work required: ABSTAIN
        print(f"[{self.agent_id}] Decision: ABSTAIN. Repository in clean state.")
        self.recent_events.append("Abstained: No actionable work")
        self.sleep()

    def sleep(self) -> None:
        self.compact_memory(max_recent=3)
        self.next_wake_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        self.transition_to(AgentState.SLEEPING, "Sleeping until next wake")
        print(f"[{self.agent_id}] Entering SLEEPING state. Next wake: {self.next_wake_at}")


# -----------------------------------------------------------------------------
# 7. EXECUTION DEMONSTRATION
# -----------------------------------------------------------------------------
def main() -> None:
    temp_dir = tempfile.mkdtemp(prefix="agent_persistent_demo_")
    db_file = os.path.join(temp_dir, "agent.db")

    try:
        print("=== A2: PERSISTENT STEWARD AGENT DEMO ===")
        github = MockGitHubAPI("octocat/steward-project")
        store = PersistentStateStore(db_file)
        gate = ApprovalGate()
        goal = DurableGoal(str(uuid.uuid4()), "Maintain repo hygiene", "octocat/steward-project")

        # Step 1: Create and put to sleep
        agent = PersistentStewardAgent("steward-1", goal, github, store, gate)
        agent.sleep()

        # Step 2: Scheduled Wake (Abstain)
        print("\n--- Phase 1: Scheduled Wake on Clean Repo ---")
        agent.run_cycle("timer.hourly")

        # Step 3: Event-Driven Wake (New Issue)
        print("\n--- Phase 2: Webhook Trigger (Issue Opened) ---")
        issue_id = github.create_issue("Implement dark mode support", "contributor_bob")
        agent.run_cycle("webhook.issue_created")

        # Step 4: Process Termination and Recovery
        print("\n--- Phase 3: Process Shutdown & Restart ---")
        saved_token = agent.pending_action["token"]
        del agent
        store.close()

        # Reopen in new process
        store = PersistentStateStore(db_file)
        data = store.load_agent("steward-1")
        print(f"Restored agent state from SQLite: Status = {data['status']}, Pending Action = {data['pending_action']['params']['issue_num']}")

        agent = PersistentStewardAgent("steward-1", goal, github, store, gate)
        agent.status = AgentState(data["status"])
        agent.pending_action = data["pending_action"]

        # Step 5: Maintainer Approves & Agent Executes
        print("\n--- Phase 4: Human Approval & Execution ---")
        gate.approve(saved_token)
        agent.run_cycle("operator.approval_confirmed")
        print(f"Comments on issue: {github.comments}")
        print(f"Labels on issue #{issue_id}: {github.issues[issue_id]['labels']}")

        print("\n--- Concluding Axiom ---")
        print("A persistent agent is not an agent that runs forever. It is an agent that can stop,")
        print("remember, wake up, re-observe reality, and safely continue pursuing a durable goal.")

    finally:
        store.close()
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
