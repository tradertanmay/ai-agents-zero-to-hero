"""
Persistent Steward Agent (Applied Agent Systems: A2)
A production-grade, stateful GitHub repository steward agent.
Core principle:
'A persistent agent is not an agent that runs forever.
It is an agent that can stop, remember, wake up, re-observe reality,
and safely continue pursuing a durable goal.'
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any
import uuid

from examples.persistent_agent.approval import ApprovalGate, ApprovalRequest
from examples.persistent_agent.events import WakeEvent, WakeTriggerType
from examples.persistent_agent.goals import Commitment, CommitmentStatus, DurableGoal
from examples.persistent_agent.lifecycle import AgentState, LifecycleEvent, validate_transition
from examples.persistent_agent.memory import ConsolidatedMemory
from examples.persistent_agent.mock_github import MockGitHubAPI
from examples.persistent_agent.runtime import AutonomyBudget, BudgetExceededError, BudgetTracker
from examples.persistent_agent.scheduler import WakeScheduler
from examples.persistent_agent.state import PersistentStateStore

logger = logging.getLogger(__name__)


class PersistentStewardAgent:
    """
    Long-running GitHub project steward with durable state, crash recovery,
    approval gates, and tiered memory consolidation.
    """

    def __init__(
        self,
        agent_id: str,
        goal: DurableGoal,
        github: MockGitHubAPI,
        state_store: PersistentStateStore,
        budget: AutonomyBudget | None = None,
        approval_gate: ApprovalGate | None = None,
        scheduler: WakeScheduler | None = None,
        memory: ConsolidatedMemory | None = None,
        status: AgentState = AgentState.CREATED,
    ):
        self.agent_id = agent_id
        self.goal = goal
        self.github = github
        self.state_store = state_store
        self.budget = budget or AutonomyBudget()
        self.approval_gate = approval_gate or ApprovalGate()
        self.scheduler = scheduler or WakeScheduler()
        self.memory = memory or ConsolidatedMemory()
        self.status = status

        self.created_at = datetime.now(timezone.utc).isoformat()
        self.last_wake_at: str | None = None
        self.next_wake_at: str | None = None
        self.wake_count: int = 0
        self.last_observation: dict[str, Any] = {}
        self.last_action: dict[str, Any] = {}
        self.pending_action: dict[str, Any] | None = None
        self.consecutive_failures: int = 0
        self.pause_reason: str | None = None
        self.termination_condition: str | None = None

        # Runtime tracker per wake
        self._tracker: BudgetTracker | None = None

    def transition_to(self, new_state: AgentState, reason: str = "") -> None:
        """Safely transition state machine and record to audit log."""
        if not validate_transition(self.status, new_state):
            raise ValueError(
                f"Illegal state transition from {self.status.value} to {new_state.value}"
            )
        old_state = self.status
        self.status = new_state
        now = datetime.now(timezone.utc).isoformat()

        # Log transition
        self.state_store.record_event(
            agent_id=self.agent_id,
            event_type="STATE_TRANSITION",
            timestamp=now,
            state_before=old_state.value,
            state_after=new_state.value,
            payload={"reason": reason},
        )
        self.save_checkpoint()

    def save_checkpoint(self) -> None:
        """Persist current execution snapshot to SQLite."""
        checkpoint_data = {
            "memory": self.memory.to_dict(),
            "last_observation": self.last_observation,
            "last_action": self.last_action,
        }
        state_record = {
            "agent_id": self.agent_id,
            "goal_id": self.goal.goal_id,
            "goal_json": self.goal.to_dict(),
            "status": self.status.value,
            "created_at": self.created_at,
            "last_wake_at": self.last_wake_at,
            "next_wake_at": self.next_wake_at,
            "wake_count": self.wake_count,
            "last_observation": self.last_observation,
            "last_action": self.last_action,
            "pending_action": self.pending_action,
            "checkpoint_json": checkpoint_data,
            "memory_summary": self.memory.long_term_summary,
            "agent_version": "1.0.0",
            "prompt_version": "1.0.0",
            "policy_version": "1.0.0",
            "memory_schema_version": "1.0.0",
            "termination_condition": self.termination_condition,
            "pause_reason": self.pause_reason,
            "consecutive_failures": self.consecutive_failures,
        }
        self.state_store.save_agent_state(state_record)

    @classmethod
    def create(
        cls,
        agent_id: str,
        goal: DurableGoal,
        github: MockGitHubAPI,
        state_store: PersistentStateStore,
        budget: AutonomyBudget | None = None,
        approval_gate: ApprovalGate | None = None,
        scheduler: WakeScheduler | None = None,
    ) -> "PersistentStewardAgent":
        """Factory for a brand new persistent agent."""
        agent = cls(
            agent_id=agent_id,
            goal=goal,
            github=github,
            state_store=state_store,
            budget=budget,
            approval_gate=approval_gate,
            scheduler=scheduler,
            status=AgentState.CREATED,
        )
        agent.save_checkpoint()
        agent.transition_to(AgentState.SLEEPING, "Initialized and put to sleep")
        return agent

    @classmethod
    def restore(
        cls,
        agent_id: str,
        github: MockGitHubAPI,
        state_store: PersistentStateStore,
        budget: AutonomyBudget | None = None,
        approval_gate: ApprovalGate | None = None,
        scheduler: WakeScheduler | None = None,
    ) -> "PersistentStewardAgent":
        """Restore an agent from durable SQLite storage."""
        data = state_store.load_agent_state(agent_id)
        if not data:
            raise ValueError(f"No persistent state found for agent_id: {agent_id}")

        goal = DurableGoal.from_dict(data["goal_json"])
        checkpoint = data.get("checkpoint_json", {})
        memory_data = checkpoint.get("memory")
        if memory_data:
            memory = ConsolidatedMemory.from_dict(memory_data)
        else:
            memory = ConsolidatedMemory(long_term_summary=data.get("memory_summary", ""))

        agent = cls(
            agent_id=agent_id,
            goal=goal,
            github=github,
            state_store=state_store,
            budget=budget,
            approval_gate=approval_gate,
            scheduler=scheduler,
            memory=memory,
            status=AgentState(data["status"]),
        )
        agent.created_at = data["created_at"]
        agent.last_wake_at = data.get("last_wake_at")
        agent.next_wake_at = data.get("next_wake_at")
        agent.wake_count = data.get("wake_count", 0)
        agent.last_observation = data.get("last_observation", {})
        agent.last_action = data.get("last_action", {})
        agent.pending_action = data.get("pending_action")
        agent.consecutive_failures = data.get("consecutive_failures", 0)
        agent.pause_reason = data.get("pause_reason")
        agent.termination_condition = data.get("termination_condition")
        return agent

    def wake(self, trigger: WakeEvent) -> None:
        """
        Reactivate the agent from SLEEPING or WAITING_FOR_APPROVAL state.
        Initiates the wake cycle with budget tracking and crash reconciliation.
        """
        if self.status in {AgentState.COMPLETED, AgentState.CANCELLED}:
            return
        if self.status == AgentState.PAUSED:
            logger.info("Agent is PAUSED. Resume required before waking.")
            return

        self._tracker = BudgetTracker(self.budget)
        self.wake_count += 1
        now_iso = datetime.now(timezone.utc).isoformat()
        self.last_wake_at = now_iso

        self.state_store.record_event(
            agent_id=self.agent_id,
            event_type=LifecycleEvent.WAKE.value,
            timestamp=now_iso,
            state_before=self.status.value,
            state_after=AgentState.WAKING.value,
            payload=trigger.to_dict(),
        )

        self.transition_to(AgentState.WAKING, f"Woken by {trigger.trigger_type.value}: {trigger.event_name}")

        self.memory.record_event(
            "WAKE",
            f"Woken via {trigger.trigger_type.value} ({trigger.event_name})",
            trigger.to_dict(),
        )

        # Check for crash recovery reconciliation
        self._reconcile_pending_action_if_any()

    def _reconcile_pending_action_if_any(self) -> None:
        """
        Crash Recovery: If an unresolved action was recorded before process death,
        inspect remote reality to determine if it actually completed.
        """
        if not self.pending_action:
            return

        idempotency_key = self.pending_action.get("idempotency_key")
        action_type = self.pending_action.get("action_type")
        target_entity = self.pending_action.get("target_entity")

        # Check if remote GitHub API recorded execution of this key
        if idempotency_key and self.github.has_idempotency_record(idempotency_key):
            now_iso = datetime.now(timezone.utc).isoformat()
            self.state_store.record_event(
                agent_id=self.agent_id,
                event_type="CRASH_RECONCILED",
                timestamp=now_iso,
                state_before=self.status.value,
                state_after=self.status.value,
                payload={
                    "reconciled_action": action_type,
                    "idempotency_key": idempotency_key,
                    "resolution": "Action already landed on remote before crash. Marked completed.",
                },
            )
            # Fulfill associated commitments
            for c in self.memory.get_open_commitments():
                if c.target_entity == target_entity:
                    c.mark_fulfilled(f"Reconciled via idempotency key: {idempotency_key}")
                    self.state_store.save_commitment(self.agent_id, c)

            self.pending_action = None
            self.save_checkpoint()

    def observe(self) -> dict[str, Any]:
        """
        Fetch repository context from GitHub API and check durable goal validity.
        """
        if self._tracker:
            self._tracker.record_step()
            self._tracker.record_tool_call()

        self.transition_to(AgentState.OBSERVING, "Observing repository state")

        repo_info = self.github.get_repo_info()
        valid, reason = self.goal.revalidate(repo_info)
        if not valid:
            self.termination_condition = reason
            self.transition_to(AgentState.COMPLETED, f"Goal finished or invalid: {reason}")
            return {"goal_status": "terminated", "reason": reason}

        issues = self.github.list_issues(state="open")
        prs = self.github.list_pull_requests(state="open")

        self.last_observation = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "repo_info": repo_info,
            "open_issues": issues,
            "open_prs": prs,
            "workflow_runs": repo_info.get("workflow_runs", []),
        }

        self.state_store.record_event(
            agent_id=self.agent_id,
            event_type=LifecycleEvent.OBSERVATION.value,
            timestamp=self.last_observation["timestamp"],
            state_before=AgentState.OBSERVING.value,
            state_after=AgentState.OBSERVING.value,
            payload={
                "open_issues_count": len(issues),
                "open_prs_count": len(prs),
            },
        )
        return self.last_observation

    def decide(self) -> dict[str, Any]:
        """
        Analyze observations against durable goals and commitments.
        Crucial principle: Abstain when no intervention is required.
        """
        if self._tracker:
            self._tracker.record_step()

        self.transition_to(AgentState.DECIDING, "Evaluating observations and commitments")

        # 1. Check if waiting on pending approval
        if self.pending_action and self.pending_action.get("status") == "WAITING_FOR_APPROVAL":
            token = self.pending_action["approval_token"]
            valid, reason = self.approval_gate.validate_for_execution(token)
            if valid:
                decision = {
                    "action": "EXECUTE_APPROVED_ACTION",
                    "details": self.pending_action,
                }
                return decision
            elif "expired" in reason.lower() or "rejected" in reason.lower():
                self.pending_action = None
                self.memory.record_event("APPROVAL_EXPIRED", reason)

        # 2. Check for actionable open issues without bot comments
        open_issues = self.last_observation.get("open_issues", [])
        for issue in open_issues:
            issue_num = issue["number"]
            # Look up if agent already committed or handled this issue
            target_entity = f"issue:#{issue_num}"
            existing_commitments = [
                c for c in self.memory.commitments if c.target_entity == target_entity
            ]
            if not existing_commitments:
                # Propose triage comment
                idempotency_key = f"{self.agent_id}:triage:issue:{issue_num}"
                decision = {
                    "action": "PROPOSE_TRIAGE_COMMENT",
                    "target_entity": target_entity,
                    "issue_number": issue_num,
                    "body": (
                        f"Hello @{issue['author']}, thank you for opening this issue! "
                        "The repository steward has queued this for maintainer review."
                    ),
                    "idempotency_key": idempotency_key,
                    "requires_approval": True,
                }
                self.state_store.record_event(
                    agent_id=self.agent_id,
                    event_type=LifecycleEvent.ACTION_PROPOSED.value,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    state_before=AgentState.DECIDING.value,
                    state_after=AgentState.DECIDING.value,
                    payload=decision,
                )
                return decision

        # 3. Check for actionable open PRs
        open_prs = self.last_observation.get("open_prs", [])
        for pr in open_prs:
            pr_num = pr["number"]
            target_entity = f"pr:#{pr_num}"
            existing_commitments = [
                c for c in self.memory.commitments if c.target_entity == target_entity
            ]
            if not existing_commitments:
                idempotency_key = f"{self.agent_id}:welcome:pr:{pr_num}"
                decision = {
                    "action": "PROPOSE_PR_WELCOME",
                    "target_entity": target_entity,
                    "pr_number": pr_num,
                    "body": f"Thank you @{pr['author']} for the PR! Automated checks are verified.",
                    "idempotency_key": idempotency_key,
                    "requires_approval": True,
                }
                return decision

        # 4. Default / Optimal decision when no tasks remain: ABSTAIN
        decision = {
            "action": "ABSTAIN",
            "reason": "All issues and pull requests are currently in clean/triaged state.",
        }
        self.state_store.record_event(
            agent_id=self.agent_id,
            event_type=LifecycleEvent.ABSTAIN.value,
            timestamp=datetime.now(timezone.utc).isoformat(),
            state_before=AgentState.DECIDING.value,
            state_after=AgentState.DECIDING.value,
            payload=decision,
        )
        self.memory.record_event("ABSTAIN", decision["reason"])
        return decision

    def request_approval(self, decision: dict[str, Any]) -> ApprovalRequest:
        """
        Create human approval request and transition to WAITING_FOR_APPROVAL.
        """
        if self._tracker:
            self._tracker.record_step()

        self.transition_to(AgentState.WAITING_FOR_APPROVAL, "Requesting human approval")

        target_entity = decision["target_entity"]
        current_entity_state = {}
        if "issue_number" in decision:
            current_entity_state = {"issue_number": decision["issue_number"], "status": "open"}

        req = self.approval_gate.create_request(
            action_type=decision["action"],
            target_entity=target_entity,
            proposed_parameters=decision,
            ttl_seconds=86400,
            current_state=current_entity_state,
        )

        self.pending_action = {
            "status": "WAITING_FOR_APPROVAL",
            "approval_token": req.token,
            "action_type": decision["action"],
            "target_entity": target_entity,
            "parameters": decision,
            "idempotency_key": decision["idempotency_key"],
        }

        # Record a commitment
        commitment = Commitment(
            commitment_id=str(uuid.uuid4()),
            goal_id=self.goal.goal_id,
            description=f"Complete triage for {target_entity}",
            target_entity=target_entity,
            status=CommitmentStatus.IN_PROGRESS,
        )
        self.memory.add_commitment(commitment)
        self.state_store.save_commitment(self.agent_id, commitment)

        self.state_store.record_event(
            agent_id=self.agent_id,
            event_type=LifecycleEvent.APPROVAL_REQUESTED.value,
            timestamp=datetime.now(timezone.utc).isoformat(),
            state_before=AgentState.WAITING_FOR_APPROVAL.value,
            state_after=AgentState.WAITING_FOR_APPROVAL.value,
            payload={"approval_token": req.token, "target_entity": target_entity},
        )
        self.save_checkpoint()
        return req

    def act(self, approved_action: dict[str, Any]) -> dict[str, Any]:
        """
        Execute an approved action against mock GitHub with idempotency protection.
        """
        if self._tracker:
            self._tracker.record_step()
            self._tracker.record_write()

        self.transition_to(AgentState.ACTING, "Executing approved action")

        action_type = approved_action.get("action") or approved_action.get("action_type")
        params = approved_action.get("parameters") or approved_action
        idempotency_key = params.get("idempotency_key")

        try:
            result = {}
            if action_type == "PROPOSE_TRIAGE_COMMENT":
                issue_num = params["issue_number"]
                body = params["body"]
                result = self.github.post_issue_comment(
                    issue_number=issue_num,
                    body=body,
                    author="steward[bot]",
                    idempotency_key=idempotency_key,
                )
                self.github.add_label(issue_num, "triaged", idempotency_key=f"{idempotency_key}:label")

            elif action_type == "PROPOSE_PR_WELCOME":
                pr_num = params["pr_number"]
                body = params["body"]
                result = self.github.post_issue_comment(
                    issue_number=pr_num,
                    body=body,
                    author="steward[bot]",
                    idempotency_key=idempotency_key,
                )

            self.last_action = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": action_type,
                "result": result,
            }

            self.state_store.record_event(
                agent_id=self.agent_id,
                event_type=LifecycleEvent.ACTION_EXECUTED.value,
                timestamp=self.last_action["timestamp"],
                state_before=AgentState.ACTING.value,
                state_after=AgentState.ACTING.value,
                payload=self.last_action,
            )

            # Move to verify
            self.verify(params.get("target_entity", ""), result)
            return result

        except Exception as e:
            self.consecutive_failures += 1
            if self.consecutive_failures >= self.budget.max_consecutive_failures:
                self.pause(f"Max consecutive failures exceeded: {str(e)}")
            else:
                self.transition_to(AgentState.FAILED, f"Action execution error: {str(e)}")
            raise

    def verify(self, target_entity: str, execution_result: dict[str, Any]) -> None:
        """
        Verify the action landed cleanly and mark commitment fulfilled.
        """
        if self._tracker:
            self._tracker.record_step()

        self.transition_to(AgentState.VERIFYING, f"Verifying execution on {target_entity}")

        # Update matching commitment
        for c in self.memory.get_open_commitments():
            if c.target_entity == target_entity:
                c.mark_fulfilled(f"Action verified successfully: {json.dumps(execution_result)}")
                self.state_store.save_commitment(self.agent_id, c)

        self.pending_action = None
        self.consecutive_failures = 0

        self.state_store.record_event(
            agent_id=self.agent_id,
            event_type=LifecycleEvent.VERIFIED.value,
            timestamp=datetime.now(timezone.utc).isoformat(),
            state_before=AgentState.VERIFYING.value,
            state_after=AgentState.VERIFYING.value,
            payload={"target_entity": target_entity, "result": execution_result},
        )

    def sleep(self) -> None:
        """
        Perform memory compaction, compute next scheduled wake, and enter SLEEPING.
        """
        if self.status in {AgentState.COMPLETED, AgentState.CANCELLED, AgentState.PAUSED}:
            return

        # Compact memory if buffer full
        compacted = self.memory.compact(max_recent_events=5)
        if compacted > 0:
            self.state_store.record_event(
                agent_id=self.agent_id,
                event_type=LifecycleEvent.MEMORY_COMPACTED.value,
                timestamp=datetime.now(timezone.utc).isoformat(),
                state_before=self.status.value,
                state_after=self.status.value,
                payload={"compacted_events_count": compacted},
            )

        if self.status == AgentState.SLEEPING:
            self.save_checkpoint()
            return

        # Plan next scheduled wake
        next_wake = self.scheduler.compute_next_wake(
            consecutive_failures=self.consecutive_failures
        )
        self.next_wake_at = next_wake.isoformat()

        self.transition_to(AgentState.SLEEPING, f"Scheduled next wake at {self.next_wake_at}")

        self.state_store.record_event(
            agent_id=self.agent_id,
            event_type=LifecycleEvent.SLEEP.value,
            timestamp=datetime.now(timezone.utc).isoformat(),
            state_before=AgentState.SLEEPING.value,
            state_after=AgentState.SLEEPING.value,
            payload={"next_wake_at": self.next_wake_at},
        )
        self._tracker = None
        self.save_checkpoint()

    def pause(self, reason: str) -> None:
        """Put agent into protective PAUSED state."""
        self.pause_reason = reason
        self.transition_to(AgentState.PAUSED, reason)
        self.state_store.record_event(
            agent_id=self.agent_id,
            event_type=LifecycleEvent.PAUSED.value,
            timestamp=datetime.now(timezone.utc).isoformat(),
            state_before=AgentState.PAUSED.value,
            state_after=AgentState.PAUSED.value,
            payload={"reason": reason},
        )

    def resume(self) -> None:
        """Resume an agent from PAUSED state back into SLEEPING."""
        if self.status != AgentState.PAUSED:
            return
        self.pause_reason = None
        self.consecutive_failures = 0
        self.transition_to(AgentState.SLEEPING, "Operator resumed agent")

    def execute_wake_cycle(self, trigger: WakeEvent) -> dict[str, Any]:
        """
        Execute a complete end-to-end wake cycle safely:
        wake -> observe -> decide -> [request_approval | act] -> sleep
        """
        self.wake(trigger)
        if self.status in {AgentState.COMPLETED, AgentState.CANCELLED, AgentState.PAUSED}:
            return {"status": self.status.value}

        obs = self.observe()
        if self.status in {AgentState.COMPLETED, AgentState.CANCELLED}:
            return {"status": self.status.value, "observation": obs}

        decision = self.decide()

        if decision.get("action") == "ABSTAIN":
            self.sleep()
            return {"status": "SLEEPING", "decision": decision}

        if decision.get("action") == "EXECUTE_APPROVED_ACTION":
            self.act(decision["details"])
            self.sleep()
            return {"status": "SLEEPING", "action_taken": decision}

        if decision.get("requires_approval"):
            req = self.request_approval(decision)
            # Cannot act immediately without approval; sleep or stay waiting
            self.save_checkpoint()
            return {
                "status": "WAITING_FOR_APPROVAL",
                "approval_token": req.token,
                "decision": decision,
            }

        # Otherwise act directly
        self.act(decision)
        self.sleep()
        return {"status": "SLEEPING", "action_taken": decision}
