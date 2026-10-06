"""
Unit tests for expression token parsing.
"""

import unittest
import os
import sys

repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_dir not in sys.path:
    sys.path.insert(0, repo_dir)

from parser import parse_tokens


class TestParser(unittest.TestCase):
    def test_token_spacing(self):
        self.assertEqual(parse_tokens("2 + 3"), ["2", "+", "3"])
        self.assertEqual(parse_tokens("10 * 5 - 2"), ["10", "*", "5", "-", "2"])

    def test_tokens_without_spaces(self):
        # Fails initially due to naive split() bug on unspaced operators
        self.assertEqual(parse_tokens("2+3*4"), ["2", "+", "3", "*", "4"])
        self.assertEqual(parse_tokens("10/(2+3)"), ["10", "/", "(", "2", "+", "3", ")"])


if __name__ == "__main__":
    unittest.main()
