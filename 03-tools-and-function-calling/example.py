"""
Module 03: Tools and Function Calling
Runnable Python Demonstration: The Complete Tool Lifecycle

This script demonstrates how tool registries, JSON schemas, argument validation,
and runtime execution function in pure standard Python (zero dependencies).
"""

import inspect
import json
from dataclasses import dataclass
from typing import Any, Callable, get_type_hints


# ============================================================================
# 1. Automatic JSON Schema Generator (Pure Python Standard Library)
# ============================================================================

def python_type_to_json_type(py_type: Any) -> str:
    """Maps Python types to JSON Schema data types."""
    if py_type in (int, float):
        return "number"
    if py_type is str:
        return "string"
    if py_type is bool:
        return "boolean"
    if py_type in (list, set):
        return "array"
    if py_type in (dict, Any):
        return "object"
    return "string"


@dataclass
class Tool:
    """Encapsulates a callable Python function and its declarative schema."""
    name: str
    description: str
    func: Callable[..., Any]
    schema: dict[str, Any]

    @classmethod
    def from_function(cls, func: Callable[..., Any], description: str | None = None) -> "Tool":
        name = func.__name__
        doc = description or (inspect.getdoc(func) or f"Execute tool {name}").strip()
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)

        properties: dict[str, Any] = {}
        required: list[str] = []

        for param_name, param in sig.parameters.items():
            param_type = type_hints.get(param_name, str)
            json_type = python_type_to_json_type(param_type)
            properties[param_name] = {
                "type": json_type,
                "description": f"Parameter '{param_name}'",
            }
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": doc,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
        return cls(name=name, description=doc, func=func, schema=schema)


# ============================================================================
# 2. Tool Registry
# ============================================================================

class ToolRegistry:
    """Manages tool registration, schema exportation, and runtime execution."""
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, func: Callable[..., Any], description: str | None = None) -> Tool:
        tool = Tool.from_function(func, description)
        self._tools[tool.name] = tool
        return tool

    def get_schemas(self) -> list[dict[str, Any]]:
        """Returns all registered tool schemas formatted for LLM consumption."""
        return [tool.schema for tool in self._tools.values()]

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Validates and executes the tool in the Python runtime.
        Catches any execution exceptions so the agent doesn't crash.
        """
        if tool_name not in self._tools:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found. Available tools: {list(self._tools.keys())}"
            }

        tool = self._tools[tool_name]
        try:
            # Runtime validation: check required arguments
            sig = inspect.signature(tool.func)
            for param_name, param in sig.parameters.items():
                if param.default is inspect.Parameter.empty and param_name not in arguments:
                    return {
                        "success": False,
                        "error": f"Missing required parameter '{param_name}' for tool '{tool_name}'."
                    }

            # Runtime execution (The Python interpreter runs the code!)
            result = tool.func(**arguments)
            return {
                "success": True,
                "result": result
            }
        except TypeError as te:
            return {"success": False, "error": f"Type error during execution: {str(te)}"}
        except Exception as e:
            return {"success": False, "error": f"Runtime error in '{tool_name}': {str(e)}"}


# ============================================================================
# 3. Define Real / Mock Tools
# ============================================================================

def calculator(a: float, b: float, op: str) -> float:
    """
    Perform mathematical operations: add, subtract, multiply, or divide.
    """
    if op == "add":
        return a + b
    elif op == "subtract":
        return a - b
    elif op == "multiply":
        return a * b
    elif op == "divide":
        if b == 0:
            raise ValueError("Cannot divide by zero!")
        return a / b
    else:
        raise ValueError(f"Unknown operation '{op}'. Allowed: add, subtract, multiply, divide")


def get_weather_mock(location: str, unit: str = "celsius") -> dict[str, Any]:
    """
    Get current weather for a specified city or location.
    """
    mock_data = {
        "San Francisco": {"temp": 18, "condition": "Sunny", "humidity": "65%"},
        "Tokyo": {"temp": 24, "condition": "Rainy", "humidity": "80%"},
        "London": {"temp": 14, "condition": "Cloudy", "humidity": "72%"},
    }
    data = mock_data.get(location, {"temp": 20, "condition": "Clear", "humidity": "50%"})
    if unit == "fahrenheit":
        data = {**data, "temp": (data["temp"] * 9/5) + 32, "unit": "F"}
    else:
        data = {**data, "unit": "C"}
    return {"location": location, **data}


def search_documents_mock(query: str, limit: int = 3) -> list[str]:
    """
    Search the internal knowledge base for relevant documents.
    """
    knowledge = [
        "Company refund policy: full refunds are allowed within 30 days of purchase.",
        "Premium subscription includes 24/7 priority support and unlimited API calls.",
        "To reset your API key, visit the dashboard settings under Security.",
    ]
    matches = [doc for doc in knowledge if any(word in doc.lower() for word in query.lower().split())]
    return matches[:limit] or ["No matching documents found."]


# ============================================================================
# 4. Demonstrating the 8-Stage Tool Lifecycle
# ============================================================================

def main() -> None:
    print("=" * 70)
    print("DEMO: THE COMPLETE TOOL LIFECYCLE (Module 03)")
    print("=" * 70)

    # 1. Register Tools
    registry = ToolRegistry()
    registry.register(calculator)
    registry.register(get_weather_mock)
    registry.register(search_documents_mock)

    print("\n--- 1. Generated JSON Schemas (Passed to Model) ---")
    schemas = registry.get_schemas()
    print(json.dumps(schemas, indent=2))

    # 2. Simulated Model Emits a Valid Tool Call
    print("\n--- 2. Model Decision & Tool Call Emission ---")
    model_tool_call = {
        "name": "calculator",
        "args": {"a": 45.0, "b": 15.0, "op": "multiply"}
    }
    print(f"Model selected: {json.dumps(model_tool_call)}")

    # 3. Runtime Validates & Executes
    print("\n--- 3. Runtime Execution by Python ---")
    obs = registry.execute(model_tool_call["name"], model_tool_call["args"])
    print(f"Runtime Observation: {json.dumps(obs)}")

    # 4. Error Handling: Missing Argument
    print("\n--- 4. Error Handling: Missing Argument ---")
    bad_call = {"name": "calculator", "args": {"a": 10.0}}
    print(f"Model emitted invalid call: {json.dumps(bad_call)}")
    error_obs = registry.execute(bad_call["name"], bad_call["args"])
    print(f"Runtime Caught Error cleanly: {json.dumps(error_obs)}")

    # 5. Error Handling: Exception Inside Tool (Divide by Zero)
    print("\n--- 5. Error Handling: Exception Inside Tool ---")
    div_zero_call = {"name": "calculator", "args": {"a": 10.0, "b": 0.0, "op": "divide"}}
    print(f"Model emitted divide-by-zero: {json.dumps(div_zero_call)}")
    div_obs = registry.execute(div_zero_call["name"], div_zero_call["args"])
    print(f"Runtime Caught Exception cleanly: {json.dumps(div_obs)}")


if __name__ == "__main__":
    main()
