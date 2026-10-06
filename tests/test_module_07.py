"""
Tests for Module 07: Context Engineering
"""

import unittest
import os
import sys
import importlib.util

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

spec = importlib.util.spec_from_file_location("module_07_example", os.path.join(root_dir, "07-context-engineering", "example.py"))
m07 = importlib.util.module_from_spec(spec)
sys.modules["module_07_example"] = m07
spec.loader.exec_module(m07)


class TestModule07(unittest.TestCase):
    def setUp(self):
        self.budget = m07.ContextBudget(
            max_total_tokens=500,
            system_prompt_max=100,
            active_state_max=100,
            tool_schemas_max=100,
            history_turns_max=150,
            observation_max=100,
        )

    def test_token_estimator(self):
        self.assertEqual(m07.TokenEstimator.count(""), 0)
        self.assertEqual(m07.TokenEstimator.count("test"), 1)
        self.assertEqual(m07.TokenEstimator.count("12345678"), 2)
        
        msgs = [{"role": "user", "content": "Hello world"}]
        est = m07.TokenEstimator.count_messages(msgs)
        self.assertTrue(est > 5)

    def test_head_tail_truncate(self):
        long_text = "\n".join(f"Line {i}" for i in range(1, 51))
        truncated = m07.ObservationPruner.head_tail_truncate(long_text, max_lines=10)
        lines = truncated.splitlines()
        
        self.assertEqual(len(lines), 11)  # 5 head + 1 omitted notice + 5 tail
        self.assertIn("Line 1", lines[0])
        self.assertIn("Line 5", lines[4])
        self.assertIn("lines omitted", lines[5])
        self.assertIn("Line 50", lines[-1])

    def test_extract_error_signals(self):
        log = (
            "Line 1: Normal info\n"
            "Line 2: Normal info\n"
            "Line 3: ERROR: Database timeout\n"
            "Line 4: Normal info\n"
            "Line 5: Normal info"
        )
        distilled = m07.ObservationPruner.extract_error_signals(log, context_lines=1)
        self.assertIn("Database timeout", distilled)
        self.assertIn("Line 3:", distilled)
        self.assertIn("Line 2:", distilled)  # context line
        self.assertIn("Line 4:", distilled)  # context line

    def test_project_json(self):
        raw = {"id": "123", "status": "active", "debug_logs": ["a", "b"], "internal_token": "secret"}
        projected = m07.ObservationPruner.project_json(raw, allowed_keys={"id", "status"})
        self.assertEqual(projected, {"id": "123", "status": "active"})
        self.assertNotIn("internal_token", projected)

    def test_context_assembler_budget_and_anchors(self):
        assembler = m07.ContextAssembler(self.budget)
        assembler.set_system_prompt("You are a helpful agent.")
        assembler.set_task("Complete deployment", {"step": 1})
        assembler.set_tools([{"name": "deploy", "parameters": {}}])
        
        # Add a massive log observation
        massive_log = "\n".join(f"Log row {i}: all systems normal" for i in range(200))
        massive_log += "\nLog row 201: FATAL: Disk full"
        massive_log += "\n" + "\n".join(f"Log row {i}: recovery attempted" for i in range(202, 300))
        
        assembler.add_tool_observation("check_logs", massive_log, prune=True)
        messages, breakdown = assembler.assemble()

        # Check anchors
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("helpful agent", messages[0]["content"])
        self.assertEqual(messages[1]["role"], "system")
        self.assertIn("ACTIVE GOAL: Complete deployment", messages[1]["content"])
        
        # Total tokens should remain well under or near budget
        self.assertTrue(breakdown["total_tokens"] <= self.budget.max_total_tokens)
        self.assertIn("FATAL: Disk full", messages[-1]["content"])

    def test_sliding_window_history_eviction(self):
        assembler = m07.ContextAssembler(self.budget)
        assembler.set_system_prompt("System rules")
        assembler.set_task("Goal", {})
        
        # Add 10 turns that would exceed the 150 token history limit
        for i in range(10):
            assembler.add_turn("user", f"Turn number {i}: long verbose conversational filler text {i}")
            
        messages, breakdown = assembler.assemble()
        
        # System prompt and goal anchors are preserved
        self.assertEqual(messages[0]["content"], "System rules")
        # History tokens must not exceed budget
        self.assertTrue(breakdown["history_turns"] <= self.budget.history_turns_max)
        # Most recent turn should be present
        self.assertIn("Turn number 9", messages[-1]["content"])


if __name__ == "__main__":
    unittest.main()
