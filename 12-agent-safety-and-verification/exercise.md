# Exercise: Hardening Blast-Radius & Compensation Controls

## Objective
Extend the Reddit Comment Agent's safety architecture to support **`edit_comment`** with strict capability gating, precondition invariants, postcondition verification, and automated compensation.

---

## Scenario
A production incident revealed that when our agent attempted to fix a typo in a previously submitted comment, the agent model hallucinated permission, bypassed the approval gate, and accidentally overwrote the entire technical solution with an empty string.

Your task is to implement the **Principle of Least Privilege** and **Postcondition Verification** for editing comments.

---

## Requirements

### 1. Capability Separation & Invariants
- Define a new `EDIT_COMMENT` capability in `Capability`.
- Agents must **not** have `EDIT_COMMENT` by default.
- Invariant 1: No comment edit may occur without an approval token explicitly bound to:
  $$\text{post\_id} \quad + \quad \text{comment\_id} \quad + \quad \text{hash}(\text{new\_comment\_body})$$
- Invariant 2 (Edit Window): Comments older than 15 minutes cannot be edited (must require senior human elevation).
- Invariant 3 (Author Match): The agent may only edit comments authored by itself (`u/HeroAgentBot`).

### 2. Precondition Verification
In `PreconditionVerifier.verify()`:
- Check that the target post and comment still exist remotely.
- Verify that `comment["author"] == "u/HeroAgentBot"`.
- Verify that `time.time() - comment["created_utc"] <= 900.0` (15 minutes).
- Verify that the cryptographic token is valid and unconsumed.

### 3. Postcondition Verification
In `PostconditionVerifier.verify()`:
- After `edit_comment()` executes, re-read the remote comment from Reddit.
- Confirm `found_comment["body"].strip() == proposed_new_body.strip()`.

### 4. Compensation Workflow
If the remote edit fails or postcondition verification detects that the comment became corrupted:
- Execute a compensating action: revert the comment body back to the original approved version stored in SQLite persistent state.
- Log the compensation event as `COMPENSATED_REVERTED` in state.

---

## Verification Test Checklist

Write tests in your scratch environment to verify the following adversarial cases:
1. [ ] Model attempts to edit without `EDIT_COMMENT` capability -> **BLOCKED**.
2. [ ] Model attempts to edit someone else's comment -> **BLOCKED**.
3. [ ] Model attempts to edit after 15-minute window expires -> **BLOCKED**.
4. [ ] Model submits tampered edit text differing from the approved edit token -> **BLOCKED**.
5. [ ] Legitimate edit succeeds and postcondition verifier confirms remote text update -> **PASSED**.
6. [ ] Invariant Violation Escape Rate across your test suite must be **0.0%**.
