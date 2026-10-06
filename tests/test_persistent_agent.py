"""
Unit & Integration Tests for Persistent Agent (Applied Agent Systems: A2)
Tests durable execution, lifecycle state machine, SQLite checkpointing,
wake scheduling, crash reconciliation, approval gating, autonomy budgets,
and memory consolidation.
Pure Python 3.11+ standard library.
"""

from datetime import datetime, timedelta, timezone
import os
import shutil
import tempfile
import unittest

from examples.persistent_agent.agent import PersistentStewardAgent
from examples.persistent_agent.approval import ApprovalGate, ApprovalStatus
from examples.persistent_agent.events import EventBus, WakeEvent, WakeTriggerType
from examples.persistent_agent.goals import Commitment, CommitmentStatus, DurableGoal
from examples.persistent_agent.lifecycle import (
    AgentState,
    LifecycleEvent,
    validate_transition,
)
from examples.persistent_agent.memory import ConsolidatedMemory
from examples.persistent_agent.mock_github import MockGitHubAPI
from examples.persistent_agent.runtime import (
    AutonomyBudget,
    BudgetExceededError,
    BudgetTracker,
)
from examples.persistent_agent.scheduler import WakeScheduler
from examples.persistent_agent.state import PersistentStateStore


class TestLifecycleStateMachine(unittest.TestCase):
    """Verify state transitions and constraints."""

    def test_valid_transitions(self):
        self.assertTrue(validate_transition(AgentState.CREATED, AgentState.SLEEPING))
        self.assertTrue(validate_transition(AgentState.SLEEPING, AgentState.WAKING))
        self.assertTrue(validate_transition(AgentState.WAKING, AgentState.OBSERVING))
        self.assertTrue(validate_transition(AgentState.OBSERVING, AgentState.DECIDING))
        self.assertTrue(validate_transition(AgentState.DECIDING, AgentState.WAITING_FOR_APPROVAL))
        self.assertTrue(validate_transition(AgentState.WAITING_FOR_APPROVAL, AgentState.ACTING))
        self.assertTrue(validate_transition(AgentState.ACTING, AgentState.VERIFYING))
        self.assertTrue(validate_transition(AgentState.VERIFYING, AgentState.SLEEPING))

    def test_terminal_states_have_no_transitions(self):
        self.assertFalse(validate_transition(AgentState.COMPLETED, AgentState.WAKING))
        self.assertFalse(validate_transition(AgentState.COMPLETED, AgentState.SLEEPING))
        self.assertFalse(validate_transition(AgentState.CANCELLED, AgentState.WAKING))

    def test_invalid_transitions_rejected(self):
        self.assertFalse(validate_transition(AgentState.CREATED, AgentState.ACTING))
        self.assertFalse(validate_transition(AgentState.OBSERVING, AgentState.VERIFYING))


class TestDurableGoalsAndCommitments(unittest.TestCase):
    """Verify goal revalidation, expiration, and commitment tracking."""

    def test_goal_expiration(self):
        past_iso = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        goal = DurableGoal.create(
            description="Short term test goal",
            target_repo="acme/test-repo",
            expires_at=past_iso,
        )
        self.assertTrue(goal.is_expired())
        valid, reason = goal.revalidate({"is_archived": False})
        self.assertFalse(valid)
        self.assertFalse(goal.is_active)
        self.assertIn("expired", reason.lower())

    def test_goal_repo_archived_cancellation(self):
        goal = DurableGoal.create(
            description="Active steward goal",
            target_repo="acme/test-repo",
        )
        valid, reason = goal.revalidate({"is_archived": True})
        self.assertFalse(valid)
        self.assertFalse(goal.is_active)
        self.assertIn("archived", reason.lower())

    def test_commitment_lifecycle(self):
        comm = Commitment(
            commitment_id="comm-101",
            goal_id="goal-1",
            description="Triage issue #5",
            target_entity="issue:#5",
        )
        self.assertEqual(comm.status, CommitmentStatus.OPEN)
        comm.mark_fulfilled("Posted triage comment id: 99")
        self.assertEqual(comm.status, CommitmentStatus.FULFILLED)
        self.assertIn("99", comm.fulfillment_evidence)


class TestApprovalGate(unittest.TestCase):
    """Verify human approval tokens, expiry, and stale action protection."""

    def setUp(self):
        self.gate = ApprovalGate()

    def test_create_and_approve(self):
        req = self.gate.create_request(
            action_type="github.post_comment",
            target_entity="issue:#12",
            proposed_parameters={"body": "Hello!"},
            ttl_seconds=3600,
        )
        self.assertEqual(req.status, ApprovalStatus.PENDING)

        approved = self.gate.approve(req.token, reason="Looks good")
        self.assertTrue(approved)
        valid, reason = self.gate.validate_for_execution(req.token)
        self.assertTrue(valid)

    def test_expired_approval_rejection(self):
        req = self.gate.create_request(
            action_type="github.post_comment",
            target_entity="issue:#12",
            proposed_parameters={"body": "Hello!"},
            ttl_seconds=-10,  # Expired immediately
        )
        approved = self.gate.approve(req.token)
        self.assertFalse(approved)
        valid, reason = self.gate.validate_for_execution(req.token)
        self.assertFalse(valid)
        self.assertIn("expired", reason.lower())

    def test_stale_action_protection(self):
        initial_state = {"issue_number": 12, "state": "open"}
        req = self.gate.create_request(
            action_type="github.close_issue",
            target_entity="issue:#12",
            proposed_parameters={},
            ttl_seconds=3600,
            current_state=initial_state,
        )
        self.gate.approve(req.token)

        # Entity changed in the meantime (e.g., someone else changed it)
        drifted_state = {"issue_number": 12, "state": "closed"}
        valid, reason = self.gate.validate_for_execution(req.token, current_state=drifted_state)
        self.assertFalse(valid)
        self.assertIn("stale action", reason.lower())


class TestMemoryCompaction(unittest.TestCase):
    """Verify tiered memory consolidation and rolling summaries."""

    def test_compaction_prevents_bloat(self):
        memory = ConsolidatedMemory()
        for i in range(10):
            memory.record_event("CYCLE", f"Completed cycle {i}")

        self.assertEqual(len(memory.recent_events), 10)
        self.assertEqual(memory.long_term_summary, "")

        compacted = memory.compact(max_recent_events=5)
        self.assertEqual(compacted, 5)
        self.assertEqual(len(memory.recent_events), 5)
        self.assertIn("Completed cycle 0", memory.long_term_summary)
        self.assertIn("Completed cycle 4", memory.long_term_summary)

    def test_fulfilled_commitment_archival(self):
        memory = ConsolidatedMemory()
        comm = Commitment(
            commitment_id="c1",
            goal_id="g1",
            description="Resolve issue 4",
            target_entity="issue:#4",
        )
        comm.mark_fulfilled("Done")
        memory.add_commitment(comm)

        memory.recent_events = [{"type": "E", "summary": "s"}] * 6
        memory.compact(max_recent_events=5)
        self.assertEqual(len(memory.commitments), 0)
        self.assertIn("Commitment c1", memory.long_term_summary)


class TestAutonomyBudget(unittest.TestCase):
    """Verify execution limits, rate limits, and pause containment."""

    def test_step_budget_exceeded(self):
        budget = AutonomyBudget(max_steps_per_wake=2)
        tracker = BudgetTracker(budget)
        tracker.record_step()
        tracker.record_step()
        with self.assertRaises(BudgetExceededError):
            tracker.record_step()

    def test_write_budget_exceeded(self):
        budget = AutonomyBudget(max_writes_per_wake=1)
        tracker = BudgetTracker(budget)
        tracker.record_write()
        with self.assertRaises(BudgetExceededError):
            tracker.record_write()


class TestPersistentStateStore(unittest.TestCase):
    """Verify SQLite persistence and checkpoint loading."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_state.db")
        self.store = PersistentStateStore(self.db_path)

    def tearDown(self):
        self.store.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_load_agent_state(self):
        state = {
            "agent_id": "test-agent-1",
            "goal_id": "g-1",
            "goal_json": {"goal_id": "g-1", "description": "Maintain", "target_repo": "r"},
            "status": "SLEEPING",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "wake_count": 3,
            "last_observation": {"clean": True},
            "last_action": {"done": True},
            "pending_action": None,
            "checkpoint_json": {"data": 123},
            "memory_summary": "Summary text",
        }
        self.store.save_agent_state(state)
        loaded = self.store.load_agent_state("test-agent-1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["agent_id"], "test-agent-1")
        self.assertEqual(loaded["status"], "SLEEPING")
        self.assertEqual(loaded["wake_count"], 3)
        self.assertEqual(loaded["last_observation"]["clean"], True)

    def test_record_and_load_event_log(self):
        self.store.save_agent_state({
            "agent_id": "test-agent-1",
            "status": "SLEEPING",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        ts = datetime.now(timezone.utc).isoformat()
        self.store.record_event(
            agent_id="test-agent-1",
            event_type="WAKE",
            timestamp=ts,
            state_before="SLEEPING",
            state_after="WAKING",
            payload={"source": "timer"},
        )
        logs = self.store.load_event_log("test-agent-1")
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["event_type"], "WAKE")
        self.assertEqual(logs[0]["payload_json"]["source"], "timer")


class TestPersistentStewardAgentIntegration(unittest.TestCase):
    """End-to-end integration tests for PersistentStewardAgent."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_agent.db")
        self.store = PersistentStateStore(self.db_path)
        self.github = MockGitHubAPI("org/repo")
        self.gate = ApprovalGate()
        self.scheduler = WakeScheduler(base_interval_seconds=60)
        self.budget = AutonomyBudget(max_steps_per_wake=10, max_writes_per_wake=5)
        self.goal = DurableGoal.create("Maintain repo", "org/repo")
        self.agent = PersistentStewardAgent.create(
            agent_id="agent-int-1",
            goal=self.goal,
            github=self.github,
            state_store=self.store,
            budget=self.budget,
            approval_gate=self.gate,
            scheduler=self.scheduler,
        )

    def tearDown(self):
        self.store.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_abstention_on_clean_repository(self):
        """Persistent agents must abstain when no action is needed."""
        wake_ev = WakeEvent(WakeTriggerType.SCHEDULED, "timer.check")
        res = self.agent.execute_wake_cycle(wake_ev)
        self.assertEqual(res["status"], "SLEEPING")
        self.assertEqual(res["decision"]["action"], "ABSTAIN")
        self.assertEqual(self.agent.status, AgentState.SLEEPING)

    def test_issue_triage_flow_with_approval_and_persistence(self):
        """Full triage workflow across process recreation."""
        issue = self.github.create_issue("Bug in parser", "Fails on trailing slash")
        wake_ev = WakeEvent(WakeTriggerType.EVENT, "github.issue.opened")
        res = self.agent.execute_wake_cycle(wake_ev)

        self.assertEqual(res["status"], "WAITING_FOR_APPROVAL")
        token = res["approval_token"]
        self.assertIsNotNone(token)
        self.assertEqual(len(self.agent.memory.get_open_commitments()), 1)

        # Drop agent instance and restore from SQLite
        del self.agent
        restored_agent = PersistentStewardAgent.restore(
            agent_id="agent-int-1",
            github=self.github,
            state_store=self.store,
            budget=self.budget,
            approval_gate=self.gate,
            scheduler=self.scheduler,
        )
        self.assertEqual(restored_agent.status, AgentState.WAITING_FOR_APPROVAL)
        self.assertIsNotNone(restored_agent.pending_action)

        # Maintainer approves
        self.gate.approve(token)

        # Agent wakes and completes action
        wake_review = WakeEvent(WakeTriggerType.MANUAL, "operator.approved")
        res_review = restored_agent.execute_wake_cycle(wake_review)
        self.assertEqual(res_review["status"], "SLEEPING")
        self.assertEqual(len(self.github.issues[issue.number].comments), 1)
        self.assertIn("triaged", self.github.issues[issue.number].labels)
        self.assertEqual(len(restored_agent.memory.get_open_commitments()), 0)

    def test_crash_recovery_prevents_duplicate_mutation(self):
        """Idempotency reconciliation prevents double-posting after a crash."""
        pr = self.github.create_pull_request("Fix typings", "Adds type annotations")
        idemp_key = f"{self.agent.agent_id}:welcome:pr:{pr.number}"

        # Simulate that write landed on GitHub before crash
        self.github.post_issue_comment(
            issue_number=pr.number,
            body="Welcome!",
            idempotency_key=idemp_key,
        )

        # Inject pending action into agent state
        self.agent.pending_action = {
            "status": "WAITING_FOR_APPROVAL",
            "action_type": "PROPOSE_PR_WELCOME",
            "target_entity": f"pr:#{pr.number}",
            "idempotency_key": idemp_key,
        }
        self.agent.save_checkpoint()

        # Re-wake
        wake_ev = WakeEvent(WakeTriggerType.EVENT, "github.pr.opened")
        self.agent.wake(wake_ev)

        # Pending action was reconciled and cleared
        self.assertIsNone(self.agent.pending_action)
        # Verify no duplicate comment was posted
        self.assertEqual(len(self.github.pull_requests[pr.number].comments), 1)


if __name__ == "__main__":
    unittest.main()
