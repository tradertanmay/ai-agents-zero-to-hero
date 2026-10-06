# Module 05: State and Memory

**Difficulty Level:** Level 2 — Builder 
**Status:** Ready

---

## What You Will Learn

1. The critical architectural differences between **Context**, **State**, **History**, and **Memory**.
2. How to manage short-term working state vs. persistent long-term storage across sessions.
3. Common misconceptions: Why calling every vector database "memory" leads to poor agent design.
4. Implementing episodic and semantic memory stores using pure standard Python (`sqlite3`).
5. Preventing context window explosion through sliding-window conversation compaction.

---

## The Multi-Tiered Memory Architecture

```mermaid
flowchart TD
    subgraph ExecutionMemory["Short-Term Execution Scope"]
        WS["Working State<br/>(Scratchpad, step count, variables)"]
        CH["Conversation History<br/>(Turns & messages)"]
        CH -->|Compacts Old Turns| Summary["Semantic Summary"]
    end

    subgraph PersistentMemory["Long-Term Persistent Scope (SQLite)"]
        EM["Entity / Semantic Memory<br/>(User preferences, facts)"]
        EP["Episodic Memory<br/>(Past session goals & answers)"]
    end

    PersistentMemory -->|Bootstrap State| WS
    Summary --> Context["Active Context Window"]
    WS --> Context
    Context --> Model["LLM Inference Turn"]

    style ExecutionMemory fill:#f8f9fa,stroke:#333,stroke-width:2px
    style PersistentMemory fill:#f8f9fa,stroke:#333,stroke-width:2px
    style WS fill:#ede7f6,stroke:#4527a0
    style CH fill:#e1f5fe,stroke:#0288d1
    style Summary fill:#e3f2fd,stroke:#1565c0
    style EM fill:#e8f5e9,stroke:#2e7d32
    style EP fill:#e8f5e9,stroke:#2e7d32
    style Context fill:#fff3e0,stroke:#e65100
    style Model fill:#f3e5f5,stroke:#7b1fa2
```

---

## Core Questions This Module Answers

- *Where should agent state live when an execution spans multiple asynchronous hours?*
- *How do you prevent memory retrieval from injecting stale or conflicting facts into the active context?*
- *When is a simple relational key-value store superior to an expensive vector database for agent state?*
- *How do agents compact 30-turn histories into small summaries without losing key variables?*

---

## Module Contents

- **[concepts.md](concepts.md)**: Theoretical breakdown of the 4 data layers, episodic/semantic/procedural memory, compaction, and failure modes.
- **[example.py](example.py)**: Runnable pure Python demonstration of working state, SQLite persistent memory, and sliding-window compaction.
- **[exercise.md](exercise.md)**: Extend the persistent store with Time-To-Live (TTL) expiration and GDPR user data deletion (`forget_user`).

---

## Quick Run

```bash
python3 05-state-and-memory/example.py
```
