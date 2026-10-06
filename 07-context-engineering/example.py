"""
Module 07: Context Engineering
Runnable Python Demonstration: Context Budgeting, Pruning, and Anti-Pollution

This script demonstrates how to engineer the LLM context window to prevent
context pollution, enforce strict token budgets, and distill verbose tool
outputs using pure standard Python 3.11+ (zero dependencies).
"""

from dataclasses import dataclass, field
import json
import re
from typing import Any


# ============================================================================
# 1. Token Estimation (Standard Library Heuristic)
# ============================================================================

class TokenEstimator:
    """
    Zero-dependency token estimator.
    Approximates BPE tokenization using standard 4-chars-per-token heuristic
    for mixed natural language and code.
    """
    @staticmethod
    def count(text: str) -> int:
        if not text:
            return 0
        # Average English and code tokens are roughly 3.8 - 4.2 characters
        return max(1, (len(text) + 3) // 4)

    @staticmethod
    def count_messages(messages: list[dict[str, str]]) -> int:
        total = 0
        for m in messages:
            # Add message envelope overhead (~4 tokens per message in OpenAI format)
            total += 4 + TokenEstimator.count(m.get("content", "")) + TokenEstimator.count(m.get("role", ""))
        return total


# ============================================================================
# 2. Context Partition Budgets
# ============================================================================

@dataclass
class ContextBudget:
    """Hard token limits for each partition of the context window."""
    max_total_tokens: int = 1000
    system_prompt_max: int = 200
    active_state_max: int = 150
    tool_schemas_max: int = 250
    history_turns_max: int = 250
    observation_max: int = 150


# ============================================================================
# 3. Observation Pruning & Distillation
# ============================================================================

class ObservationPruner:
    """Techniques for distilling noisy, verbose tool outputs before context injection."""

    @staticmethod
    def head_tail_truncate(text: str, max_lines: int = 20) -> str:
        """Keeps first N/2 and last N/2 lines, omitting the noisy middle."""
        lines = text.strip().splitlines()
        if len(lines) <= max_lines:
            return text

        half = max_lines // 2
        omitted = len(lines) - (half * 2)
        head = lines[:half]
        tail = lines[-half:]
        return "\n".join(head + [f"... [{omitted} lines omitted to conserve context] ..."] + tail)

    @staticmethod
    def extract_error_signals(text: str, context_lines: int = 2) -> str:
        """
        Greps for error keywords and extracts surrounding lines only.
        Keywords: ERROR, FAIL, Exception, Traceback, Critical.
        """
        lines = text.strip().splitlines()
        error_pattern = re.compile(r"(error|fail|exception|traceback|critical|fatal)", re.IGNORECASE)
        matched_indices: set[int] = set()

        for idx, line in enumerate(lines):
            if error_pattern.search(line):
                for offset in range(-context_lines, context_lines + 1):
                    target = idx + offset
                    if 0 <= target < len(lines):
                        matched_indices.add(target)

        if not matched_indices:
            # Fall back to head-tail if no explicit error keywords matched
            return ObservationPruner.head_tail_truncate(text, max_lines=10)

        sorted_indices = sorted(matched_indices)
        extracted: list[str] = []
        last_idx = -1

        for idx in sorted_indices:
            if last_idx != -1 and idx > last_idx + 1:
                extracted.append("  [... omitted lines ...]")
            extracted.append(f"  Line {idx + 1}: {lines[idx]}")
            last_idx = idx

        header = f"[Extracted {len(sorted_indices)} relevant error lines from {len(lines)} total lines]:\n"
        return header + "\n".join(extracted)

    @staticmethod
    def project_json(data: dict[str, Any], allowed_keys: set[str]) -> dict[str, Any]:
        """Filters high-cardinality JSON responses down to essential fields."""
        return {k: v for k, v in data.items() if k in allowed_keys}


# ============================================================================
# 4. Context Assembler
# ============================================================================

class ContextAssembler:
    """
    Constructs the model context while respecting hard partition budgets
    and preventing context pollution.
    """
    def __init__(self, budget: ContextBudget) -> None:
        self.budget = budget
        self.system_prompt: str = ""
        self.goal: str = ""
        self.scratchpad: dict[str, Any] = {}
        self.tools: list[dict[str, Any]] = []
        self.turns: list[dict[str, str]] = []

    def set_system_prompt(self, prompt: str) -> None:
        self.system_prompt = prompt.strip()

    def set_task(self, goal: str, scratchpad: dict[str, Any] | None = None) -> None:
        self.goal = goal.strip()
        self.scratchpad = scratchpad or {}

    def set_tools(self, tools: list[dict[str, Any]]) -> None:
        self.tools = tools

    def add_turn(self, role: str, content: str) -> None:
        self.turns.append({"role": role, "content": content})

    def add_tool_observation(self, tool_name: str, raw_output: str, prune: bool = True) -> None:
        if prune:
            est_tokens = TokenEstimator.count(raw_output)
            if est_tokens > self.budget.observation_max:
                distilled = ObservationPruner.extract_error_signals(raw_output)
                content = f"Tool '{tool_name}' Output (Distilled):\n{distilled}"
            else:
                content = f"Tool '{tool_name}' Output:\n{raw_output}"
        else:
            content = f"Tool '{tool_name}' Output (Raw):\n{raw_output}"

        self.turns.append({"role": "tool", "content": content})

    def assemble(self) -> tuple[list[dict[str, str]], dict[str, int]]:
        """
        Assembles the prioritized context array:
        1. System Prompt (Anchor)
        2. Goal & Working State (Anchor)
        3. Dynamic Tool Schemas
        4. Turn History (Sliding window if necessary)
        """
        messages: list[dict[str, str]] = []
        breakdown: dict[str, int] = {}

        # 1. System Prompt
        sys_tokens = TokenEstimator.count(self.system_prompt)
        breakdown["system_prompt"] = sys_tokens
        messages.append({"role": "system", "content": self.system_prompt})

        # 2. Goal & State Anchor
        state_str = json.dumps(self.scratchpad, indent=2) if self.scratchpad else "{}"
        state_content = f"ACTIVE GOAL: {self.goal}\nWORKING STATE:\n{state_str}"
        state_tokens = TokenEstimator.count(state_content)
        breakdown["active_state"] = state_tokens
        messages.append({"role": "system", "content": state_content})

        # 3. Tool Schemas
        tools_str = json.dumps(self.tools, indent=2)
        tools_content = f"AVAILABLE TOOLS:\n{tools_str}"
        tools_tokens = TokenEstimator.count(tools_content)
        breakdown["tool_schemas"] = tools_tokens
        messages.append({"role": "system", "content": tools_content})

        # 4. Turn History (Sliding window eviction if budget exceeded)
        history_tokens = 0
        included_turns: list[dict[str, str]] = []
        
        # Traverse turns from newest to oldest to preserve recency
        for turn in reversed(self.turns):
            turn_tokens = TokenEstimator.count(turn["content"]) + 4
            if history_tokens + turn_tokens <= self.budget.history_turns_max or not included_turns:
                included_turns.append(turn)
                history_tokens += turn_tokens
            else:
                # Evict older turns
                break

        # Restore chronological order
        included_turns.reverse()
        breakdown["history_turns"] = history_tokens
        messages.extend(included_turns)

        total_tokens = sum(breakdown.values())
        breakdown["total_tokens"] = total_tokens
        return messages, breakdown


# ============================================================================
# 5. Demonstration: Unmanaged vs. Context-Engineered Agent
# ============================================================================

def generate_simulated_verbose_log() -> str:
    """Generates a realistic 300-line server log with 1 buried critical error."""
    lines = []
    for i in range(1, 140):
        lines.append(f"2026-10-05 14:00:{i%60:02d} INFO [worker-{i%4}] Health check OK. Latency {10 + i%5}ms.")
    
    # Buried root cause
    lines.append("2026-10-05 14:01:02 ERROR [auth_service] DBConnectionError: Connection refused at db_pool.py:84")
    lines.append("2026-10-05 14:01:03 CRITICAL [worker-2] Process worker-2 terminated with unhandled exception")
    
    for i in range(143, 260):
        lines.append(f"2026-10-05 14:02:{i%60:02d} INFO [worker-{i%4}] Retrying connection queue idle.")
    return "\n".join(lines)


def main() -> None:
    print("=" * 65)
    print("DEMO: CONTEXT ENGINEERING & TOKEN BUDGET MANAGEMENT")
    print("=" * 65)

    budget = ContextBudget(
        max_total_tokens=1000,
        system_prompt_max=150,
        active_state_max=100,
        tool_schemas_max=200,
        history_turns_max=350,
        observation_max=200,
    )

    system_instructions = (
        "You are an SRE Incident Agent. You diagnose infrastructure faults.\n"
        "Strict rules: Never deploy without verification. Report root cause."
    )
    goal = "Investigate why auth_service is failing in cluster staging-us-east."
    tools = [
        {"name": "fetch_logs", "description": "Fetches raw service logs", "parameters": {"service": "str"}},
        {"name": "restart_service", "description": "Restarts a service", "parameters": {"service": "str"}}
    ]

    verbose_log = generate_simulated_verbose_log()
    raw_log_tokens = TokenEstimator.count(verbose_log)
    print(f"Generated raw server log: {len(verbose_log.splitlines())} lines (~{raw_log_tokens} tokens).")

    # ------------------------------------------------------------------------
    # Scenario 1: Unmanaged Context (Pollution & Budget Overflow)
    # ------------------------------------------------------------------------
    print("\n--- [SCENARIO 1] Unmanaged Context (Raw Injection) ---")
    unmanaged = ContextAssembler(budget)
    unmanaged.set_system_prompt(system_instructions)
    unmanaged.set_task(goal, {"status": "INVESTIGATING", "attempt": 1})
    unmanaged.set_tools(tools)
    unmanaged.add_turn("user", "Check the logs for auth_service immediately.")
    unmanaged.add_turn("assistant", "Calling fetch_logs(service='auth_service')...")
    
    # Inject RAW without pruning
    unmanaged.add_tool_observation("fetch_logs", verbose_log, prune=False)

    msgs_raw, breakdown_raw = unmanaged.assemble()
    print(f"Total Context Size: {breakdown_raw['total_tokens']} tokens (Budget Limit: {budget.max_total_tokens})")
    print("Token Breakdown:")
    for k, v in breakdown_raw.items():
        print(f"  - {k:<18}: {v} tokens")

    overflow = breakdown_raw['total_tokens'] > budget.max_total_tokens
    print(f"Budget Exceeded: {overflow} (Context overflow by {breakdown_raw['total_tokens'] - budget.max_total_tokens} tokens!)")

    # ------------------------------------------------------------------------
    # Scenario 2: Context-Engineered Assembler (Distilled & Budget-Compliant)
    # ------------------------------------------------------------------------
    print("\n" + "-" * 65)
    print("--- [SCENARIO 2] Context-Engineered (Signal Distillation) ---")
    print("-" * 65)
    managed = ContextAssembler(budget)
    managed.set_system_prompt(system_instructions)
    managed.set_task(goal, {"status": "INVESTIGATING", "attempt": 1})
    managed.set_tools(tools)
    managed.add_turn("user", "Check the logs for auth_service immediately.")
    managed.add_turn("assistant", "Calling fetch_logs(service='auth_service')...")

    # Inject with Automated Distillation / Pruning
    managed.add_tool_observation("fetch_logs", verbose_log, prune=True)

    msgs_managed, breakdown_managed = managed.assemble()
    print(f"Total Context Size: {breakdown_managed['total_tokens']} tokens (Budget Limit: {budget.max_total_tokens})")
    print("Token Breakdown:")
    for k, v in breakdown_managed.items():
        print(f"  - {k:<18}: {v} tokens")

    print(f"\nBudget Compliant: {breakdown_managed['total_tokens'] <= budget.max_total_tokens}")
    savings = breakdown_raw['total_tokens'] - breakdown_managed['total_tokens']
    pct = (savings / breakdown_raw['total_tokens']) * 100
    print(f"Token Savings: {savings} tokens ({pct:.1f}% reduction)")

    print("\nDistilled Observation Payload Seen by Model:")
    print("=" * 65)
    tool_turn = next(m for m in msgs_managed if m["role"] == "tool")
    print(tool_turn["content"])
    print("=" * 65)


if __name__ == "__main__":
    main()
