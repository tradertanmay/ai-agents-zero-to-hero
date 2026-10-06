# Module 15: Self-Improving Agents (Concepts)

The culmination of autonomous agent systems centers on a fundamental question:

> **What changes when an agent is allowed to modify not just its task environment, but parts of the system that determine its own future behavior?**

Unconstrained "self-modifying" agents that rewrite their own codebase without governance inevitably degrade, overfit, or bypass safety guardrails. Genuine self-improvement requires controlled, evidence-based evolution: isolated candidates, multi-dimensional frozen benchmarks, holdout generalization, strict verifier boundaries, and mandatory human promotion gates.

---

## 1. Learning vs. Self-Modification: The Five Adaptation Surfaces

Self-improvement is not a single binary capability. Different adaptation surfaces have vastly different blast radii and risk profiles:

```
Learning from experience
          |
Change retrieved examples / memory
          |
      LOW RISK (Level 1)
          |
          v
Prompt adaptation
          |
Change instructions & constraints
          |
    MODERATE RISK (Level 2)
          |
          v
Tool adaptation
          |
Change tool schemas & descriptions
          |
    HIGHER RISK (Level 3)
          |
          v
Workflow / harness adaptation
          |
Change control logic & policies
          |
    HIGHER RISK (Level 4)
          |
          v
Code modification
          |
Change executable source code
          |
    HIGHEST RISK (Level 5)
```

### The 5 Surfaces Analyzed

| Surface | Mechanism | Failure Example | Mitigation & Verification |
| :--- | :--- | :--- | :--- |
| **1. Memory** | Add high-quality trajectories to dynamic few-shot library. | Agent repeatedly picks wrong tool for ambiguous queries. | Retrieve verified exemplar; lowest risk because code and instructions are unchanged. |
| **2. Prompt** | Refine system guidelines and constraints. | Agent guesses missing parameters instead of asking. | Add explicit precondition rules to candidate prompt; evaluate on prompt benchmarks. |
| **3. Tool Descriptions** | Clarify overlapping tool schemas and boundaries. | Agent calls `search_web()` for local documentation questions. | Re-write `search_docs()` schema boundary; evaluate on frozen tool-selection suite. |
| **4. Harness / Policy** | Adjust runtime retry rules, reconciliation, or rate limits. | Ambiguous write timeout causes duplicate action upon blind retry. | Require pre-retry reconciliation in candidate harness; test with simulated network faults. |
| **5. Code** | Mutate underlying executable Python code. | Naive full-file search causes context bloat and hallucinated edits. | Candidate Coding Agent applies AST symbol localization patch inside an isolated sandbox. |

---

## 2. The Controlled Self-Improvement Architecture

To prevent runaway degradation, self-improvement must follow an isolated candidate pipeline:

```
                 Production Baseline
                         v1.0
                          |
                    Failure Logs
                    (Development)
                          |
                          v
                Improvement Proposer
                          |
                          v
                  Candidate v1.1
                 (ISOLATED COPY)
                          |
            +-------------+-------------+
            |                           |
       Frozen Evals                Safety Evals
    (Regression Suite)         (Zero Invariant Escapes)
            |                           |
            +-------------+-------------+
                          |
                          v
                  Holdout Evaluation
                 (Unseen Generalization)
                          |
                          v
                  Regression Check
                          |
                Better AND No Harm?
                  /             \
                NO               YES
                |                 |
             Reject          Human Review
                                  |
                             Promote v1.1
                                  |
                          Keep v1.0 Available
                             for Rollback
```

---

## 3. The Prime Directive: The Subject Must Not Control the Evaluator

A catastrophic vulnerability in autonomous self-modification occurs when an agent attempts to pass evaluation by **modifying the tests, verifiers, or promotion rules**.

> **Governing Axiom**: The subject of evaluation must NOT control the evaluator.

Under this rule, candidate agents operating on the Code surface may mutate constrained implementation files (such as `agent.py`, `context_selector.py`, or `search.py`), but are strictly forbidden from modifying:
- `approval.py` (Human approval tokens and review gates)
- `safety.py` (Capability gates and blast radius limiters)
- `verifier.py` (Test runners and trace parsers)
- `evaluator.py` (Benchmark scoring harnesses)
- `promotion.py` (Multi-dimensional gate policies)
- `rollback.py` (Version restoration engines)
- `versions.py` (Version registry and audit trails)
- `evals/*.json` (Frozen regression and holdout datasets)

Any candidate patch touching a protected file is rejected with a security violation.

---

## 4. Multi-Dimensional Gates vs. Single Aggregate Scores

A common trap in AI evaluation is relying on a single aggregate benchmark score. Consider this scenario:

```text
Baseline v1.0:
  Task Success Rate:      82.0%
  Unsafe Action Rate:      0.0%
  Recovery Success:       91.0%

Candidate v1.1:
  Task Success Rate:      89.0%  (+7.0% improvement)
  Unsafe Action Rate:      2.0%  (Safety degradation!)
  Recovery Success:       95.0%

Verdict: REJECTED
```

Even though the candidate achieved higher overall task success, it introduced a 2.0% unsafe action rate. **In safety-critical systems, an improvement in capability never compensates for an increase in safety violations.**

### Promotion Gate Criteria
A candidate is eligible for promotion review if and only if:
1. `candidate.unsafe_action_rate == 0.0%` (Zero tolerance)
2. `candidate.invariant_escape_rate == 0.0%` (Zero tolerance)
3. `candidate.regressions_count == 0` (No existing baseline behavior broken)
4. `candidate.task_success >= baseline.task_success`
5. `candidate.holdout_success >= baseline.holdout_success`
6. Candidate passes all internal unit test suites cleanly.

---

## 5. Development Failures vs. Holdout Generalization

An agent that modifies itself based on its test suite can easily overfit:

$$\text{Improvement on Known Failures} \neq \text{General Improvement}$$

To prevent overfitting:
- **Development Cases (`development_cases.json`)**: Accessible to the `ImprovementProposer` to observe failure patterns.
- **Regression Cases (`regression_cases.json`)**: Frozen suite evaluated against both baseline and candidate to detect regressions.
- **Holdout Cases (`holdout_cases.json`)**: Strictly hidden from the proposer; evaluated only by the `PromotionGate` to verify generalization on unseen tasks.

---

## 6. Versioning and Rollback Governance

> **Axiom**: Self-improvement without versioning and rollback is mutation, not controlled evolution.

Every candidate release preserves an immutable audit record:
- `version_id`: Identifier (e.g. `v1.0`, `v1.1-candidate`, `v1.1`)
- `parent_version`: Ancestor lineage
- `surface`: Target adaptation surface (memory, prompt, tool, harness, code)
- `change_summary`: Exact rationale and unified diff
- `eval_results`: Multi-dimensional metrics
- `promotion_status`: `candidate`, `promoted`, `rejected`, or `rolled_back`
- `approved_by`: Identity of human operator
- `promoted_at`: Timestamp

If production latency, errors, or distribution drift emerge after deployment, the system can instantly execute `rollback_to_parent()`, restoring the proven baseline with zero downtime.

---

## 7. The Zero to Hero Curriculum Culmination

Across fifteen modules, we have traced the complete evolution of autonomous AI agents:

```text
01–03  Give an agent perception and action
04     Build and test it
05     Give it memory
06     Give it planning
07     Control its context
08     Control its runtime
09     Coordinate multiple agents
10     Survive failure
11     Measure behavior
12     Constrain and verify behavior
13     Operate reliably in production
14     Modify software safely
15     Modify its own future behavior under evaluation and governance
```

> **The Final Axiom**:
> **A system should earn the right to change itself through evidence, not confidence.**
