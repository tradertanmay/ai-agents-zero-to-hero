# Exercise 01: Classifying Agentic Systems

## Goal
Test your ability to differentiate between LLMs, Chatbots, Workflows, and Agents in real-world engineering scenarios.

---

## Challenge: Scenario Classification

Review the following 4 engineering scenarios and determine which paradigm each represents:
- **(A) Stateless LLM**
- **(B) Chatbot**
- **(C) Deterministic Workflow**
- **(D) AI Agent**

---

### Scenario 1: The Automated Customer Support Classifier
A customer submits a ticket. A Python script calls `gpt-4o-mini` with a classification prompt to label the ticket as `billing`, `tech_support`, or `sales`. The script immediately routes the ticket to the corresponding Zendesk queue.
- **Your Classification:** _____________
- **Why:** ___________________________

---

### Scenario 2: The Database Debugger
A developer asks a system to resolve a slow database query. The system runs `EXPLAIN ANALYZE`, inspects missing indices, creates a temporary test index in a sandbox, re-runs the benchmark, evaluates if latency dropped, and iterates until latency is under 50ms before writing a migration script.
- **Your Classification:** _____________
- **Why:** ___________________________

---

### Scenario 3: The Document Summarizer
A user pastes a 20-page PDF into a web UI and clicks "Summarize". The backend splits the document into chunks, embeds them, retrieves top chunks, and prompts an LLM once to generate a summary.
- **Your Classification:** _____________
- **Why:** ___________________________

---

### Scenario 4: The Interactive CLI Assistant
A developer interacts with a terminal app that maintains a history of user messages and LLM responses, allowing the user to converse back and forth, but the app does not run any shell commands or read files directly.
- **Your Classification:** _____________
- **Why:** ___________________________

---

## Yes Solution & Verification

<details>
<summary>Click to reveal answers</summary>

1. **Scenario 1 is a Deterministic Workflow / Router (C/Level 3)**: The LLM acts as a single-step classifier; the routing logic is fixed deterministic code.
2. **Scenario 2 is an AI Agent (D/Level 5)**: It executes closed-loop Observe $\to$ Decide $\to$ Act $\to$ Observe cycles, inspects runtime benchmark feedback, and dynamically self-corrects until a goal is achieved.
3. **Scenario 3 is a Deterministic Workflow / Pipeline (C)**: It is a standard RAG pipeline with a predetermined sequence of steps.
4. **Scenario 4 is a Chatbot (B)**: It maintains conversation context across turns, but does not interact with the external environment or execute actions.

</details>
