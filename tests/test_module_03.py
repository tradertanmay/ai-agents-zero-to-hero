"""
Tests for Module 03: Tools and Function Calling
"""

import unittest
import os
import sys
import importlib.util

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

spec = importlib.util.spec_from_file_location("module_03_example", os.path.join(root_dir, "03-tools-and-function-calling", "example.py"))
m03 = importlib.util.module_from_spec(spec)
sys.modules["module_03_example"] = m03
spec.loader.exec_module(m03)


class TestModule03(unittest.TestCase):
    def setUp(self):
        self.registry = m03.ToolRegistry()
        self.registry.register(m03.calculator)
        self.registry.register(m03.get_weather_mock)

    def test_schema_generation(self):
        schemas = self.registry.get_schemas()
        self.assertEqual(len(schemas), 2)
        calc_schema = next(s for s in schemas if s["function"]["name"] == "calculator")
        props = calc_schema["function"]["parameters"]["properties"]
        self.assertIn("a", props)
        self.assertIn("b", props)
        self.assertIn("op", props)
        self.assertEqual(props["a"]["type"], "number")

    def test_valid_tool_execution(self):
        res = self.registry.execute("calculator", {"a": 20.0, "b": 4.0, "op": "divide"})
        self.assertTrue(res["success"])
        self.assertEqual(res["result"], 5.0)

    def test_missing_argument_validation(self):
        res = self.registry.execute("calculator", {"a": 20.0})
        self.assertFalse(res["success"])
        self.assertIn("missing required parameter", res["error"].lower())

    def test_unhandled_exception_trapping(self):
        res = self.registry.execute("calculator", {"a": 20.0, "b": 0.0, "op": "divide"})
        self.assertFalse(res["success"])
        self.assertIn("cannot divide by zero", res["error"].lower())

    def test_unregistered_tool_execution(self):
        res = self.registry.execute("unknown_tool", {})
        self.assertFalse(res["success"])
        self.assertIn("not found", res["error"].lower())


if __name__ == "__main__":
    unittest.main()
