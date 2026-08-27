# Exercise 00: Environment Verification

Let's ensure your environment is ready for the entire course.

---

## Goal
Verify that your Python installation is 3.11+ and that the standard library test runner works properly.

---

## Step-by-Step Instructions

### Step 1: Check Python Version
Open your terminal in the repository root and run:

```bash
python3 --version
```

*Expected output:* `Python 3.11.x` (or newer, e.g. 3.12, 3.13).

### Step 2: Verify No Third-Party Packages Are Required
Run Python with a dry-run check of the standard libraries we use:

```bash
python3 -c "import json, dataclasses, typing, unittest, time, urllib.request; print('All core standard libraries available!')"
```

*Expected output:* `All core standard libraries available!`

### Step 3: Run the Test Suite
Run the built-in test runner:

```bash
python3 -m unittest discover -s tests -v
```

---

## Reflection Question
In your own words:
1. What is the difference between an **LLM** and an **Agent**?
2. If an LLM cannot execute tools directly, who actually executes them?

*(Proceed to [01-what-is-an-agent](../01-what-is-an-agent/README.md) to explore the answers!)*
