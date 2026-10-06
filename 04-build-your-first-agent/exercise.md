# Exercise 04: Add Shipping Calculation and Regression Test to Your Agent

## Goal
Extend the agent created in Module 04 by adding a new tool, updating the decision logic to handle shipping fees based on customer location, and adding a regression test case to the evaluation scorecard.

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
       if tier == "gold":
           return 0.0
       elif tier == "standard":
           return 15.0
       return 25.0
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
5. **Add a Regression Test Case**:
   - Add an 11th `TestCase` to `build_10_case_battery()`:
     ```python
     TestCase(
         case_id=11,
         name="Gold tier with shipping fee",
         goal="Calculate final bill for customer 'cust_42' on a $250 purchase shipping to zip '94105'.",
         max_steps=6,
         expected_keyword="Gold member",
         expected_amount="$200.00"
     )
     ```
   - Run the scorecard and ensure the agent achieves **11/11 passed (100%)** without breaking existing cases!

---

## Verification Check
Run your updated script and ensure `AgentState.messages` records every tool observation accurately, and the regression scorecard shows zero regressions across all test cases.
