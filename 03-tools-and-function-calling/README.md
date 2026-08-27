# Module 03: Tools and Function Calling

**Difficulty Level:** Level 2 — Builder 
**Focus:** The complete tool lifecycle, schema generation, argument validation, and execution boundaries.

---

## What You Will Learn

1. Why tools exist and how they extend a model's capabilities beyond static weights.
2. The **Complete 8-Stage Tool Lifecycle**:
   - Tool Definition $\to$ Schema Presentation $\to$ Model Selection $\to$ Argument Generation $\to$ Runtime Validation $\to$ Runtime Execution $\to$ Observation Formatting $\to$ Context Feedback.
3. The fundamental architectural truth: **The LLM never runs your code. The runtime does.**
4. How to generate JSON schemas automatically from Python type hints and docstrings using only the standard library.
5. How to build a clean `ToolRegistry` with validation and error-handling guardrails.

---

## The Complete Tool Lifecycle

```mermaid
sequenceDiagram
    autonumber
    participant Developer as Developer
    participant Registry as ToolRegistry (Runtime)
    participant Model as LLM (Inference)
    participant Runtime as Agent Runtime
    participant ToolFunc as Python Tool Function

    Developer->>Registry: Register tool: calculator(a, b, op)
    Registry->>Registry: Generate JSON Schema
    Runtime->>Model: Send System Prompt + Available Tool Schemas
    Note over Model: Model decides it needs calculation
    Model-->>Runtime: Emit Tool Call JSON: {"name": "calculator", "args": {"a": 10, "b": 5, "op": "multiply"}}
    Runtime->>Registry: Validate args against schema
    alt Arguments Valid
        Runtime->>ToolFunc: Execute calculator(a=10, b=5, op="multiply")
        ToolFunc-->>Runtime: Return 50
        Runtime->>Model: Feed Observation: {"tool": "calculator", "output": 50}
    else Validation Fails
        Runtime->>Model: Feed Error Observation: "Invalid argument type for 'a'"
    end
```

---

## Module Contents

- **[concepts.md](concepts.md)**: In-depth technical breakdown of schemas, function calling mechanics, and security boundaries.
- **[example.py](example.py)**: Pure Python `ToolRegistry` with automatic JSON schema generation, argument validation, and mock tool executions.
- **[exercise.md](exercise.md)**: Implement a sandboxed string-manipulation tool with schema validation.

---

## Quick Run

```bash
python 03-tools-and-function-calling/example.py
```
