"""
Tokenizes and validates arithmetic expression strings.
"""


def parse_tokens(expression: str) -> list[str]:
    """
    Splits an expression string into number and operator tokens.
    e.g. '2 + 3 * 4' -> ['2', '+', '3', '*', '4']
    """
    # BUG: Naively splits only on whitespace, failing when operators lack spaces
    raw_tokens = expression.split()
    for tok in raw_tokens:
        if not (tok.isdigit() or tok in ("+", "-", "*", "/", "^", "(", ")")):
            raise ValueError(f"Invalid token: {tok}")
    return raw_tokens
