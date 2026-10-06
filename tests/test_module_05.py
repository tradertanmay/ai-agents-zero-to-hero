"""
Tests for Module 05: State and Memory
"""

import unittest
import os
import sys
import importlib.util

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

spec = importlib.util.spec_from_file_location("module_05_example", os.path.join(root_dir, "05-state-and-memory", "example.py"))
m05 = importlib.util.module_from_spec(spec)
sys.modules["module_05_example"] = m05
spec.loader.exec_module(m05)


class TestModule05(unittest.TestCase):
    def setUp(self):
        self.store = m05.PersistentMemoryStore(db_path=":memory:")
        self.registry = m05.ToolRegistry()
        self.registry.register(m05.get_item_price)
        self.agent = m05.StatefulAgent(memory_store=self.store, registry=self.registry)

    def tearDown(self):
        self.store.close()

    def test_working_state_initialization(self):
        ws = m05.WorkingState(task_id="t1", user_id="u1", goal="Test task")
        self.assertEqual(ws.task_id, "t1")
        self.assertEqual(ws.step, 0)
        self.assertFalse(ws.is_finished)
        self.assertIsInstance(ws.scratchpad, dict)

    def test_conversation_history_compaction(self):
        history = m05.ConversationHistory(max_uncompacted_turns=4)
        for i in range(6):
            history.add_message(m05.Message(role="user", content=f"Message {i}"))
        
        # After adding 6 messages with limit 4, compaction should have triggered
        self.assertTrue(len(history.messages) <= 4)
        # First message should be system summary
        self.assertEqual(history.messages[0].role, "system")
        self.assertIn("Historical Summary", history.messages[0].content)

    def test_persistent_memory_store_preferences(self):
        self.store.set_preference("user_1", "theme", "dark")
        self.store.set_preference("user_1", "currency", "GBP")
        self.store.set_preference("user_1", "nested_config", {"rate": 1.25})

        prefs = self.store.get_preferences("user_1")
        self.assertEqual(prefs["theme"], "dark")
        self.assertEqual(prefs["currency"], "GBP")
        self.assertEqual(prefs["nested_config"]["rate"], 1.25)

        # Update existing key
        self.store.set_preference("user_1", "theme", "light")
        updated_prefs = self.store.get_preferences("user_1")
        self.assertEqual(updated_prefs["theme"], "light")

    def test_persistent_memory_episodes(self):
        self.store.record_episode("s1", "u1", "Goal 1", "Answer 1")
        self.store.record_episode("s2", "u1", "Goal 2", "Answer 2")

        episodes = self.store.get_episodes("u1", limit=10)
        self.assertEqual(len(episodes), 2)
        # Check goals are recorded
        goals = [e["goal"] for e in episodes]
        self.assertIn("Goal 1", goals)
        self.assertIn("Goal 2", goals)

    def test_stateful_agent_multi_session_recall(self):
        # Session 1: establish preference
        ans1 = self.agent.run_session("sess_1", "alice", "My preferred currency is EUR.")
        self.assertIn("EUR", ans1)

        # Session 2: run task without re-stating currency
        ans2 = self.agent.run_session("sess_2", "alice", "Order 5 units of widget_a.")
        self.assertIn("EUR", ans2)
        self.assertIn("€62.50", ans2)


if __name__ == "__main__":
    unittest.main()
