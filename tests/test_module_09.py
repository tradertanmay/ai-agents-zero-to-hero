"""
Tests for Module 09: Multi-Agent Systems
"""

import unittest
import os
import sys
import importlib.util

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

spec = importlib.util.spec_from_file_location("module_09_example", os.path.join(root_dir, "09-multi-agent-systems", "example.py"))
m09 = importlib.util.module_from_spec(spec)
sys.modules["module_09_example"] = m09
spec.loader.exec_module(m09)


class TestModule09(unittest.TestCase):
    def test_agent_message_creation(self):
        msg = m09.AgentMessage(
            sender="Supervisor",
            recipient="Researcher",
            content="Fetch incident data",
            metadata={"priority": "high"}
        )
        self.assertEqual(msg.sender, "Supervisor")
        self.assertEqual(msg.recipient, "Researcher")
        self.assertEqual(msg.status, "IN_PROGRESS")
        self.assertTrue(msg.timestamp > 0)
        self.assertEqual(msg.metadata["priority"], "high")

    def test_researcher_agent(self):
        researcher = m09.ResearcherAgent()
        req = m09.AgentMessage(sender="Supervisor", recipient="Researcher", content="Scan logs")
        res = researcher.handle(req)

        self.assertEqual(res.status, "COMPLETED")
        self.assertEqual(res.recipient, "Supervisor")
        self.assertIn("DB-CLUSTER-PROD-01", res.content)
        self.assertEqual(len(researcher.context), 2)  # request + reply

    def test_writer_agent_revision_cycle(self):
        writer = m09.WriterAgent()
        
        # Iteration 1
        req1 = m09.AgentMessage(sender="Supervisor", recipient="Writer", content="Draft report")
        res1 = writer.handle(req1)
        self.assertEqual(writer.revision_count, 1)
        self.assertIn("DRAFT 1", res1.content)
        self.assertIn("100 failed login attempts", res1.content)

        # Iteration 2
        req2 = m09.AgentMessage(sender="Supervisor", recipient="Writer", content="Revise report")
        res2 = writer.handle(req2)
        self.assertEqual(writer.revision_count, 2)
        self.assertIn("REVISED FINAL", res2.content)
        self.assertIn("45 failed login attempts", res2.content)

    def test_fact_checker_rejection_and_approval(self):
        checker = m09.FactCheckerAgent()
        source = "45 repeated failed login attempts from IP 198.51.100.24"
        
        # Draft with mismatch
        bad_draft = "Approximately 100 failed login attempts occurred."
        critique_bad = checker.verify(source, bad_draft)
        self.assertEqual(critique_bad.status, "REJECTED")
        self.assertIn("FACT DISCREPANCY DETECTED", critique_bad.content)

        # Draft matching facts
        good_draft = "Exactly 45 repeated failed login attempts were recorded."
        critique_good = checker.verify(source, good_draft)
        self.assertEqual(critique_good.status, "COMPLETED")
        self.assertIn("VERIFICATION PASSED", critique_good.content)

    def test_supervisor_orchestration_end_to_end(self):
        supervisor = m09.SupervisorAgent(max_turns=10)
        success, final_report = supervisor.run("Investigate security incident")

        self.assertTrue(success)
        self.assertIn("REVISED FINAL", final_report)
        self.assertIn("45 failed login attempts", final_report)
        self.assertIn("FW-882", final_report)
        
        # Verify message history contains communications between all agents
        senders = {m.sender for m in supervisor.message_history}
        self.assertIn("Supervisor", senders)
        self.assertIn("Researcher", senders)
        self.assertIn("Writer", senders)
        self.assertIn("FactChecker", senders)

    def test_supervisor_turn_budget_ceiling(self):
        supervisor = m09.SupervisorAgent(max_turns=2)
        # Mock critic to always reject
        supervisor.critic.verify = lambda source_facts, draft: m09.AgentMessage(
            sender="FactChecker",
            recipient="Supervisor",
            content="Never approving this draft.",
            status="REJECTED"
        )
        success, report = supervisor.run("Goal that cannot reach consensus")
        self.assertFalse(success)
        self.assertIn("Exceeded maximum multi-agent coordination turns", report)


if __name__ == "__main__":
    unittest.main()
