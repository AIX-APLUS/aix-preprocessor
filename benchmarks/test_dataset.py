"""Check that the logical oracle is order-independent and rejects changed rows."""

import unittest

from dataset import COLUMNS, GOLDEN, read_golden, summarize


class LogicalComparisonTest(unittest.TestCase):
    def setUp(self):
        self.expected = read_golden(GOLDEN)
        self.rows = list(self.expected.values())

    def test_permutation_preserves_fingerprint(self):
        self.assertEqual(summarize(self.rows, self.expected),
                         summarize(reversed(self.rows), self.expected))

    def test_missing_extra_duplicate(self):
        for pattern, rows in [
            ("Missing", self.rows[1:]),
            ("Unexpected", [dict(self.rows[0], base_path="Extra.java"), *self.rows]),
            ("Duplicate", [*self.rows, self.rows[0]]),
        ]:
            with self.subTest(pattern), self.assertRaisesRegex(ValueError, pattern):
                summarize(rows, self.expected)

    def test_all_fields_contribute_to_fingerprint_and_golden_comparison(self):
        before = summarize(self.rows)["logical_sha256"]
        for name in COLUMNS:
            row = self.rows[0].copy()
            value = row[name]
            if isinstance(value, bool):
                row[name] = not value
            elif isinstance(value, str):
                row[name] = value + "\n"
            else:
                row[name] = value + 1
            changed = [row, *self.rows[1:]]
            with self.subTest(name):
                self.assertNotEqual(before, summarize(changed)["logical_sha256"])
                with self.assertRaises(ValueError):
                    summarize(changed, self.expected)


if __name__ == "__main__":
    unittest.main()
