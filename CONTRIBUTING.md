# Contributing to AI Agents: Zero → Hero

Thank you for your interest in contributing to **AI Agents: Zero → Hero**! 

The mission of this repository is to teach developers and technical professionals **what AI agents actually are**, starting from absolute fundamentals and mechanics before introducing frameworks.

---

## Guiding Principles

1. **First Principles First**: Understand the underlying mechanics before using frameworks. If a concept can be taught with 30 lines of standard Python, do not introduce a 50,000-line library.
2. **Zero Mandatory Dependencies**: All foundational modules (00 through 08) and core tests must run using standard library Python 3.11+ without installing external packages or requiring API keys.
3. **The Model is Not the Agent**: Maintain crystal-clear architectural boundaries:
   $$\text{Agent} = \text{Model} + \text{Control Loop} + \text{Environment}$$
4. **Clarity Over Cleverness**: Code must be readable, well-commented, and heavily focused on the specific concept being taught.
5. **No AI-Generated Fluff**: Keep explanations concise, visual, and backed by runnable code.

---

## Pedagogical Template (The 7-Part Pattern)

When writing or updating conceptual documentation (`concepts.md` or major README sections), follow this 7-part structure:

1. **What is it?** — Plain-language, unambiguous definition.
2. **Why does it exist?** — The problem it solves and what happens if you don't have it.
3. **How does it work?** — Architectural explanation and execution flow.
4. **Minimal example** — Small, runnable snippet + Mermaid diagram.
5. **Common misconception** — What people get wrong (e.g., confusing context with memory).
6. **Failure mode** — How this component breaks in practice.
7. **Where it appears in real systems** — Practical context (e.g., how frameworks structure this).

---

## Standard Module Structure

Every module in the repository follows this directory layout:

```text
XX-module-name/
├── README.md # Module overview, learning goals, and mental model
├── concepts.md # In-depth architectural concepts using the 7-part pattern
├── example.py # Standalone, runnable Python script with zero dependencies
└── exercise.md # Hands-on challenge for the learner with verification steps
```

---

## Testing Guidelines

All code contributions must include tests or verify against existing tests using Python's built-in `unittest` runner:

```bash
python -m unittest discover -s tests -v
```

Before submitting a PR:
1. Ensure all `example.py` files execute independently:
   ```bash
   python 01-what-is-an-agent/example.py
   python 02-agent-loop/example.py
   python 03-tools-and-function-calling/example.py
   python 04-build-your-first-agent/example.py
   python 08-agent-runtime-and-harness/example.py
   python examples/minimal_agent/main.py
   ```
2. Verify all tests pass with zero external dependencies.
3. Check all markdown links and Mermaid diagrams.

---

## Submitting Questions and Ideas

Have a question or a topic you'd like explained?
- Check [QUESTIONS.md](QUESTIONS.md) to see community topics.
- Open a GitHub Issue using the **Question / Topic Request** template.
