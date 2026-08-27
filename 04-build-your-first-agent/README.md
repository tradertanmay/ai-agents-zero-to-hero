# Module 04: Build Your First Agent

**Difficulty Level:** Level 2 — Builder 
**Focus:** Assembling Model, Tools, Registry, State, and Control Loop into your first complete, working AI agent from scratch.

---

## What You Will Learn

1. The "Aha!" moment: Seeing all the independent building blocks connect into a unified, functioning agent.
2. How to build a complete agent in ~120 lines of standard Python with zero dependencies.
3. How `AgentState`, `ToolRegistry`, and `AgentLoop` coordinate to solve multi-step problems.
4. How an agent dynamically decomposes a goal into consecutive tool executions, records observations, and synthesizes a verified final answer.

---

## The Complete Architecture

```mermaid
flowchart TD
    User([" User Goal"]) --> Runtime["Agent Runtime"]
    
    subgraph ExecutionCycle["The Agent Loop"]
        Runtime -->|1. Build Context| LLM["LLM Decision Engine"]
        LLM -->|2. Emit Decision / Tool Call| Runtime
        
        Runtime --> IsTerminal{"Is Terminal / Finish?"}
        IsTerminal -->|Yes| Output([" Final Answer to User"])
        
        IsTerminal -->|No| ToolRegistry["Tool Registry"]
        ToolRegistry -->|3. Run Function| Tool["Execute Python Tool"]
        Tool -->|4. Return Result| ToolRegistry
        ToolRegistry -->|5. Observation| State["Agent State (History & Context)"]
        State -->|6. Next Turn| Runtime
    end

    style User fill:#e3f2fd,stroke:#1565c0
    style Runtime fill:#fff3e0,stroke:#e65100,stroke-width:2px
    style LLM fill:#f3e5f5,stroke:#7b1fa2
    style ToolRegistry fill:#e8f5e9,stroke:#2e7d32
    style Tool fill:#e8f5e9,stroke:#2e7d32
    style State fill:#ede7f6,stroke:#4527a0
    style Output fill:#c8e6c9,stroke:#2e7d32
```

---

## Module Contents

- **[concepts.md](concepts.md)**: Architectural breakdown of how each component interfaces with the others.
- **[example.py](example.py)**: Complete, standalone, runnable agent resolving a multi-step query using mock and rule-based LLM decision engines.
- **[exercise.md](exercise.md)**: Extend the agent with a new tool and multi-step reasoning capability.

---

## Quick Run

```bash
python 04-build-your-first-agent/example.py
```
