"""
Unit tests for calculator operations.
"""

import unittest
import os
import sys

# Ensure demo_repo root is importable
repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_dir not in sys.path:
    sys.path.insert(0, repo_dir)

from calculator import calculate


class TestCalculator(unittest.TestCase):
    def test_addition(self):
        self.assertEqual(calculate("+", 2, 3), 5.0)

    def test_subtraction(self):
        self.assertEqual(calculate("-", 10, 4), 6.0)

    def test_multiplication(self):
        self.assertEqual(calculate("*", 3, 4), 12.0)

    def test_division(self):
        self.assertEqual(calculate("/", 8, 2), 4.0)

    def test_division_by_zero(self):
        with self.assertRaises(ValueError):
            calculate("/", 5, 0)

    def test_power(self):
        # Fails initially due to XOR bug: calculate("^", 2, 3) returns 1.0 != 8.0
        self.assertEqual(calculate("^", 2, 3), 8.0)
        self.assertEqual(calculate("^", 3, 2), 9.0)


if __name__ == "__main__":
    unittest.main()
