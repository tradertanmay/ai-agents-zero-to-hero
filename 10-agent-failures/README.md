# Module 10: Agent Failures

**Difficulty Level:** Level 4 — Production 
**Status:** Coming Soon

---

## What You Will Learn

1. A comprehensive taxonomy of real-world agent failure modes:
   - **Tool Selection Failure**: Calling the wrong tool or fabricating non-existent tools.
   - **Argument Hallucination**: Passing invalid types or invalid parameter keys.
   - **Loop Lock / Oscillations**: Repeatedly executing the same failing action.
   - **Context Pollution**: Model losing track of original goal due to noisy tool logs.
   - **Premature Termination**: Declaring task completion without verifying intermediate outcomes.
   - **State Corruption**: Overwriting or dropping critical operational state.
2. For each failure mode: **Symptom**, **Underlying Cause**, **Real Example**, **Automated Detection**, and **Mitigation Strategy**.
3. Defensive engineering patterns to make agents resilient in production.

---

## Core Questions This Module Answers

- *How do you automatically detect when an agent is caught in a repetitive action loop?*
- *What guardrails prevent an agent from returning an unverified hallucinated answer when a tool fails?*
- *How do you write self-healing prompts that recover from schema mismatches at runtime?*

---

## Planned Example

`10-agent-failures/example.py` will demonstrate:
- A simulator that injects 5 common failure modes (schema errors, missing tools, loop locks, noisy logs).
- Active runtime defenses (circuit breakers, schema recovery prompts, and verification tripwires).

---

## Prerequisites

- Completed [08-agent-runtime-and-harness](../08-agent-runtime-and-harness/README.md).
