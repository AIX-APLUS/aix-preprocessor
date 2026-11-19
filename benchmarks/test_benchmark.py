"""Keep failed trials and warmups out of the published performance baseline."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from benchmark import summarize


class BenchmarkTest(unittest.TestCase):
    def test_summary_uses_only_verified_measurements_for_each_thread_count(self):
        measured = [
            dict(threads=1, phase="measured", success=True, seconds=s,
                 merges_per_second=6 / s, samples_per_second=12 / s)
            for s in (1, 2, 3)
        ]
        summary = summarize([
            *measured,
            dict(threads=1, phase="warmup", success=True, seconds=100),
            dict(threads=1, phase="measured", success=False, seconds=200),
            dict(threads=4, phase="measured", success=False, seconds=300),
        ])
        self.assertEqual(3, summary["1"]["verified"])
        self.assertEqual(1, summary["1"]["failed"])
        self.assertEqual({"min": 1, "median": 2, "max": 3, "sample_stdev": 1},
                         summary["1"]["seconds"])
        self.assertEqual(3, summary["1"]["merges_per_second"]["median"])
        self.assertEqual(6, summary["1"]["samples_per_second"]["median"])
        self.assertEqual({"verified": 0, "failed": 1}, summary["4"])

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
