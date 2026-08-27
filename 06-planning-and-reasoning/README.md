# Module 06: Planning and Reasoning

**Difficulty Level:** Level 3 — Systems 
**Status:** Coming Soon

---

## What You Will Learn

1. The mechanics of structured reasoning paradigms: **ReAct** (Reason + Act), **Plan-and-Execute**, and **Tree-of-Thoughts**.
2. Dynamic task decomposition: Breaking high-level user goals into structured dependency graphs (DAGs).
3. The vital counter-intuitive truth: **More reasoning does not automatically produce a better agent** (and when deep reasoning degrades performance or multiplies costs).
4. Reflection and self-critique loops: Detecting plan deviation and replanning at runtime.

---

## Core Questions This Module Answers

- *When should an agent create a full upfront plan vs. acting reactively step-by-step?*
- *How does an agent recover when step 3 of a 10-step plan fails due to an unexpected environment state?*
- *How do reasoning models (like OpenAI o1/o3 or DeepSeek R1) change how we architect external planning loops?*

---

## Planned Example

`06-planning-and-reasoning/example.py` will demonstrate:
- A two-phase **Planner → Executor** agent architecture.
- Dynamic replanning triggered when a subtask execution yields an error.
- A benchmark comparison between standard single-step ReAct and upfront Plan-and-Solve on a multi-step constraint puzzle.

---

## Prerequisites

- Completed [04-build-your-first-agent](../04-build-your-first-agent/README.md).
- Familiarity with directed acyclic graphs (DAGs) and state transitions.
