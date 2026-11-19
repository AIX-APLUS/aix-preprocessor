"""Offline regressions for complete study artifacts. Parquet decoding is exercised by quality.py."""
import base64
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

import quality
from report_study import summaries


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = HERE / "evidence" / "runs"
REPOS = [line.split()[1] for line in (HERE / "pins.tsv").read_text().splitlines()]


class StudyWorkflowTest(unittest.TestCase):
    def setUp(self):
        # Use a real work volume for the pilot's atomic publication (including on Windows).
        tmp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name)
        self.results = self.work / "results"
        self.results.mkdir()
        self.inputs = [self.work / (r.replace("/", "__") + ".parquet") for r in REPOS]
        for path in self.inputs:
            name = "pilot-" + path.stem + ".json"
            shutil.copyfile(RUN / name, self.results / name)
        shutil.copyfile(RUN / "quality.json", self.results / "quality.json")
        self.first = self.results / ("pilot-" + self.inputs[0].stem + ".json")

    def manifests(self):
        return quality.study_pilots(self.results, self.inputs)

    def test_five_successful_manifests(self):
        reports = list(self.manifests().values())
        self.assertEqual((380, 54, 326), tuple(sum(r[field] for r in reports) for field in
                         ("eligible_samples", "positive_samples", "negative_samples")))

    def test_missing_parquet_or_duplicate(self):
        self.inputs.pop()
        with self.assertRaisesRegex(ValueError, "five pinned"):
            self.manifests()
        self.inputs.append(self.inputs[0])
        with self.assertRaisesRegex(ValueError, "five pinned"):
            self.manifests()

    def test_missing_empty_or_corrupt_pilot_report(self):
        self.first.unlink()
        with self.assertRaisesRegex(ValueError, "missing or invalid"):
            self.manifests()
        for content in (b"", b'{"status":'):
            self.first.write_bytes(content)
            with self.subTest(content=content), self.assertRaisesRegex(ValueError, "missing or invalid"):
                self.manifests()

    def test_partial_extraction_and_pin_mismatches(self):
        report = json.loads(self.first.read_bytes())
        for field, value in (("status", "failed"), ("extraction_exit", 124), ("repository", "other/repo"),
                             ("default_tip", "0"*40), ("extractor_sha", "0"*40),
                             ("analyzed_refs", ["a"*40 + " refs/heads/pilot"]), ("source_refs_preserved", False)):
            self.first.write_text(json.dumps({**report, field: value}), encoding="utf-8")
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.manifests()

    def test_coordinated_anchor_and_ref_change(self):
        report = json.loads(self.first.read_bytes())
        # A real, different commit from the same history. Both self-reported fields still agree.
        other = report["default_tip"]
        self.assertNotEqual(report["pilot_anchor"], other)
        report.update(pilot_anchor=other, analyzed_refs=[other + " refs/heads/pilot"])
        self.first.write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "analyzed pilot ref"):
            self.manifests()

    def test_tokenizer_self_hash_cannot_replace_pin(self):
        file = self.work / "other-tokenizer.json"
        file.write_bytes(b'{"example":"different"}')
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
        self.assertEqual(digest, quality.tokenizer_digest(file, digest, required=False))
        with self.assertRaisesRegex(ValueError, "Qwen tokenizer"):
            quality.tokenizer_digest(file, digest, required=True)

    def test_tokenizer_required_for_study_optional_for_generic_quality(self):
        self.assertIsNone(quality.tokenizer_digest(None, None, required=False))
        with self.assertRaisesRegex(ValueError, "requires"):
            quality.tokenizer_digest(None, None, required=True)

    def test_changed_logical_digest_rejected_even_with_same_counts(self):
        # A valid zero-row Parquet has a defined digest even though it has no row-level repo_id.
        digest = hashlib.sha256(b"aix-merge-sample-v1\n").hexdigest()
        report = {"repository": REPOS[0], "eligible_samples": 0, "positive_samples": 0, "negative_samples": 0,
                  "parquet_validation": {"samples": 0, "positive": 0, "negative": 0, "logical_sha256": digest}}
        quality.check_study_rows(report, {})
        report["parquet_validation"]["logical_sha256"] = "a"*64
        with self.assertRaisesRegex(ValueError, "Parquet validation"):
            quality.check_study_rows(report, {})

    def test_five_zero_yield_pilots_can_publish_zero_yield(self):
        quality_file = self.results / "quality.json"
        aggregate = json.loads(quality_file.read_bytes())
        aggregate["token_analysis"] = "no_rows"
        for profile in [*aggregate["inputs"], aggregate["combined_profile"]]:
            profile.update(rows=0, positive=0, negative=0, base_code_tokens=None)
        for path in self.results.glob("pilot-*.json"):
            pilot = json.loads(path.read_bytes())
            pilot.update(eligible_samples=0, positive_samples=0, negative_samples=0)
            pilot["parquet_validation"].update(samples=0, positive=0, negative=0,
                                               logical_sha256=hashlib.sha256(b"aix-merge-sample-v1\n").hexdigest())
            path.write_text(json.dumps(pilot), encoding="utf-8")
        quality_file.write_text(json.dumps(aggregate), encoding="utf-8")
        self.assertEqual(6, len(list(summaries(self.results))))

    def pilot_args(self):
        return ["run", REPOS[0], "1"*40, "--source", str(ROOT), "--jar", str(self.work / "jar"),
                "--work", str(self.work / "pilot"), "--out", str(self.work)]

    def test_failed_pilot_publishes_readable_diagnostic(self):
        proc = subprocess.run([sys.executable, "-B", str(HERE / "pilot.py"), *self.pilot_args()], capture_output=True)
        self.assertNotEqual(0, proc.returncode)
        report = json.loads((self.work / self.first.name).read_bytes())
        self.assertEqual("failed", report["status"])
        self.assertIn("jar", report["error"])

    def test_terminated_pilot_leaves_no_published_empty_json(self):
        # Pause the real pilot inside its first subprocess, then terminate it as a runner timeout would.
        (self.work / "jar").touch()
        ready = self.work / "started"
        child = """import pathlib, runpy, subprocess, sys, time
def pause(*args, **kwargs):
    ready.touch()
    time.sleep(60)
ready = pathlib.Path(sys.argv.pop(1))
sys.argv.pop(0)
subprocess.run = pause
runpy.run_path(sys.argv[0], run_name='__main__')
"""
        with subprocess.Popen([sys.executable, "-B", "-c", child, str(ready), str(HERE / "pilot.py"),
                               *self.pilot_args()]) as proc:
            try:
                until = time.monotonic() + 10
                while not ready.exists() and proc.poll() is None and time.monotonic() < until:
                    time.sleep(.02)
                self.assertTrue(ready.exists(), "pilot never entered subprocess")
            finally:
                proc.kill()
                proc.wait(timeout=10)
        self.assertFalse((self.work / self.first.name).exists())

    def test_aggregate_step_emits_only_complete_readable_payloads(self):
        def summarize():
            return subprocess.run([sys.executable, "-B", str(HERE / "report_study.py"), str(self.results)],
                                  capture_output=True)

        good = summarize()
        self.assertEqual(0, good.returncode, good.stderr)
        lines = good.stdout.splitlines()
        self.assertEqual(6, len(lines))
        for line in lines:
            label, name, payload = line.split()
            self.assertEqual(b"SUMMARY", label)
            self.assertEqual((self.results / name.decode()).read_bytes(), gzip.decompress(base64.b64decode(payload)))
        quality_file = self.results / "quality.json"
        quality_file.unlink()
        for invalid in (None, b"", b"{", b"{}"):
            if invalid is not None:
                quality_file.write_bytes(invalid)
            bad = summarize()
            with self.subTest(invalid=invalid):
                self.assertNotEqual(0, bad.returncode)
                self.assertEqual(b"", bad.stdout)


if __name__ == "__main__":
    unittest.main()
