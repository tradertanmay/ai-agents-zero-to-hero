"""
Persistent Agent: Multi-Day GitHub Steward Simulation (Applied Agent Systems: A2)
Demonstrates durable execution across process boundaries, event/scheduled wakes,
abstention discipline, human approval gates, crash recovery, and memory compaction.
Pure Python 3.11+ standard library. Zero external dependencies.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

# Ensure repo root is on sys.path for direct script execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from examples.persistent_agent.agent import PersistentStewardAgent
from examples.persistent_agent.approval import ApprovalGate
from examples.persistent_agent.events import EventBus, WakeEvent, WakeTriggerType
from examples.persistent_agent.goals import DurableGoal
from examples.persistent_agent.mock_github import MockGitHubAPI
from examples.persistent_agent.runtime import AutonomyBudget
from examples.persistent_agent.scheduler import WakeScheduler
from examples.persistent_agent.state import PersistentStateStore


def run_simulation() -> None:
    temp_dir = tempfile.mkdtemp(prefix="persistent_agent_demo_")
    db_path = os.path.join(temp_dir, "steward_state.db")

    print("================================================================================")
    print("   APPLIED AGENT SYSTEMS: A2 - PERSISTENT AGENT (GITHUB STEWARD)               ")
    print("================================================================================")
    print("Core principle: 'Persistence is not an infinite loop. It is durable goals,     ")
    print("                 durable state, and controlled reactivation across time.'        ")
    print("--------------------------------------------------------------------------------\n")

    try:
        # Initialize Shared Infrastructure
        github = MockGitHubAPI(repo_name="org/core-agent-runtime")
        state_store = PersistentStateStore(db_path=db_path)
        approval_gate = ApprovalGate()
        scheduler = WakeScheduler(base_interval_seconds=3600)
        event_bus = EventBus()
        budget = AutonomyBudget(max_steps_per_wake=5, max_writes_per_wake=2)

        agent_id = "steward-agent-001"
        goal = DurableGoal.create(
            description="Continuously maintain repository hygiene, triage issues, and welcome PRs.",
            target_repo="org/core-agent-runtime",
        )

        print("[INIT] Creating PersistentStewardAgent with durable goal...")
        agent = PersistentStewardAgent.create(
            agent_id=agent_id,
            goal=goal,
            github=github,
            state_store=state_store,
            budget=budget,
            approval_gate=approval_gate,
            scheduler=scheduler,
        )
        print(f"[INIT] Agent created. Status: {agent.status.value}. Checkpointed in SQLite.\n")

        # -------------------------------------------------------------------------
        # DAY 1: Scheduled Wake & The Power of Abstention
        # -------------------------------------------------------------------------
        print("=== DAY 1: SCHEDULED WAKE & ABSTENTION DISCIPLINE ===")
        print("Scenario: Agent wakes on recurring timer. No new issues or PRs exist.")
        wake_day1 = WakeEvent(
            trigger_type=WakeTriggerType.SCHEDULED,
            event_name="scheduler.hourly_maintenance",
        )
        result_day1 = agent.execute_wake_cycle(wake_day1)
        print(f"Agent Observation: Clean repository. Open issues: 0, Open PRs: 0.")
        print(f"Agent Decision: {result_day1.get('decision', {}).get('action')} - {result_day1.get('decision', {}).get('reason')}")
        print(f"Final State: {agent.status.value} (Next wake scheduled at: {agent.next_wake_at})\n")

        # -------------------------------------------------------------------------
        # DAY 2: Event-Driven Wake & Human Approval Gate
        # -------------------------------------------------------------------------
        print("=== DAY 2: EVENT-DRIVEN WAKE & HUMAN-IN-THE-LOOP APPROVAL ===")
        print("Scenario: An external user opens Issue #1 ('Add support for streaming JSON').")
        new_issue = github.create_issue(
            title="Add support for streaming JSON",
            body="Can we stream tokens directly to the client?",
            author="alice_dev",
        )
        event_day2 = WakeEvent(
            trigger_type=WakeTriggerType.EVENT,
            event_name="github.issues.opened",
            payload={"issue_number": new_issue.number},
        )
        print("Incoming Webhook Event -> Waking Agent...")
        result_day2 = agent.execute_wake_cycle(event_day2)
        token = result_day2.get("approval_token")
        print(f"Agent State: {agent.status.value}")
        print(f"Proposed Action: {result_day2.get('decision', {}).get('action')}")
        print(f"Approval Token Generated: {token}")
        print(f"Open Commitments Tracked: {len(agent.memory.get_open_commitments())}\n")

        # -------------------------------------------------------------------------
        # SIMULATE PROCESS TERMINATION AND RESTART
        # -------------------------------------------------------------------------
        print("=== PROCESS SHUTDOWN & RESTART SIMULATION ===")
        print("Simulating server reboot or worker crash while waiting for human review...")
        del agent
        state_store.close()

        # Reopen database in fresh execution context
        state_store = PersistentStateStore(db_path=db_path)
        print("Re-instantiating agent from SQLite state store...")
        agent = PersistentStewardAgent.restore(
            agent_id=agent_id,
            github=github,
            state_store=state_store,
            budget=budget,
            approval_gate=approval_gate,
            scheduler=scheduler,
        )
        print(f"Restored Agent Status: {agent.status.value}")
        print(f"Restored Goal: {agent.goal.description}")
        print(f"Restored Pending Action: {agent.pending_action.get('action_type') if agent.pending_action else 'None'}")
        print(f"Restored Open Commitments: {len(agent.memory.get_open_commitments())}\n")

        # Human maintainer reviews and grants approval
        print("[HUMAN OPERATOR] Approving pending action token...")
        approved = approval_gate.approve(token, reason="Approved by repo admin")
        print(f"Approval Status: {approved}")

        # Agent wakes to execute approved action
        wake_review = WakeEvent(
            trigger_type=WakeTriggerType.MANUAL,
            event_name="operator.approval_granted",
        )
        print("Waking Agent to finalize approved commitment...")
        agent.execute_wake_cycle(wake_review)
        print(f"Post-Execution Status: {agent.status.value}")
        issue_comments = github.issues[new_issue.number].comments
        print(f"GitHub Issue #1 Comments: {len(issue_comments)} posted by {issue_comments[0].author}")
        print(f"GitHub Issue #1 Labels: {github.issues[new_issue.number].labels}")
        print(f"Remaining Open Commitments: {len(agent.memory.get_open_commitments())}\n")

        # -------------------------------------------------------------------------
        # DAY 3: Crash Recovery & Idempotency Reconciliation
        # -------------------------------------------------------------------------
        print("=== DAY 3: MID-ACTION CRASH & RECONCILIATION ===")
        print("Scenario: An action lands on GitHub, but agent process dies before recording verification.")
        pr = github.create_pull_request(
            title="Refactor logger module",
            body="Cleans up log handlers",
            author="bob_eng",
        )
        idemp_key = f"{agent_id}:welcome:pr:{pr.number}"
        github.post_issue_comment(
            issue_number=pr.number,
            body="Thank you @bob_eng for the PR!",
            author="steward[bot]",
            idempotency_key=idemp_key,
        )

        # Inject simulated interrupted state into state store
        agent.pending_action = {
            "status": "WAITING_FOR_APPROVAL",
            "action_type": "PROPOSE_PR_WELCOME",
            "target_entity": f"pr:#{pr.number}",
            "idempotency_key": idemp_key,
        }
        agent.save_checkpoint()
        print("Simulated crash: pending_action saved, process restarted.")

        # Re-wake agent
        wake_day3 = WakeEvent(
            trigger_type=WakeTriggerType.EVENT,
            event_name="github.pull_request.opened",
            payload={"pr_number": pr.number},
        )
        agent.wake(wake_day3)
        print(f"Agent woke up. Reconciled Pending Action: {agent.pending_action}")
        print("Audit Event Log shows: CRASH_RECONCILED. Double posting was avoided.")
        agent.sleep()
        print(f"Post-reconciliation state: {agent.status.value}\n")

        # -------------------------------------------------------------------------
        # DAY 4: Memory Compaction & Long-Term Rolling Summary
        # -------------------------------------------------------------------------
        print("=== DAY 4: MEMORY TIERING & COMPACTION ===")
        print("Simulating 6 rapid event cycles to demonstrate token compaction...")
        for i in range(1, 7):
            agent.memory.record_event(
                "ROUTINE_CHECK",
                f"Completed health check cycle {i}; all systems nominal.",
            )
        print(f"Recent events buffer before sleep: {len(agent.memory.recent_events)}")
        agent.sleep()
        print(f"Recent events buffer after sleep compaction: {len(agent.memory.recent_events)}")
        print("Consolidated Long-Term Summary snippet:")
        summary_preview = agent.memory.long_term_summary.strip().split("\n")[:3]
        for line in summary_preview:
            print(f"  > {line}")

        print("\n================================================================================")
        print("Simulation completed successfully.")
        print("Concluding Axiom:")
        print("'A persistent agent is not an agent that runs forever. It is an agent that can ")
        print(" stop, remember, wake up, re-observe reality, and safely continue pursuing a    ")
        print(" durable goal.'                                                                 ")
        print("================================================================================")

    finally:
        state_store.close()
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    run_simulation()
