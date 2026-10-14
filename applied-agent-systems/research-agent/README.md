# A3 — Research Agent: Autonomous Multi-Source Deep Research

> **Core Principle**: *"Deep research is not a single search query passed to an LLM. It is an iterative loop of query decomposition, multi-source evidence retrieval, noise stripping, cross-verification, and citation-grounded synthesis."*

---

## Full Production Repository

This module serves as the architectural bridge between the first-principles concepts in **AI Agents: Zero → Hero** and the complete, deployable **Autonomous Deep Research Agent**.

> **Full Standalone Project**: **[github.com/tradertanmay/research-agent](https://github.com/tradertanmay/research-agent)**
>
> Features a 100% local-first runtime (Ollama) or cloud providers (Gemini, OpenAI, Groq, OpenRouter), live **arXiv + DuckDuckGo + Wikipedia** search, **local PDF/document upload**, async HTML boilerplate stripping, strict inline citation grounding (`[1]`, `[2]`), interactive follow-up Q&A, recursive deep-dive, and an executive web dashboard with real-time SSE streaming.

```bash
# Quick Start for the Full Production System:
git clone https://github.com/tradertanmay/research-agent.git
cd research-agent
./install.sh
./start.sh
```

---

## Overview

A common misconception is that a "Research Agent" is simply an LLM wired up to a web search tool. When given a complex technical question, a naive single-shot search agent:
1. Issues one overly broad search query.
2. Stuffs raw, noisy HTML snippets into the prompt window.
3. Hallucinates unverified claims or invents fake citation URLs.
4. Fails to notice when primary sources (e.g., peer-reviewed papers) contradict secondary blog posts.

**A3 — Research Agent** demonstrates how to engineer a rigorous, evidence-grounded research system by composing foundational primitives taught in Modules 01–13.

---

## How Zero → Hero Concepts Map to the Production Research Agent

| Zero → Hero Module | Concept Taught | Implementation in `tradertanmay/research-agent` |
| :--- | :--- | :--- |
| **[03 — Tools & Function Calling](../../03-tools-and-function-calling/README.md)** | Structured tool schemas & multi-source adapters | Specialized search clients in `agent/search/` (`arXiv`, `DuckDuckGo`, `Wikipedia`) and local PDF parsers in `agent/storage/`. |
| **[05 — State & Memory](../../05-state-and-memory/README.md)** | Durable storage & session history | Local research `vault/` persisting generated reports, uploaded documents, and follow-up Q&A sessions. |
| **[06 — Planning & Reasoning](../../06-planning-and-reasoning/README.md)** | Task decomposition & iterative refinement | `Planner` (`agent/core/`) breaks broad topics into targeted academic, web, and encyclopedic sub-queries, plus recursive deep-dives. |
| **[07 — Context Engineering](../../07-context-engineering/README.md)** | Signal-to-noise optimization & token hygiene | `Scraper` (`agent/scraper/`) strips ads, navbars, cookie banners, and HTML boilerplate before text enters the model context. |
| **[11 — Agent Evaluation](../../11-agent-evaluation/README.md)** | Multi-dimensional quality verification | Citation coverage checks, source diversity scoring, and automated test suites. |
| **[12 — Safety & Verification](../../12-agent-safety-and-verification/README.md)** | Preconditions, postconditions & role isolation | Strict inline citation binding (`[1]`, `[2]`) and guest role isolation (`403 Forbidden` on private vault/keys when shared). |

---

## Architecture & Directory Layout

In this repository (`ai-agents-zero-to-hero`), we provide the conceptual blueprint and a zero-dependency standard-library reference simulation:

```
applied-agent-systems/research-agent/
├── README.md               # Capstone overview & bridge to tradertanmay/research-agent
├── concepts.md             # Deep-dive: 6-stage research pipeline & citation grounding
├── example.py              # Standalone pure-Python reference simulation (zero dependencies)
└── exercise.md             # 4 engineering exercises (credibility, contradictions, gap loop)
```

In the standalone production repository ([`tradertanmay/research-agent`](https://github.com/tradertanmay/research-agent)):

```
research-agent/
├── install.sh / start.sh   # 1-Click installer and launcher
├── run.py                  # Unified CLI, Web & Diagnostic entrypoint
├── vault/                  # Local storage for reports, conversations, and PDF uploads
├── agent/
│   ├── core/               # Planner, Synthesizer & Master Research Agent
│   ├── llm/                # Ollama & OpenAI-compatible model providers
│   ├── search/             # DuckDuckGo, arXiv, Wikipedia search clients
│   ├── scraper/            # Async HTML crawler & boilerplate cleaner
│   ├── storage/            # Vault manager, PDF/document loader & exporter
│   └── web/                # FastAPI server, SSE streaming & executive Web UI
└── tests/                  # Automated unit & integration test suite
```

---

## How to Run

### 1. Run the Zero-Dependency Reference Simulation (In This Repo)
Demonstrates query decomposition, multi-source fan-out (`arXiv`, `Web`, `Wikipedia`, `Local PDF`), HTML noise stripping, deterministic citation registry binding, and post-synthesis citation verification using pure Python 3.11+ standard library:

```bash
python3 applied-agent-systems/research-agent/example.py
```

### 2. Run the Automated Verification Tests (In This Repo)
```bash
python3 -m unittest tests/test_research_agent.py
```

### 3. Run the Full Production Research Agent (Standalone Repo)
Clone and launch the complete local-first application with web UI and live search:

```bash
git clone https://github.com/tradertanmay/research-agent.git
cd research-agent
./install.sh
./start.sh
```

---

## Concluding Axiom

> **"An LLM generates plausible prose; a Research Agent constructs verifiable evidence. Without query planning, noise stripping, and strict citation binding, autonomous research is just confident hallucination."**
