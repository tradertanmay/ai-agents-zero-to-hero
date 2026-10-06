# Curriculum Roadmap

This roadmap tracks the development of **AI Agents: Zero → Hero**. The curriculum is organized across six phases spanning beginner foundations to cutting-edge research.

---

## Phases Overview

- **Phase 1 — Agent Fundamentals** (Level 1 — Beginner: Modules 00, 01, 02)
- **Phase 2 — Building Agents** (Level 2 — Builder: Modules 03, 04, 05)
- **Phase 3 — Agent Systems** (Level 3 — Systems: Modules 06, 07, 08, 09)
- **Phase 4 — Production Agents** (Level 4 — Production: Modules 10, 11, 12, 13)
- **Phase 5 — Applied & Domain Agents** (Level 5 — Research: Module 14)
- **Phase 6 — Self-Improving Agents** (Level 5 — Research: Module 15)

---

## Phase 1 — Agent Fundamentals (Level 1 — Beginner)

*Objective: Unpack what an agent is, dispel industry buzzwords, and understand the core execution loop.*

- [x] **00 — Introduction**
  - [x] Course philosophy & prerequisites
  - [x] Setting up zero-dependency environment
  - [x] How to use the repo & mental models
- [x] **01 — What Is an AI Agent?**
  - [x] LLM vs Chatbot vs Workflow vs Agent
  - [x] **What People Call an Agent — But Isn't Necessarily an Agent** (The 7-Stage Spectrum)
  - [x] The Agent Equation: $\text{Agent} = \text{Model} + \text{Control Loop} + \text{Environment}$
  - [x] Degrees of autonomy and environment feedback
- [x] **02 — The Agent Loop**
  - [x] The Observe → Decide → Act → Observe cycle
  - [x] Termination conditions and state updates
  - [x] Building a deterministic simulation loop from scratch

---

## Phase 2 — Building Agents (Level 2 — Builder)

*Objective: Connect models to tools, manage execution state, and assemble complete end-to-end agents.*

- [x] **03 — Tools and Function Calling**
  - [x] Full Tool Lifecycle (Definition → Selection → Argument Parsing → Runtime Execution → Observation Return)
  - [x] Why LLMs never execute code directly
  - [x] **MCP (Model Context Protocol) Deep Dive**: What is MCP? Is it an agent? MCP vs. Function Calling
  - [x] Building a pure Python ToolRegistry and JSON schema generator
- [x] **04 — Build Your First Agent**
  - [x] The "Aha!" moment: assembling Agent, Tool, Registry, State, and Loop
  - [x] Multi-step problem solving with mock and real LLM interfaces
  - [x] Clean architecture in ~140 lines of standard Python
  - [x] **Early Evaluation**: 10-case regression scorecard, structured failure log, and before/after comparison (stopping "vibes-based debugging" before touching memory)
- [x] **05 — State and Memory**
  - [x] Precise disambiguation: Context vs State vs Memory vs History
  - [x] Ephemeral execution state vs persistent long-term storage
  - [x] Short-term rolling windows, summarization, and external stores
  - [x] Working memory scratchpad, SQLite-backed entity persistence, and compaction

---

## Phase 3 — Agent Systems (Level 3 — Systems)

*Objective: Master agent orchestration, reasoning strategies, context window hygiene, and runtime harnesses.*

- [x] **06 — Planning and Reasoning**
  - [x] ReAct, Plan-and-Execute, task decomposition, and reflection
  - [x] Why "more reasoning" does not always yield better agents
  - [x] Dynamic replanning and failure recovery during execution plans
- [ ] **07 — Context Engineering**
  - [ ] Context window budget allocation and token economy
  - [ ] Context pollution, stale tool outputs, and noise reduction
  - [ ] Dynamic pruning, compression, and structured prompting
- [x] **08 — Agent Runtime and Harness**
  - [x] The Harness as the Operating System for the Model
  - [x] Execution budgets, step limits, timeouts, and retries
  - [x] Middleware, tool permission gates, and trajectory recording
- [ ] **09 — Multi-Agent Systems**
  - [ ] Supervisor-worker, handoffs, debates, and peer coordination
  - [ ] Shared state vs isolated messaging channels
  - [ ] When **NOT** to use multiple agents (and why a single agent + tools is often superior)

---

## Phase 4 — Production Agents (Level 4 — Production)

*Objective: Build resilient, observable, evaluatable, and safe agentic infrastructure for real-world deployments.*

- [ ] **10 — Agent Failures**
  - [ ] Taxonomy of failure modes: tool hallucination, loop lock, premature stop, state corruption
  - [ ] Root causes, symptoms, and mitigations
  - [ ] Defensive patterns and guardrail design
- [ ] **11 — Agent Evaluation**
  - [ ] *(Note: Evaluation begins early in Module 04 with deterministic 10-case scorecards; Module 11 deepens this into advanced production evaluation infrastructure)*
  - [ ] Why evaluating final answers alone is insufficient
  - [ ] Trajectory quality, tool efficiency, step cost, and multi-turn reliability metrics
  - [ ] Deterministic unit tests, benchmark suites, and LLM-as-a-judge
  - [ ] Measuring and benchmarking multi-agent systems
- [ ] **12 — Agent Safety and Verification**
  - [ ] Permission boundaries, sandboxing, and human-in-the-loop gates
  - [ ] Verifying outcomes vs trusting model assertions
  - [ ] Checkpoints, rollbacks, and reversible action patterns
- [ ] **13 — Production Agents**
  - [ ] Production architecture: tracing, telemetry, rate limiting, and persistence
  - [ ] Async runtimes, distributed state, and background task resumption
  - [ ] Cost controls, authentication, and SLA enforcement

---

## Phase 5 — Applied & Domain Agents (Level 5 — Research)

*Objective: Deep-dive into sophisticated real-world agent specializations.*

- [ ] **14 — Coding Agents**
  - [ ] Codebase exploration, file search, and indexing
  - [ ] Patch generation, test execution, and iterative debugging loops
  - [ ] Deterministic linting and verification harnesses

---

## Phase 6 — Self-Improving Agents (Level 5 — Research)

*Objective: Explore autonomous learning, meta-reasoning, and self-evolution.*

- [ ] **15 — Self-Improving Agents**
  - [ ] Trajectory reflection, failure memory, and dynamic few-shot learning
  - [ ] Prompt and tool self-adaptation
  - [ ] Safety risks and drift in autonomous self-modifying systems

---

## Runnable Examples Roadmap

- [x] `examples/minimal_agent/`: Fully functional, modular agent with mock/pluggable LLM adapters.
- [ ] `examples/coding_assistant/`: Minimal repo-investigation and patch-applying agent.
- [ ] `examples/research_assistant/`: Multi-source search, citation, and synthesis agent.
- [ ] `examples/eval_harness/`: Trajectory evaluation and benchmark suite.
