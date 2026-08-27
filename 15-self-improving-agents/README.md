# Module 15: Self-Improving and Self-Evolving Agents

**Difficulty Level:** Level 5 — Research 
**Status:** Coming Soon

---

## What You Will Learn

1. The mechanics of autonomous self-improvement: Learning from past trajectories, meta-prompting, and automated tool creation.
2. Trajectory reflection and error memory: How an agent critiques its past mistakes and dynamically updates few-shot guidance.
3. Tool evolution (Voyager / Cradle pattern): Allowing an agent to write, verify, and store new tools in its own tool catalog.
4. The critical hazards of self-evolution: Distribution drift, catastrophic forgetting, runaway prompts, and safety degradation.

---

## Core Questions This Module Answers

- *How can an agent discover a novel skill and register it as a permanent reusable tool?*
- *How do we ensure that an agent modifying its own system prompt or instructions doesn't remove safety guardrails?*
- *What is the boundary between dynamic in-context learning and weights fine-tuning in modern agent research?*

---

## Planned Example

`15-self-improving-agents/example.py` will demonstrate:
- An agent that attempts a task, fails, reflects on why it failed, creates a new helper tool in Python, tests the tool in a sandbox, and successfully accomplishes the task on retry.
- Persistent skill library storage and reuse in subsequent runs.

---

## Prerequisites

- Completed [12-agent-safety-and-verification](../12-agent-safety-and-verification/README.md) and [14-coding-agents](../14-coding-agents/README.md).
