"""Measure optional research profiles only on exact logical replicas of the archived pilots."""

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from quality import distribution

AUDIT = Path(__file__).resolve().parent
TOKEN_THRESHOLDS = (4096, 8192, 16384, 32768)
BYTE_THRESHOLDS = (16384, 65536)
REVISION = "8123ea2e9354afb7ffcc6c8641d1b2f5ecf18301"


def require_match(actual, expected, what):
    if actual != expected:
        raise ValueError(f"{what} differs from the recovered Ubuntu pilot")


def summarize(rows, numeric_fields):
    positive = [r for r in rows if r["has_text_conflict"]]
    positive_merges = Counter((r["repo_id"], r["merge_sha"]) for r in positive)
    features = {}
    for field in numeric_fields:
        values = [r[field] for r in rows]
        quantiles = distribution(values)
        features[field] = {**quantiles, "zero_rows": values.count(0)} if quantiles else None
    return {
        "rows": len(rows), "positive_rows": len(positive), "negative_rows": len(rows) - len(positive),
        "unique_positive_merges": len(positive_merges),
        "unique_positive_paths": len({(r["repo_id"], r["base_path"]) for r in positive}),
        "max_positives_from_one_merge": max(positive_merges.values(), default=0),
        "history_features": features,
        "base_code_tokens_gt": {str(t): sum(r["tokens"] > t for r in rows) for t in TOKEN_THRESHOLDS},
        "positive_base_code_tokens_gt": {str(t): sum(r["tokens"] > t for r in positive) for t in TOKEN_THRESHOLDS},
        "base_code_utf8_bytes_gt": {str(t): sum(r["bytes"] > t for r in rows) for t in BYTE_THRESHOLDS},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datasets", required=True, type=Path, help="owner__repo.parquet files")
    parser.add_argument("--jar", required=True, type=Path, help="pinned extractor fat JAR / Parquet reader classpath")
    parser.add_argument("--benchmarks", default=AUDIT.parents[1] / "benchmarks", type=Path)
    parser.add_argument("--tokenizer-json", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.benchmarks.resolve()))
    import dataset
    import tokenizers

    evidence = AUDIT / "evidence" / "runs"
    quality = json.loads((evidence / "quality.json").read_bytes())
    expected_profiles = {entry["repo_id"]: entry for entry in quality["inputs"]}
    tokenizer_hash = hashlib.sha256(args.tokenizer_json.read_bytes()).hexdigest()
    require_match(tokenizer_hash, quality["tokenizer_json_sha256"], "tokenizer SHA-256")
    require_match(tokenizers.__version__, "0.21.4", "tokenizers version")
    tokenizer = tokenizers.Tokenizer.from_file(str(args.tokenizer_json))
    tokenizer.no_padding()
    tokenizer.no_truncation()

    result = {
        "source_run": 44549292132,
        "method": "Supplemental profiling of each complete historical pilot only after matching the original 15-column, key-sorted logical SHA-256, class counts and token quantiles. No runtimes are reused from the replay.",
        "tokenizer": {"model": "Qwen/Qwen2.5-Coder-0.5B", "revision": REVISION,
                      "tokenizer_json_sha256": tokenizer_hash, "tokenizers_version": tokenizers.__version__,
                      "scope": "base_code only, no padding, truncation or special tokens"},
        "definitions": {"unique_positive_merges": "distinct (repo_id, merge_sha) with at least one positive row",
                        "unique_positive_paths": "distinct (repo_id, base_path) with at least one positive row; aliases are separate",
                        "history_features": "row-weighted nearest-rank statistics of the six stored numeric history fields",
                        "tail_counts": "strictly greater than each threshold, one count per sample, including repeated paths",
                        "combined": "all exact-verified pilots, weighted by individual rows"},
        "repositories": {},
    }
    pooled = []
    features = dataset.COLUMNS[8:14]
    for pilot_path in sorted(evidence.glob("pilot-*.json")):
        pilot = json.loads(pilot_path.read_bytes())
        repo = pilot["repository"]
        parquet = args.datasets / (repo.replace("/", "__") + ".parquet")
        lines = subprocess.check_output(["java", "--class-path", str(args.jar.resolve()),
                                         str(args.benchmarks.resolve() / "DumpParquet.java"), str(parquet.resolve())],
                                        encoding="ascii")
        source_rows = [dataset.decode_row(line) for line in lines.splitlines()]
        verified = dataset.summarize(source_rows)
        require_match(verified, pilot["parquet_validation"], f"{repo} logical rows")
        rows = []
        for row in source_rows:
            require_match(row["repo_id"], repo, "repository identity")
            rows.append({**{key: row[key] for key in ("repo_id", "merge_sha", "base_path", "has_text_conflict", *features)},
                         "bytes": len(row["base_code"].encode("utf-8")),
                         "tokens": len(tokenizer.encode(row["base_code"], add_special_tokens=False).ids)})
        require_match(distribution(r["tokens"] for r in rows), expected_profiles[repo]["base_code_tokens"],
                      f"{repo} Qwen token quantiles")
        result["repositories"][repo] = {
            "source_pilot": f"evidence/runs/{pilot_path.name}", "pilot_anchor": pilot["pilot_anchor"],
            "logical_sha256": verified["logical_sha256"], "validation": "all_15_fields_logical_sha256_matches_ubuntu",
            **summarize(rows, features),
        }
        pooled.extend(rows)
    require_match(set(result["repositories"]), set(expected_profiles), "reproduced repositories")
    result["combined"] = summarize(pooled, features)
    args.output.write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
