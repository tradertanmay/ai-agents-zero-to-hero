# A3 — Research Agent: Hands-On Engineering Exercises

These exercises challenge you to extend the Research Agent reference pipeline with source credibility weighting, claim-level verification, recursive gap-analysis, and guest privacy isolation as implemented in the full production repository ([`tradertanmay/research-agent`](https://github.com/tradertanmay/research-agent)).

---

## Exercise 1: Source Credibility Tiering & Contradiction Detection

### Context
When gathering evidence from heterogeneous sources (`arXiv` preprints, `local_pdf` specifications, `wikipedia`, and general `web` posts), sources often disagree on numerical benchmarks or architectural claims. A rigorous research agent must not treat a random blog post as equal to a peer-reviewed benchmark or an internal hardware specification.

### Requirements
1. Extend `SourceRecord` in `example.py` with a deterministic `credibility_weight: float` based on `source_modality`:
   - `local_pdf`: `1.0` (authoritative internal specification)
   - `arxiv`: `0.9` (peer-reviewed / primary scientific preprint)
   - `wikipedia`: `0.75` (curated baseline taxonomy)
   - `web`: `0.6` (general industry blog / secondary source)
2. Implement a `ContradictionDetector` that flags when two sources report conflicting metrics for the same entity, and explicitly surfaces both claims in the report while ranking the higher-credibility source first.

### Acceptance Criteria
- Every registered `SourceRecord` carries a deterministic `credibility_weight`.
- Conflicting numerical claims across modalities are explicitly noted in a `Contradictions & Caveats` section rather than silently dropped.

---

## Exercise 2: Quantitative Claim Citation Enforcement

### Context
Even when a report contains valid `[1]` and `[2]` citations overall, an LLM might slip an uncited quantitative claim (e.g., *"Throughput increases by 4.5x under FP8 quantization."*) into a paragraph without attaching a `[N]` marker.

### Requirements
1. Enhance `CitationVerifier` to split the synthesized report into individual sentences.
2. Flag any sentence containing a numerical metric (`%`, `x` speedup, `GB`, `ms`, `FLOPs`) that does not contain at least one valid `[N]` citation marker in the same sentence.
3. Add `uncited_quantitative_sentences: list[str]` to `CitationAuditResult` and fail the audit (`is_valid = False`) if the list is non-empty.

### Acceptance Criteria
- Sentences with numbers/percentages and a valid `[N]` marker pass.
- Any sentence making a quantitative claim without an inline `[N]` marker causes `audit.is_valid` to return `False` and lists the offending sentence.

---

## Exercise 3: Bounded Recursive Deep-Dive Loop

### Context
Initial search queries often uncover new technical terms or unanswered bottlenecks that require a second hop of investigation. However, an unbounded recursive research loop can run forever.

### Requirements
1. Add a `run_recursive_deep_dive(question: str, gap_questions: list[str], max_depth: int = 2)` method to `DeepResearchAgent`.
2. For each gap question up to `max_depth`:
   - Call `planner.plan_deep_dive(question, gap)` to generate follow-up sub-queries.
   - Retrieve, clean, and register new sources into the **existing** `CitationRegistry` (preserving existing `[1]..[4]` IDs and assigning `[5]`, `[6]`, etc. to new sources).
   - Append a `## Deep-Dive Addendum` section to the report and re-run `CitationVerifier`.

### Acceptance Criteria
- Existing citation numbers (`[1]..[4]`) remain immutable when new deep-dive sources (`[5]+`) are appended.
- If `depth > max_depth`, the agent stops recursing and returns the consolidated report.

---

## Exercise 4: Host vs. Guest Capability Isolation

### Context
In the full [`tradertanmay/research-agent`](https://github.com/tradertanmay/research-agent) system, users can share their running research dashboard over a local network or Cloudflare Tunnel (`./start.sh share`). Remote visitors must be able to run new research queries, but must be strictly blocked from viewing the host's personal research vault or reading/modifying API keys.

### Requirements
1. Implement a `RequestContext(client_ip: str)` and `AccessControlGate`.
2. Classify requests from `127.0.0.1` or `::1` as `HOST`, and all other IP addresses as `GUEST`.
3. Enforce the following access matrix:
   - `POST /api/research` -> Allowed for both `HOST` and `GUEST` (logs inquiry with timestamp and IP to `user_queries.md`).
   - `GET /api/vault/history` -> Returns saved reports for `HOST`; returns empty list `[]` for `GUEST`.
   - `POST /api/settings/keys` -> Allowed for `HOST`; raises `PermissionError("403 Forbidden: Guest role cannot access API keys")` for `GUEST`.

### Acceptance Criteria
- Localhost callers can read history and update keys.
- Remote guest callers can run research queries (which are audited), see a clean empty vault history, and receive a deterministic `403 Forbidden` when attempting to read or write settings keys.
