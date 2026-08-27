"""
Agent Coordinator
examples/minimal_agent/agent.py
"""

from typing import Any

try:
    from .state import AgentState, Message
    from .tools import ToolRegistry
    from .llm import BaseLLM, MockLLM
    from .runtime import AgentRuntime
except ImportError:
    from state import AgentState, Message # type: ignore
    from tools import ToolRegistry # type: ignore
    from llm import BaseLLM, MockLLM # type: ignore
    from runtime import AgentRuntime # type: ignore


class Agent:
    """
    A minimal, modular agent coordinating Model, Tools, State, and Runtime.
    """
    def __init__(
        self,
        llm: BaseLLM | None = None,
        registry: ToolRegistry | None = None,
        runtime: AgentRuntime | None = None
    ) -> None:
        self.llm = llm or MockLLM()
        self.registry = registry or ToolRegistry()
        self.runtime = runtime or AgentRuntime(max_steps=5)

    def run(self, goal: str) -> str:
        """Execute a goal to completion."""
        state = AgentState(goal=goal)
        state.messages.append(Message(role="user", content=goal))
        return self.runtime.execute_loop(state, self.llm, self.registry)
