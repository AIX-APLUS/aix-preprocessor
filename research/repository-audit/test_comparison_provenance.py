"""A report built without Actions evidence must identify its REST-only observations."""
import unittest
from pathlib import Path
from unittest.mock import patch

import comparison


class ComparisonProvenanceTest(unittest.TestCase):
    def test_metadata_only_has_no_observed_git_run(self):
        with patch.object(comparison, "nullable", return_value={}):
            records = comparison.collect(Path(comparison.__file__).with_name("evidence"))
        for row in (r for r in records if r["record_type"] == "primary_candidate"):
            with self.subTest(repo=row["repository"]):
                self.assertIsNone(row["extractor_sha"])
                self.assertIsNone(row["analyzed_refs"]["default_git_graph"])
                self.assertEqual(row["total_commits_source"], "github_rest")
                self.assertEqual(row["total_commits"], row["total_commits_pinned_rest"])
                self.assertIsNone(row["eligible_samples"])

    def test_archived_graph_identifies_git_count_and_actual_extractor(self):
        records = comparison.collect(Path(comparison.__file__).with_name("evidence"))
        for row in (r for r in records if r["record_type"] == "primary_candidate"):
            with self.subTest(repo=row["repository"]):
                self.assertEqual(row["total_commits_source"], "git_rev_list")
                self.assertEqual(row["analyzed_refs"]["default_git_graph"], row["pinned_sha"])
                self.assertEqual(row["extractor_sha"], "06e755ebabed1707a3413ec99ffa2511b046c543")
