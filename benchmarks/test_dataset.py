"""Check that the logical oracle is order-independent and rejects changed rows."""

import json
from pathlib import Path
import tempfile
import unittest

from dataset import COLUMNS, GOLDEN, identity, read_golden, summarize


class LogicalComparisonTest(unittest.TestCase):
    def setUp(self):
        self.expected = read_golden(GOLDEN)
        self.rows = list(self.expected.values())

    def test_permutation_preserves_fingerprint(self):
        self.assertEqual(summarize(self.rows, self.expected),
                         summarize(reversed(self.rows), self.expected))

    def test_invalid_golden_field_types_and_ranges(self):
        source = self.rows[0]
        invalid = [(name, None) for name in COLUMNS[:8]]
        for name in COLUMNS[8:11] + COLUMNS[12:14]:
            invalid.extend((name, val) for val in (True, 2.0, -(2**31) - 1, 2**31))
        invalid.extend(("has_text_conflict", val) for val in (0, 1, "false"))
        invalid.extend(("top_author_share_90d", val)
                       for val in (True, 1, "1.0", 1e300, float("nan"), float("inf")))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "golden.json"
            for name, value in invalid:
                with self.subTest(name=name, value=value):
                    path.write_text(json.dumps([dict(source, **{name: value})]), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, name):
                        read_golden(path)

    def test_golden_decimal_compares_at_parquet_float_precision(self):
        row = dict(self.rows[0], top_author_share_90d=0.6666667)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "golden.json"
            path.write_text(json.dumps([row]), encoding="utf-8")
            expected = read_golden(path)
        value = expected[identity(row)]["top_author_share_90d"]
        self.assertEqual(value, 0.6666666865348816)
        self.assertEqual(summarize([dict(row, top_author_share_90d=value)], expected)["samples"], 1)
        previous_float = 0.6666666269302368
        with self.assertRaisesRegex(ValueError, "top_author_share_90d"):
            summarize([dict(row, top_author_share_90d=previous_float)], expected)

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
