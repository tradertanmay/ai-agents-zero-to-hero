"""
Agent State Representation
examples/minimal_agent/state.py
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    role: str # "system", "user", "assistant", or "tool"
    content: Any
    name: str | None = None
    tool_call: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.name:
            d["name"] = self.name
        if self.tool_call:
            d["tool_call"] = self.tool_call
        return d


@dataclass
class AgentState:
    goal: str
    messages: list[Message] = field(default_factory=list)
    step: int = 0
    is_finished: bool = False
    final_answer: str | None = None

    def get_context_messages(self) -> list[dict[str, Any]]:
        """Returns message list formatted for model consumption."""
        return [m.to_dict() for m in self.messages]
