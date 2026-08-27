"""
Tool Registry & Tool Definitions
examples/minimal_agent/tools.py
"""

import inspect
from dataclasses import dataclass
from typing import Any, Callable, get_type_hints


def _py_type_to_json(t: Any) -> str:
    if t in (int, float):
        return "number"
    if t is str:
        return "string"
    if t is bool:
        return "boolean"
    if t in (list, set):
        return "array"
    return "object"


@dataclass
class Tool:
    name: str
    description: str
    func: Callable[..., Any]
    schema: dict[str, Any]

    @classmethod
    def from_callable(cls, func: Callable[..., Any], description: str | None = None) -> "Tool":
        name = func.__name__
        doc = description or (inspect.getdoc(func) or f"Execute tool {name}").strip()
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)

        props: dict[str, Any] = {}
        required: list[str] = []

        for p_name, param in sig.parameters.items():
            p_type = type_hints.get(p_name, str)
            props[p_name] = {
                "type": _py_type_to_json(p_type),
                "description": f"Argument '{p_name}'",
            }
            if param.default is inspect.Parameter.empty:
                required.append(p_name)

        schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": doc,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
            },
        }
        return cls(name=name, description=doc, func=func, schema=schema)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, func: Callable[..., Any], description: str | None = None) -> None:
        tool = Tool.from_callable(func, description)
        self._tools[tool.name] = tool

    def get_schemas(self) -> list[dict[str, Any]]:
        return [tool.schema for tool in self._tools.values()]

    def execute(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        if tool_name not in self._tools:
            return {"status": "error", "error": f"Tool '{tool_name}' not registered."}
        try:
            res = self._tools[tool_name].func(**args)
            return {"status": "success", "result": res}
        except Exception as e:
            return {"status": "error", "error": f"Tool '{tool_name}' failed: {str(e)}"}


# ============================================================================
# Standard Demo Tools
# ============================================================================

def get_weather(city: str) -> dict[str, Any]:
    """
    Look up the current live weather report for a specified city.
    """
    database = {
        "seattle": {"temp_c": 14, "condition": "Rainy", "humidity": "88%"},
        "austin": {"temp_c": 31, "condition": "Sunny", "humidity": "42%"},
        "tokyo": {"temp_c": 22, "condition": "Cloudy", "humidity": "60%"},
    }
    return database.get(city.lower(), {"temp_c": 20, "condition": "Clear", "humidity": "50%"})


def calculate_discount(base_amount: float, vip_status: bool = False) -> float:
    """
    Calculate dollar discount based on purchase amount and VIP membership.
    """
    rate = 0.25 if vip_status else 0.10
    return base_amount * rate
