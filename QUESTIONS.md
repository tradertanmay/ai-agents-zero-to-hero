# Community Questions & Discussion Topics

> **Have a question about AI agents that you want covered?**
>
> This curriculum is living and continuously evolves based on what developers find confusing or want to explore deeper.
> 
> [Submit a Question / Topic Request via GitHub Issues](../../issues/new?template=question.md)

---

## Categorized Questions Index

Below are questions submitted by learners and addressed across our curriculum modules:

### Fundamentals & Taxonomy
- **Q**: *What people call an agent — but isn't necessarily an agent? (Chatbot vs RAG vs Workflow vs Agent)*
  - Addressed in [01-what-is-an-agent](01-what-is-an-agent/concepts.md).
- **Q**: *Is ChatGPT with web browsing an agent or a chatbot?*
  - Addressed in [01-what-is-an-agent](01-what-is-an-agent/README.md).
- **Q**: *What actually stops an agent from looping forever if it doesn't solve a task?*
  - Addressed in [02-agent-loop](02-agent-loop/README.md) and [08-agent-runtime-and-harness](08-agent-runtime-and-harness/README.md).
- **Q**: *What is the difference between a Prompt, Context, State, History, and Memory?*
  - Addressed in [00-introduction](00-introduction/concepts.md) and [05-state-and-memory](05-state-and-memory/README.md).

### Tools, Function Calling & MCP
- **Q**: *Does the LLM run Python code when it calls a tool?*
  - Addressed in [03-tools-and-function-calling](03-tools-and-function-calling/README.md).
- **Q**: *What is MCP (Model Context Protocol)? Is MCP an agent? Is MCP a tool? Why does an agent need MCP?*
  - Addressed in [03-tools-and-function-calling](03-tools-and-function-calling/concepts.md).
- **Q**: *What is the difference between Function Calling and MCP?*
  - Addressed in [03-tools-and-function-calling](03-tools-and-function-calling/concepts.md).
- **Q**: *How does the runtime handle tools that return large payloads or errors?*
  - Addressed in [03-tools-and-function-calling](03-tools-and-function-calling/concepts.md) and [08-agent-runtime-and-harness](08-agent-runtime-and-harness/README.md).

### Memory & State
- **Q**: *When should I use a vector database vs. a relational database for agent memory?*
  - Planned in [05-state-and-memory](05-state-and-memory/README.md).
- **Q**: *How do we prevent an agent's memory from poisoning its future decisions?*
  - Planned in [05-state-and-memory](05-state-and-memory/README.md) and [10-agent-failures](10-agent-failures/README.md).

### Planning & Reasoning
- **Q**: *Does chain-of-thought always make an agent smarter, or can it degrade performance?*
  - Planned in [06-planning-and-reasoning](06-planning-and-reasoning/README.md).
- **Q**: *How do agents recover when an initial step in a 10-step plan fails?*
  - Planned in [06-planning-and-reasoning](06-planning-and-reasoning/README.md).

### Context Engineering
- **Q**: *How do you keep agent context from filling up during long multi-step workflows?*
  - Planned in [07-context-engineering](07-context-engineering/README.md).

### Agent Runtime & Harness
- **Q**: *What is the difference between the Model and the Agent Harness?*
  - Addressed in [08-agent-runtime-and-harness](08-agent-runtime-and-harness/README.md).
- **Q**: *How do step limits and execution budgets protect production systems?*
  - Addressed in [08-agent-runtime-and-harness](08-agent-runtime-and-harness/concepts.md).

### Multi-Agent Systems
- **Q**: *When should I use multiple agents instead of a single agent with multiple tools?*
  - Planned in [09-multi-agent-systems](09-multi-agent-systems/README.md).
- **Q**: *How do agents coordinate shared state without overwriting each other?*
  - Planned in [09-multi-agent-systems](09-multi-agent-systems/README.md).

### Failures & Debugging
- **Q**: *Why do agents get stuck in repetitive action loops, and how do we detect them?*
  - Planned in [10-agent-failures](10-agent-failures/README.md).

### Evaluation
- **Q**: *Why is evaluating the final output not enough for agent benchmarking?*
  - Planned in [11-agent-evaluation](11-agent-evaluation/README.md).

### Safety & Verification
- **Q**: *How do we ensure an agent doesn't execute destructive shell commands or API calls?*
  - Planned in [12-agent-safety-and-verification](12-agent-safety-and-verification/README.md).

### Production Agents
- **Q**: *How do you handle agent state persistence and human-in-the-loop approvals in production?*
  - Planned in [13-production-agents](13-production-agents/README.md).

### Advanced & Research
- **Q**: *How do coding agents like Claude Code or SWE-bench solvers verify their patches?*
  - Planned in [14-coding-agents](14-coding-agents/README.md).
- **Q**: *Can agents safely update their own prompt instructions or tool registry over time?*
  - Planned in [15-self-improving-agents](15-self-improving-agents/README.md).
