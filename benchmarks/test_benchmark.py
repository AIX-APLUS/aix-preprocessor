"""Keep failed trials and warmups out of the published performance baseline."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from benchmark import checkout_state, one_run, summarize


class BenchmarkTest(unittest.TestCase):
    def test_summary_uses_only_verified_measurements_for_each_thread_count(self):
        measured = [
            dict(threads=1, phase="measured", success=True, seconds=s,
                 merges_per_second=6 / s, samples_per_second=12 / s)
            for s in (1, 2, 3)
        ]
        runs = [
            *measured,
            dict(threads=1, phase="warmup", success=True, seconds=100),
        ]
        summary = summarize(runs, complete=True)
        self.assertEqual(3, summary["1"]["verified"])
        self.assertEqual(0, summary["1"]["failed"])
        self.assertEqual({"min": 1, "median": 2, "max": 3, "sample_stdev": 1},
                         summary["1"]["seconds"])
        self.assertEqual(3, summary["1"]["merges_per_second"]["median"])
        self.assertEqual(6, summary["1"]["samples_per_second"]["median"])
        partial = summarize([
            *runs,
            dict(threads=1, phase="measured", success=False, seconds=200),
            dict(threads=4, phase="measured", success=False, seconds=300),
        ], complete=False)
        self.assertEqual({"verified": 3, "failed": 1}, partial["1"])
        self.assertEqual({"verified": 0, "failed": 1}, partial["4"])

    def test_first_trial_rejects_consistently_wrong_output_against_external_expectations(self):
        observed = dict(samples=0, positive=0, negative=0, logical_sha256="0" * 64)
        args = SimpleNamespace(java="java", jar="subject.jar")
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)

            def run_cli(cmd, *, stdout, stderr):
                (work / "trial.parquet").write_bytes(b"reader test double")
                stdout.write(b"7 two-parent merges, 0 samples, 0 positives. Skips: {}\n")
                return subprocess.CompletedProcess(cmd, 0)

            with patch("benchmark.subprocess.run", side_effect=run_cli), \
                    patch("benchmark.inspect_dataset", return_value=observed):
                for count, digest, error in [(1, "0" * 64, "Expected 1 samples"),
                                             (0, "1" * 64, "Logical SHA-256")]:
                    with self.subTest(count=count, digest=digest):
                        args.expect_samples, args.expect_logical_sha256 = count, digest
                        trial = {"threads": 1, "success": False}
                        with self.assertRaisesRegex(ValueError, error):
                            one_run(trial, args, work, "test/repo", work, 7, None, reference=None)
                        self.assertFalse(trial["success"])
                        self.assertEqual(0, trial["samples"])

    def test_checkout_metadata_is_optional_outside_git(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual({"head": None, "dirty": None}, checkout_state(Path(directory)))

    def test_setup_failure_exits_nonzero_and_records_no_measurements(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            report = work / "report.json"
            cmd = [sys.executable, str(Path(__file__).with_name("benchmark.py")),
                   "--jar", str(work / "absent.jar"), "--report", str(report)]
            process = subprocess.run(cmd, capture_output=True)
            self.assertNotEqual(0, process.returncode)
            result = json.loads(report.read_bytes())
            self.assertIs(result["success"], False)
            self.assertIn("absent.jar", result["error"])
            self.assertEqual([], result["runs"])
            self.assertEqual({}, result["summary_by_threads"])


if __name__ == "__main__":
    unittest.main()
