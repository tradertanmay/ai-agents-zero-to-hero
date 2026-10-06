# Exercise 09: Implement Multi-Agent Consensus Voting and Veto Power

## Goal
Extend the `SupervisorAgent` from Module 09 by implementing an **M-of-N Consensus Voting Protocol** with a **Security Veto Gate** before an artifact is approved for production deployment.

---

## The Challenge

1. **Create Specialized Reviewer Agents**:
   Implement three distinct reviewer agents inheriting from a common base:
   - `SecurityReviewer`: Inspects code/plans for injection flaws and hardcoded secrets. Has **VETO** power.
   - `PerformanceReviewer`: Checks for unbounded queries and exponential loops.
   - `ComplianceReviewer`: Verifies GDPR and licensing compliance.

   Each reviewer returns an `AgentMessage` with:
   ```python
   status = "APPROVED" | "REJECTED"
   metadata = {"veto": True | False, "category": "security"}
   ```

2. **Implement Consensus Arbitration in Supervisor**:
   In `SupervisorAgent`:
   - Send the draft artifact to all 3 reviewers concurrently (or sequentially).
   - Collect their votes:
     - If ANY reviewer with `metadata["veto"] == True` votes `"REJECTED"`, the artifact is **IMMEDIATELY REJECTED** regardless of other votes.
     - Otherwise, require at least **2 out of 3 approvals** to declare consensus.

3. **Implement Deadlock Arbitration**:
   Track total revision rounds. If the team fails to achieve consensus after `max_revision_rounds = 2`, abort execution with a structured deadlock escalation report.

---

## Verification Check

Write a short verification test:
1. Submit a deployment plan that passes Compliance and Performance, but contains a hardcoded API secret.
2. Verify that `SecurityReviewer` issues a VETO and the Supervisor halts deployment despite 2 positive votes.
3. Submit a corrected plan; verify that all reviewers approve and the Supervisor issues a successful deployment verdict.
