# Module 09: Multi-Agent Systems

**Difficulty Level:** Level 3 — Systems 
**Status:** Coming Soon

---

## What You Will Learn

1. The primary multi-agent topologies: **Supervisor-Worker**, **Sequential Handoffs**, **Hierarchical Teams**, and **Debate/Consensus**.
2. Shared state architecture vs. isolated message-passing channels between agents.
3. **When NOT to use multiple agents**: Why 80% of multi-agent use cases are better and more reliably solved by a single well-instructed agent with tools.
4. Coordination protocols, agent contracts, and termination arbitration.

---

## Core Questions This Module Answers

- *How do you pass control and context cleanly between specialized agents without losing operational state?*
- *What causes multi-agent deadlocks or infinite chatter loops, and how do you prevent them?*
- *When does adding a second agent increase error rates instead of accuracy?*

---

## Planned Example

`09-multi-agent-systems/example.py` will demonstrate:
- A clean Supervisor-Worker pattern coordinating a "Researcher Agent" and an "Editor Agent".
- Explicit handoff tokens and message passing without framework bloat.
- A side-by-side evaluation comparing the multi-agent system against a single agent equipped with research tools.

---

## Prerequisites

- Completed [04-build-your-first-agent](../04-build-your-first-agent/README.md) and [08-agent-runtime-and-harness](../08-agent-runtime-and-harness/README.md).
