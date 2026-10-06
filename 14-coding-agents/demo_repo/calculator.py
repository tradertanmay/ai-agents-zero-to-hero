"""
Basic arithmetic calculator operations.
"""


def calculate(op: str, a: float, b: float) -> float:
    """Performs arithmetic operations on two numbers."""
    if op == "+":
        return a + b
    elif op == "-":
        return a - b
    elif op == "*":
        return a * b
    elif op == "/":
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
    elif op == "^":
        # BUG: Uses bitwise XOR instead of exponentiation
        return float(int(a) ^ int(b))
    else:
        raise ValueError(f"Unsupported operator: {op}")
