# Module 11: Agent Evaluation

**Difficulty Level:** Level 4 — Production 
**Status:** Coming Soon

---

## What You Will Learn

1. Why evaluating an agent by only checking its final answer is dangerous and insufficient.
2. The core dimensions of agent evaluation:
   - **Task Success Rate**: Did the agent achieve the objective?
   - **Trajectory Quality**: Did the agent take reasonable, safe, and necessary steps?
   - **Tool Accuracy**: Were tool arguments well-formed and efficient?
   - **Step & Token Efficiency**: How many turns and tokens were consumed?
   - **Cost & Latency**: Economic and temporal feasibility.
3. Building deterministic unit tests, mock environment benchmarks, and LLM-as-a-Judge evaluators.

---

## Core Questions This Module Answers

- *How do you benchmark an agent non-deterministically without running up huge API bills?*
- *How do you write unit tests for an agent system that can take multiple valid paths to a solution?*
- *How do industry benchmarks like SWE-bench, GAIA, and WebArena evaluate agent performance?*

---

## Planned Example

`11-agent-evaluation/example.py` will demonstrate:
- An automated trajectory evaluation harness.
- Grading agent runs on both **Outcome** (was the correct result produced?) and **Trajectory Efficiency** (did it take redundant steps?).
- Generating an evaluation scorecard with latency, cost, and step metrics.

---

## Prerequisites

- Completed [08-agent-runtime-and-harness](../08-agent-runtime-and-harness/README.md).
