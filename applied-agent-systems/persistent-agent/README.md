# A2 — Persistent Agent: GitHub Project Steward Agent

> **Core Principle**: *"Persistence is not an infinite loop. A persistent agent is a system with durable goals, durable state, and controlled reactivation across time."*

---

## Overview

Most AI agent tutorials implement persistence as an infinite `while True:` loop wrapped around `time.sleep()`. In real production systems, this pattern fails instantly: when processes restart, servers deploy, or pods are rescheduled, in-memory state is lost, context windows explode with accumulated history, and unmanaged agents burn API budgets performing repetitive busywork.

**A2 — Persistent Agent** presents an applied, production-grade architectural capstone: a **GitHub Project Steward Agent** designed to run over days, weeks, and months.

The agent demonstrates the vital distinction between:
- **Persistent Memory**: Information survives across sessions (databases, vector stores).
- **Persistent Agent**: Goals, state, unfinished work, and execution continue across process restarts and time.

---

## Key Capabilities

1. **12-State Explicit Lifecycle Machine**: Strict transition validation covering `CREATED`, `SCHEDULED`, `SLEEPING`, `WAKING`, `OBSERVING`, `DECIDING`, `WAITING_FOR_APPROVAL`, `ACTING`, `VERIFYING`, `COMPLETED`, `PAUSED`, `FAILED`.
2. **Durable Goals & Open Commitments**: Long-running objectives stored in SQLite that revalidate against environment reality on every wake cycle.
3. **Controlled Reactivation**: Sleep states with zero CPU consumption, triggered either by timers (scheduled wake with exponential backoff) or webhooks (event-driven wake).
4. **Crash Recovery & Reconciliation**: Detects in-flight actions from crashed previous processes and reconciles against remote GitHub reality using idempotency keys, avoiding double-mutations.
5. **The Power of Abstention**: First-class support for `ABSTAIN` decisions—when repository state is clean, the agent refrains from hallucinating busywork.
6. **Human Approval Gate**: Cryptographically unique approval tokens for external mutations, with SHA256 entity fingerprinting to prevent executing stale actions.
7. **Tiered Memory Compaction**: Rolling event buffers that automatically compress historical interactions into long-term summaries to eliminate token context explosion.
8. **Autonomy Budgets**: Operational boundaries that enforce step limits, tool limits, write limits, and failure tripwires.

---

## Architecture & Directory Layout

```
applied-agent-systems/persistent-agent/
├── README.md               # Capstone documentation and architectural overview
├── concepts.md             # In-depth engineering concepts and design patterns
├── exercise.md             # 4 hands-on reliability and resilience exercises
└── example.py              # Standalone, runnable minimal implementation

examples/persistent_agent/
├── __init__.py             # Public exports
├── lifecycle.py            # 12-state enum and state machine transition rules
├── goals.py                # DurableGoal and Commitment models
├── mock_github.py          # Stateful GitHub simulator with idempotency keys
├── memory.py               # Consolidated tiered memory and compaction logic
├── events.py               # WakeTriggerType, WakeEvent, and EventBus
├── scheduler.py            # WakeScheduler with exponential backoff
├── approval.py             # ApprovalGate with stale-action detection
├── state.py                # SQLite persistence (agents, audit log, commitments)
├── runtime.py              # AutonomyBudget and BudgetTracker
├── agent.py                # PersistentStewardAgent coordinator
└── main.py                 # Multi-day end-to-end simulation runner
```

---

## How to Run

### 1. Run the Multi-Day Simulation
Simulates Day 1 (Abstain), Day 2 (Issue opened, approval requested, process killed, process restored, approved, executed), Day 3 (Mid-action crash & reconciliation), and Day 4 (Memory compaction):

```bash
python3 examples/persistent_agent/main.py
```

### 2. Run the Minimal Standalone Example
```bash
python3 applied-agent-systems/persistent-agent/example.py
```

### 3. Run the Automated Test Suite
```bash
python3 -m unittest tests/test_persistent_agent.py
```

---

## Concluding Axiom

> **"A persistent agent is not an agent that runs forever. It is an agent that can stop, remember, wake up, re-observe reality, and safely continue pursuing a durable goal."**
