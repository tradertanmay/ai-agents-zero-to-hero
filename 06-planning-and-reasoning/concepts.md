# Concepts: Planning, Reasoning, and Replanning

In simple environments, an agent can act reactively: observe the world, choose a tool, and repeat. But for non-trivial, multi-stage goals—such as diagnosing a distributed database outage or refactoring a code repository—purely reactive agents frequently get lost, repeat redundant steps, or fail to foresee obvious blockers.

To solve complex tasks, agents use **structured reasoning and planning**.

---

## 1. The Planning Spectrum

Agent planning exists on a spectrum from instantaneous reaction to deliberative graph search:

```mermaid
flowchart LR
    P1["1. Direct Action<br/>(No scratchpad)"] --> P2["2. ReAct<br/>(Think, then Act)"]
    P2 --> P3["3. Plan-and-Execute<br/>(Upfront plan, then run)"]
    P3 --> P4["4. Dynamic Replanning<br/>(Plan, run, adapt on failure)"]
    P4 --> P5["5. Tree-of-Thoughts / Search<br/>(Explore branches)"]

    style P1 fill:#f5f5f5,stroke:#9e9e9e
    style P2 fill:#e1f5fe,stroke:#0288d1
    style P3 fill:#fff3e0,stroke:#e65100
    style P4 fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style P5 fill:#ede7f6,stroke:#4527a0
```

### Paradigm A: Pure Reactive (No Explicit Reasoning)
- **Mechanism**: The model immediately maps state directly to an action without an intermediate scratchpad.
- **Flaw**: Highly prone to short-sighted blunders and greedy choices that lead to dead ends.

### Paradigm B: ReAct (Reason + Act)
- **Mechanism**: At every turn, the agent generates an explicit natural-language **Thought** before generating the **Action** (Tool Call).
- **Formula**: $\text{Observation} \to \text{Thought} \to \text{Action} \to \text{Observation}$.
- **Benefit**: Forces the model to synthesize intermediate observations and articulate a rationale before acting.

### Paradigm C: Plan-and-Execute (Upfront Decomposition)
- **Mechanism**: 
  1. A **Planner** breaks down a high-level goal into an explicit ordered list of subtasks (a DAG: Directed Acyclic Graph).
  2. An **Executor** executes the subtasks sequentially.
- **Benefit**: Long-horizon vision; prevents premature termination or skipping required preparatory steps.

### Paradigm D: Dynamic Replanning (Adaptive Execution)
- **Mechanism**: Plan upfront, but monitor runtime observations. When an execution fails or returns unexpected data, a **Replanner** alters the remaining subtasks dynamically.
- **Benefit**: Combines the strategic horizon of planning with the resilience of reactive systems.

---

## 2. ReAct vs. Plan-and-Execute Architecture

```mermaid
flowchart TD
    subgraph ReActLoop["ReAct Architecture (Step-by-Step)"]
        R_Obs["Observation"] --> R_Think["Thought (Internal Reasoning)"]
        R_Think --> R_Act["Action (Tool Execution)"]
        R_Act --> R_Obs
    end

    subgraph PlanExecLoop["Plan-and-Execute with Replanning"]
        Goal["User Goal"] --> Planner["Planner: Generate Step List [1..N]"]
        Planner --> Exec["Executor: Run Step k"]
        Exec --> Check{"Step k Succeeded?"}
        Check -->|Yes| Next{"More Steps?"}
        Next -->|Yes| Exec
        Next -->|No| Done["Goal Complete"]
        Check -->|No| Replanner["Replanner: Inspect Error & Re-Plan"]
        Replanner --> Exec
    end

    style ReActLoop fill:#f8f9fa,stroke:#333,stroke-width:1px
    style PlanExecLoop fill:#f8f9fa,stroke:#333,stroke-width:2px
    style Planner fill:#e3f2fd,stroke:#1565c0
    style Exec fill:#fff3e0,stroke:#e65100
    style Replanner fill:#fbe9e7,stroke:#d84315
    style Done fill:#c8e6c9,stroke:#2e7d32
```

---

## 3. The Counter-Intuitive Truth: When Planning Degrades Performance

A common beginner mistake is assuming:
$$\text{More Planning} = \text{Better Agent}$$

In practice, excessive or rigid planning often makes agent systems **slower, more expensive, and more brittle**:

| Scenario | Pure ReAct | Rigid Plan-and-Execute | Winner | Why |
| :--- | :--- | :--- | :--- | :--- |
| **Simple 1-2 Step Query** | 1 prompt call | 2 prompt calls (Planner + Executor) | **ReAct** | Planning adds 2x latency and cost with zero quality benefit. |
| **High Environment Uncertainty** | Adapts after every tool output | Plan becomes invalid on step 2; gets stuck | **Dynamic Replanning** | Rigid plans assume a static world that rarely exists in real systems. |
| **Complex 8-Step Refactor** | Forgets initial goal around step 5 | Maintains global checklist across turns | **Plan-and-Execute** | Prevents context drift and ensures all requirements are met. |

### The Three Costs of Planning
1. **Latency Overhead**: Generating an upfront plan requires a full model inference pass before any real tool is invoked.
2. **Context Window Inflation**: Long task checklists and step histories consume significant context tokens.
3. **Plan Hallucination**: Models frequently generate plans based on assumptions about files or APIs that do not exist, and then blindly attempt to follow them.

---

## 4. The Anatomy of Dynamic Replanning

When an unexpected event occurs during execution (e.g. an API returns `404 Not Found` or a server port is already bound), a production agent does not crash. It triggers **reconciliation**:

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Planner as Planner Module
    participant Executor as Execution Runtime
    participant Env as Environment

    User->>Planner: "Deploy app to staging and verify health"
    Planner->>Executor: Initial Plan: [1. Pull repo, 2. Deploy app, 3. Health check]
    
    Executor->>Env: Step 1: pull_repo() -> OK
    Executor->>Env: Step 2: deploy_app(port=8080)
    Env-->>Executor: Error: "Port 8080 already in use by PID 1420"
    
    Note over Executor,Planner: Failure detected! Triggering Replanner...
    
    Executor->>Planner: Replan Request(Error: Port 8080 in use, Done: [Step 1])
    Planner-->>Executor: Revised Plan: [Step 2a: kill_process(1420), Step 2b: deploy_app(port=8080), Step 3: Health check]
    
    Executor->>Env: Step 2a: kill_process(1420) -> Process terminated
    Executor->>Env: Step 2b: deploy_app(port=8080) -> Deployed OK
    Executor->>Env: Step 3: health_check() -> 200 OK
    Executor-->>User: "Deployment successful! App is healthy on port 8080."
```

---

## 5. Reasoning Models vs. External Planning Runtimes

With the emergence of models with internal reasoning tokens (e.g. OpenAI o1/o3, DeepSeek R1), where does external planning belong?

- **Internal Model Reasoning (Chain of Thought)**:
  - Best for: Pure mathematical reasoning, algorithmic logic, and code synthesis within a single turn.
  - Limitation: Cannot pause mid-thought to execute a bash tool, check a database, and resume thinking with fresh data.
- **External Agent Planning (Orchestrator)**:
  - Best for: Environment interaction, tool call coordination, error recovery, and tasks that span minutes or hours.
  - Conclusion: **They are complementary.** An external agent loop coordinates the macroscopic plan, while reasoning models handle tough microscopic decisions at each step.

---

## 6. Common Failure Modes in Planning

1. **The Sunk-Cost Loop**:
   - The agent stubbornly retries a failing step using identical arguments because the plan told it to execute that step.
   - *Defense*: Track consecutive tool failures. If a step fails twice, trigger replanning or human escalation.
2. **Premature Completion ("Declaration of Victory")**:
   - The model claims the overall goal is accomplished while only completing step 1 of 4.
   - *Defense*: The runtime verifies that all required subtasks in the plan are marked complete before accepting a termination action.
3. **Plan Bloat**:
   - The planner generates an impractical 25-step plan for a trivial 2-step task.
   - *Defense*: Constrain plan length in the prompt schema (e.g. `max_plan_steps: 6`).

---

## 7. Where It Appears in Real Systems

| Planning Concept | In Our Scratch Implementation | In Industry |
| :--- | :--- | :--- |
| **ReAct Loop** | `Thought:` before `tool_call` | LangChain `create_react_agent` |
| **Plan-and-Execute** | `Planner` + `Executor` classes | Plan-and-Solve Prompting, BabyAGI |
| **Replanning** | `replan()` on error observation | Devin / Claude Code repair loops |
| **Task Graph** | List of `TaskStep` dataclasses | LangGraph StateGraph, CrewAI Flows |
