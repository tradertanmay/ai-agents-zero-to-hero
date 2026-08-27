# Exercise 04: Add Shipping Calculation to Your Agent

## Goal
Extend the agent created in Module 04 by adding a new tool and updating the decision logic to handle shipping fees based on customer location.

---

## The Challenge

1. Implement a new tool:
   ```python
   def get_shipping_fee(tier: str, zip_code: str) -> float:
       """
       Gold tier customers get free shipping ($0.0).
       Standard tier customers pay $15.00 for shipping.
       All others pay $25.00.
       """
       # Implement logic
   ```
2. Register `get_shipping_fee` with the `ToolRegistry`.
3. Modify the goal to:
   *"Calculate final bill for customer 'cust_42' on a $250 purchase shipping to zip '94105'."*
4. Trace the execution and verify that the agent resolves the goal through 4 sequential tool calls:
   - `get_customer_info` $\to$ Returns tier (`gold`)
   - `multiply` $\to$ Discount ($50)
   - `subtract` $\to$ Subtotal ($200)
   - `get_shipping_fee` $\to$ Shipping ($0.0)
   - `add` $\to$ Final Total ($200.0)

---

## Verification Check
Run your updated script and ensure `AgentState.messages` records every tool observation accurately and concludes with the correct final answer.
