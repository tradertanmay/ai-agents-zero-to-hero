"""
Module 09: Multi-Agent Systems
Runnable Python Demonstration: Supervisor-Worker Orchestration with Review Loop

This script demonstrates multi-agent coordination, message passing envelopes,
isolated context windows, and review loops in pure standard Python 3.11+
(zero dependencies).
"""

from dataclasses import dataclass, field
import time
from typing import Any


# ============================================================================
# 1. Message Passing Envelopes & Types
# ============================================================================

@dataclass
class AgentMessage:
    sender: str
    recipient: str
    content: str
    status: str = "IN_PROGRESS"  # "IN_PROGRESS", "COMPLETED", "REJECTED"
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


# ============================================================================
# 2. Specialized Worker Agents (Isolated Contexts)
# ============================================================================

class ResearcherAgent:
    """Specialist responsible for fact retrieval and raw data extraction."""
    def __init__(self) -> None:
        self.name = "Researcher"
        self.system_prompt = "You are a Research Specialist. You extract raw verifiable facts from logs and databases."
        self.context: list[AgentMessage] = []

    def handle(self, message: AgentMessage) -> AgentMessage:
        self.context.append(message)
        print(f"  [{self.name}] Analyzing query: '{message.content}'")

        # Simulated factual extraction from infrastructure audit logs
        findings = (
            "AUDIT LOG EXTRACTION:\n"
            "- Target: DB-CLUSTER-PROD-01\n"
            "- Event: 45 repeated failed login attempts from IP 198.51.100.24\n"
            "- Timestamp: 2026-10-05 03:14:22 UTC\n"
            "- Action Taken: Automated firewall drop rule FW-882 applied at 03:15:00 UTC\n"
            "- Data Breach: None detected. 0 unauthorized queries executed."
        )

        reply = AgentMessage(
            sender=self.name,
            recipient=message.sender,
            content=findings,
            status="COMPLETED",
            metadata={"source": "audit_logs", "records_scanned": 45}
        )
        self.context.append(reply)
        return reply


class WriterAgent:
    """Specialist responsible for formatting clear executive summaries."""
    def __init__(self) -> None:
        self.name = "Writer"
        self.system_prompt = "You are an Executive Technical Writer. You synthesize technical data into concise briefings."
        self.context: list[AgentMessage] = []
        self.revision_count = 0

    def handle(self, message: AgentMessage) -> AgentMessage:
        self.context.append(message)
        self.revision_count += 1
        print(f"  [{self.name}] Drafting executive briefing (Iteration {self.revision_count})...")

        if self.revision_count == 1:
            # First draft contains a slight discrepancy (claims 100 attempts instead of 45)
            # to demonstrate the critic review loop catching errors
            draft = (
                "INCIDENT BRIEFING (DRAFT 1):\n"
                "On 2026-10-05, DB-CLUSTER-PROD-01 experienced an unauthorized brute-force incident\n"
                "consisting of approximately 100 failed login attempts from IP 198.51.100.24.\n"
                "Automated firewall rule FW-882 successfully blocked the attacker.\n"
                "Zero data leakage occurred."
            )
        else:
            # Revised draft accurately aligns with verified facts
            draft = (
                "INCIDENT BRIEFING (REVISED FINAL):\n"
                "On 2026-10-05 at 03:14:22 UTC, DB-CLUSTER-PROD-01 recorded 45 failed login attempts\n"
                "from IP 198.51.100.24. Automated firewall rule FW-882 engaged within 38 seconds.\n"
                "No unauthorized queries were executed and zero data breach occurred."
            )

        reply = AgentMessage(
            sender=self.name,
            recipient=message.sender,
            content=draft,
            status="COMPLETED",
            metadata={"draft_iteration": self.revision_count}
        )
        self.context.append(reply)
        return reply


class FactCheckerAgent:
    """Specialist responsible for adversarial critique and cross-referencing."""
    def __init__(self) -> None:
        self.name = "FactChecker"
        self.system_prompt = "You are a Critical Fact-Checker. You cross-reference claims against source records."
        self.context: list[AgentMessage] = []

    def verify(self, source_facts: str, draft: str) -> AgentMessage:
        print(f"  [{self.name}] Cross-referencing draft against source audit facts...")
        
        # Check for numeric mismatch in login attempts
        if "100 failed login attempts" in draft and "45 repeated failed login attempts" in source_facts:
            rejection_reason = (
                "FACT DISCREPANCY DETECTED:\n"
                "Draft claims '100 failed login attempts', but source audit log confirms exactly '45'.\n"
                "Revision required: Correct the attempt count before publication."
            )
            return AgentMessage(
                sender=self.name,
                recipient="Supervisor",
                content=rejection_reason,
                status="REJECTED"
            )

        # Everything matches
        approval = "VERIFICATION PASSED: All claims in the draft match source records with zero discrepancies."
        return AgentMessage(
            sender=self.name,
            recipient="Supervisor",
            content=approval,
            status="COMPLETED"
        )


# ============================================================================
# 3. Supervisor / Orchestrator
# ============================================================================

class SupervisorAgent:
    """
    Coordinates specialized worker agents.
    Decomposes the goal, routes tasks, reviews critiques, and arbitrates completion.
    """
    def __init__(self, max_turns: int = 8) -> None:
        self.name = "Supervisor"
        self.max_turns = max_turns
        self.researcher = ResearcherAgent()
        self.writer = WriterAgent()
        self.critic = FactCheckerAgent()
        self.message_history: list[AgentMessage] = []

    def log_message(self, msg: AgentMessage) -> None:
        self.message_history.append(msg)

    def run(self, user_goal: str) -> tuple[bool, str]:
        print(f"[{self.name}] Initiating multi-agent workflow for goal: '{user_goal}'")
        turns = 0

        # Phase 1: Research
        turns += 1
        print(f"\n[Turn {turns}] Supervisor -> Researcher")
        req_research = AgentMessage(sender=self.name, recipient="Researcher", content=user_goal)
        self.log_message(req_research)
        research_reply = self.researcher.handle(req_research)
        self.log_message(research_reply)
        source_data = research_reply.content

        # Phase 2: Drafting & Critique Loop
        draft_content = ""
        while turns < self.max_turns:
            turns += 1
            print(f"\n[Turn {turns}] Supervisor -> Writer")
            req_write = AgentMessage(
                sender=self.name,
                recipient="Writer",
                content=f"Draft briefing based on source findings:\n{source_data}\nPrevious feedback: {draft_content}"
            )
            self.log_message(req_write)
            write_reply = self.writer.handle(req_write)
            self.log_message(write_reply)
            draft_content = write_reply.content

            turns += 1
            print(f"\n[Turn {turns}] Supervisor -> FactChecker")
            check_reply = self.critic.verify(source_facts=source_data, draft=draft_content)
            self.log_message(check_reply)

            if check_reply.status == "COMPLETED":
                print(f"  [{self.name}] Critique approved! Delivering final artifact.")
                return True, draft_content
            else:
                print(f"  [{self.name}] Critique rejected draft: {check_reply.content.splitlines()[0]}")
                print(f"  [{self.name}] Ordering revision cycle...")

        return False, "Failed: Exceeded maximum multi-agent coordination turns without consensus."


# ============================================================================
# 4. Demonstration & Output
# ============================================================================

def main() -> None:
    print("=" * 65)
    print("DEMO: SUPERVISOR-WORKER MULTI-AGENT COORDINATION")
    print("=" * 65)

    user_goal = "Investigate DB-CLUSTER-PROD-01 brute force incident and publish verified executive report."
    supervisor = SupervisorAgent(max_turns=10)

    success, final_report = supervisor.run(user_goal)

    print("\n" + "=" * 65)
    print(f"ORCHESTRATION OUTCOME: Success={success}")
    print(f"Total Inter-Agent Messages Exchanged: {len(supervisor.message_history)}")
    print("=" * 65)
    print("\nFINAL DELIVERED ARTIFACT:")
    print("-" * 65)
    print(final_report)
    print("-" * 65)


if __name__ == "__main__":
    main()
