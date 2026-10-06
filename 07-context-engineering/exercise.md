# Exercise 07: Dynamic Tool Filtering and Stale Observation Deduplication

## Goal
Extend the `ContextAssembler` from Module 07 by implementing **Dynamic Tool Filtering** (reducing tool schema tokens based on active task phase) and **Stale Observation Deduplication** (preventing repeated file reads or log fetches from poisoning the context).

---

## The Challenge

1. **Tag Tools with Categories / Phases**:
   Update tool definitions to include an optional `category` or `phase` tag:
   ```python
   tool = {
       "name": "git_commit",
       "description": "Commits staged changes",
       "category": "deployment",  # "investigation", "remediation", "deployment"
       "parameters": {...}
   }
   ```

2. **Implement Phase-Aware Tool Filtering in `ContextAssembler`**:
   Add a method to inject only tools relevant to the active task phase:
   ```python
   def set_tools_for_phase(self, all_tools: list[dict[str, Any]], active_phase: str) -> None:
       """Filters tool catalog to only include tools matching active_phase or 'general'."""
       filtered = [
           t for t in all_tools
           if t.get("category") == active_phase or t.get("category") == "general"
       ]
       self.set_tools(filtered)
   ```

3. **Implement Stale Observation Replacement**:
   When an agent calls an idempotent read tool (e.g., `read_file("config.py")`) multiple times, keeping older outputs wastes tokens and can cause the model to act on outdated information.
   
   In `ContextAssembler.add_tool_observation`:
   - Detect if an observation for the same tool and target already exists in `self.turns`.
   - If found, replace the old turn's content with `[Superseded by turn T: newer read result available below]` to reclaim tokens without breaking turn ordering.

---

## Verification Check

Write a short verification test:
1. Create a catalog of 8 tools across `["investigation", "deployment"]`.
2. Filter for phase `"investigation"`; verify that `deployment` tools are excluded and tool schema tokens decrease significantly.
3. Add a tool observation for `read_file("db.py")` with content $V_1$.
4. Add another observation for `read_file("db.py")` with content $V_2$.
5. Verify that the earlier turn was compressed/superseded and only $V_2$ occupies the active observation budget.
