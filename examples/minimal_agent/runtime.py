"""
Agent Runtime & Control Loop
examples/minimal_agent/runtime.py
"""

from dataclasses import dataclass, field
import time
from typing import Any

try:
    from .state import AgentState, Message
    from .tools import ToolRegistry
    from .llm import BaseLLM
except ImportError:
    from state import AgentState, Message # type: ignore
    from tools import ToolRegistry # type: ignore
    from llm import BaseLLM # type: ignore


@dataclass
class StepLog:
    step: int
    decision_type: str
    tool_name: str | None
    tool_args: dict[str, Any] | None
    tool_result: dict[str, Any] | None
    duration_ms: float


class AgentRuntime:
    """
    Supervises step budgets, tool dispatches, state updates, and trajectory logging.
    """
    def __init__(self, max_steps: int = 5, timeout_seconds: float = 10.0) -> None:
        self.max_steps = max_steps
        self.timeout_seconds = timeout_seconds
        self.trajectory: list[StepLog] = []

    def execute_loop(self, state: AgentState, llm: BaseLLM, registry: ToolRegistry) -> str:
        start_time = time.perf_counter()

        while not state.is_finished and state.step < self.max_steps:
            # Timeout check
            if time.perf_counter() - start_time >= self.timeout_seconds:
                state.is_finished = True
                state.final_answer = "Aborted: Execution timeout reached."
                break

            state.step += 1
            step_start = time.perf_counter()

            # 1. Ask model for decision
            response = llm.generate_decision(
                state.get_context_messages(),
                registry.get_schemas()
            )

            # 2. Check if model signaled completion
            if response.action_type == "finish":
                state.is_finished = True
                state.final_answer = response.content or "Completed."
                duration_ms = (time.perf_counter() - step_start) * 1000
                self._record(state.step, "finish", None, None, None, duration_ms)
                break

            # 3. Model requested a tool execution
            tool_name = response.tool_name or ""
            tool_args = response.tool_args or {}

            # Append assistant message
            state.messages.append(Message(
                role="assistant",
                content=response.content or "",
                tool_call={"name": tool_name, "args": tool_args}
            ))

            # 4. Runtime executes tool
            result = registry.execute(tool_name, tool_args)

            # 5. Record observation back in state
            state.messages.append(Message(
                role="tool",
                name=tool_name,
                content=result
            ))

            duration_ms = (time.perf_counter() - step_start) * 1000
            self._record(state.step, "tool_call", tool_name, tool_args, result, duration_ms)

        if not state.is_finished and not state.final_answer:
            state.final_answer = f"Aborted: Maximum step limit ({self.max_steps}) reached."

        return state.final_answer

    def _record(
        self,
        step: int,
        decision_type: str,
        tool_name: str | None,
        tool_args: dict[str, Any] | None,
        tool_result: dict[str, Any] | None,
        duration_ms: float
    ) -> None:
        self.trajectory.append(StepLog(
            step=step,
            decision_type=decision_type,
            tool_name=tool_name,
            tool_args=tool_args,
            tool_result=tool_result,
            duration_ms=round(duration_ms, 2)
        ))
