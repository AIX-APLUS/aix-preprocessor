"""Audit candidate Parquets with the pinned AIX CLI. Run in the extractor checkout.

python quality.py --jar build/libs/aix-preprocessor.jar --output quality.json INPUTS...
Supply one *complete pilot* file per repo_id. No source code is written to the JSON.
"""
import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile


SPLITS = ("train", "val", "test")


def require(condition, message):
    if not condition:
        raise ValueError(message)


@dataclass(frozen=True)
class Sample:
    full_hash: bytes
    code_hash: bytes
    layout_hash: bytes
    positive: bool
    characters: int
    utf8_bytes: int
    tokens: int | None
    lines: int
    has_tab_indent: bool
    has_crlf: bool


def distribution(values):
    values = sorted(values)
    if not values:
        return None
    return {name: values[max(0, math.ceil(len(values) * p) - 1)]
            for name, p in (("min", 0), ("p50", .5), ("p90", .9), ("p95", .95), ("max", 1))}


def profile(records):
    """One row per sample, including repeats. No sampling or token estimation."""
    paths, modules, module_pos, merges = Counter(), Counter(), Counter(), Counter()
    code_labels = defaultdict(Counter)
    code_paths = defaultdict(set)
    for (repo, merge, path), sample in records.items():
        paths[repo, path] += 1
        module = path.split("/")[0] if "/" in path else "(root)"
        modules[module] += 1
        module_pos[module] += sample.positive
        merges[repo, merge] += 1
        code_labels[sample.code_hash][sample.positive] += 1
        code_paths[sample.code_hash].add((repo, path))
    n = len(records)
    positives = sum(s.positive for s in records.values())
    mixed = [c for c in code_labels.values() if len(c) > 1]
    return {
        "rows": n, "positive": positives, "negative": n - positives,
        "positive_fraction": positives / n if n else None,
        "contributing_merges": len(merges), "unique_paths": len(paths),
        "paths_seen_multiple_times": sum(v > 1 for v in paths.values()),
        "rows_on_repeated_paths": sum(v for v in paths.values() if v > 1),
        "max_rows_per_path": max(paths.values(), default=0),
        "top_level_path_rows": [{"top_level": p, "rows": count, "positive": module_pos[p]}
                                for p, count in modules.most_common(5)],
        "distinct_exact_code": len(code_labels), "repeated_code_excess_rows": n-len(code_labels),
        "code_hashes_at_multiple_paths": sum(len(v) > 1 for v in code_paths.values()),
        "code_hashes_with_both_labels": len(mixed),
        "rows_in_both_label_code_groups": sum(sum(v.values()) for v in mixed),
        "minority_rows_in_both_label_code_groups": sum(min(v.values()) for v in mixed),
        "base_code_unicode_characters": distribution(s.characters for s in records.values()),
        "base_code_utf8_bytes": distribution(s.utf8_bytes for s in records.values()),
        "base_code_tokens": distribution(s.tokens for s in records.values() if s.tokens is not None),
        "source_lines": distribution(s.lines for s in records.values()),
        "rows_with_tab_indented_line": sum(s.has_tab_indent for s in records.values()),
        "rows_with_crlf": sum(s.has_crlf for s in records.values()),
        "rows_under_src_test_java": sum("/src/test/java/" in ("/"+k[2]+"/") for k in records),
    }


def split_leakage(partitions):
    measures = {
        "repo_and_path": lambda key, row: (key[0], key[2]),
        "repo_and_merge": lambda key, row: key[:2],
        "exact_code_sha256": lambda key, row: row.code_hash,
        "layout_normalized_sha256": lambda key, row: row.layout_hash,
    }
    out = {}
    for name, identify in measures.items():
        groups = defaultdict(set)
        for part, rows in partitions.items():
            for key, row in rows.items():
                groups[identify(key, row)].add(part)
        out[name] = {"groups_in_multiple_splits": sum(len(v) > 1 for v in groups.values()),
                     "test_rows_seen_in_train": sum("train" in groups[identify(k, r)]
                                                    for k, r in partitions["test"].items())}
    return out


def corrupt_schema(source, target):
    # Rename a field and its column path in the Thrift footer. Equal byte lengths preserve framing.
    shutil.copyfile(source, target)
    with target.open("r+b") as stream:
        stream.seek(-8, os.SEEK_END)
        length, magic = struct.unpack("<I4s", stream.read(8))
        require(magic == b"PAR1", "Expected a Parquet footer")
        start = stream.tell() - 8 - length
        stream.seek(start)
        footer = stream.read(length)
        require(b"base_path" in footer, "Field name unavailable for invalid-schema control")
        stream.seek(start)
        stream.write(footer.replace(b"base_path", b"base_patz"))


def run(args, work):
    dataset_dir = args.benchmarks.resolve()
    sys.path.insert(0, str(dataset_dir))
    import dataset  # Pinned extractor's benchmark decoder and canonical column order.
    jar = args.jar.resolve()
    subprocess.run(["javac", "-cp", str(jar), "-d", str(work), str(dataset_dir / "DumpParquet.java")],
                   check=True)
    reader = ["java", "-cp", os.pathsep.join(map(str, (work, jar))), "DumpParquet"]
    def cli(*options, error=None):
        proc = subprocess.run(["java", "-jar", str(jar), *map(str, options)], capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
        if error:
            require(proc.returncode != 0 and error in proc.stderr, f"Negative control failed: {error}")
        else:
            require(proc.returncode == 0, f"{options[0]} exit {proc.returncode}: {proc.stderr[-900:]}")
        return proc.stdout

    tokenizer = None
    token_file_sha256 = None
    if args.tokenizer_json:
        from tokenizers import Tokenizer
        token_file_sha256 = hashlib.sha256(args.tokenizer_json.read_bytes()).hexdigest()
        require(args.tokenizer_sha256 == token_file_sha256, "Unexpected tokenizer file SHA-256")
        tokenizer = Tokenizer.from_file(str(args.tokenizer_json))
        tokenizer.no_truncation()
        tokenizer.no_padding()

    def read(path, *, measure_tokens=False):
        rows = {}
        with subprocess.Popen([*reader, str(path)], stdout=subprocess.PIPE, text=True, encoding="ascii") as proc:
            try:
                for line in proc.stdout:
                    row = dataset.decode_row(line)
                    key = dataset.identity(row)
                    require(key not in rows, "Duplicate sample key")
                    code = row["base_code"]
                    source = code.encode("utf-8")
                    # Line ending / trailing horizontal whitespace only; a text-block change can matter.
                    lines = code.splitlines()
                    layout = "\n".join(s.rstrip(" \t") for s in lines).encode("utf-8")
                    values = json.dumps([row[col] for col in dataset.COLUMNS], ensure_ascii=False,
                                        separators=(",", ":"), allow_nan=False).encode("utf-8")
                    count = len(tokenizer.encode(code, add_special_tokens=False).ids) if tokenizer and measure_tokens else None
                    rows[key] = Sample(hashlib.sha256(values).digest(), hashlib.sha256(source).digest(),
                                       hashlib.sha256(layout).digest(), row["has_text_conflict"],
                                       len(code), len(source), count, len(lines),
                                       any(s.startswith("\t") for s in lines), "\r\n" in code)
                require(proc.wait() == 0, f"Parquet schema or read failure in {path.name}")
            finally:
                if proc.poll() is None:
                    proc.kill()
                proc.stdout.close()
        return rows

    def check_stats(path, rows):
        out = cli("stats", path)
        def field(label):
            match = re.search(rf"^{label}: (.+)$", out, re.M)
            require(match, f"Missing CLI stats field {label}")
            return match[1].strip()
        pos = sum(s.positive for s in rows.values())
        require(int(field("Samples")) == len(rows) and int(field("Positives")) == pos,
                "stats counts differ from independent row read")
        rate = field("Positive rate")
        if rows:
            require(rate.endswith("%") and abs(float(rate[:-1]) - pos*100/len(rows)) <= .0050001,
                    "stats percentage is incorrect")
        else:
            require(rate == "N/A", "Expected N/A for empty dataset")
        return rate

    def hashes(rows):
        return {k: v.full_hash for k, v in rows.items()}

    result = {"schema_columns_validated": list(dataset.COLUMNS), "quantile_method": "nearest rank, row weighted",
              "tokenizer_json_sha256": token_file_sha256, "inputs": []}
    all_rows, seen_repos = {}, set()
    nonempty_file = None
    for path in args.inputs:
        records = read(path, measure_tokens=True)
        repo_ids = {key[0] for key in records}
        require(len(repo_ids) <= 1 and not repo_ids & seen_repos, "Expected one complete pilot per distinct repo_id")
        seen_repos.update(repo_ids)
        all_rows.update(records)
        if records:
            nonempty_file = path
        result["inputs"].append({"filename": path.name, "repo_id": next(iter(repo_ids), None),
                                 "stats_positive_rate_display": check_stats(path, records), **profile(records)})
    code_repos, layout_repos = defaultdict(set), defaultdict(set)
    for key, row in all_rows.items():
        code_repos[row.code_hash].add(key[0])
        layout_repos[row.layout_hash].add(key[0])
    result["code_hashes_at_multiple_repositories"] = sum(len(r) > 1 for r in code_repos.values())
    result["rows_matching_code_in_another_repository"] = sum(len(code_repos[r.code_hash]) > 1 for r in all_rows.values())
    result["layout_hashes_at_multiple_repositories"] = sum(len(r) > 1 for r in layout_repos.values())
    result["combined_profile"] = profile(all_rows)
    result["merged"] = None
    if len(args.inputs) >= 2:
        src = work / "combined.parquet"
        cli("merge", *args.inputs, "--output", src)
        merged = read(src)
        require(list(hashes(merged).items()) == list(hashes(all_rows).items()), "Merge changed order or row data")
        result["merged"] = {"full_rows_equal_in_input_order": True,
                            "stats_positive_rate_display": check_stats(src, merged)}
    else:
        src = args.inputs[0]
    if nonempty_file:
        invalid = work / "duplicates.parquet"
        cli("merge", nonempty_file, nonempty_file, "--output", invalid, error="Duplicate sample")
        require(not invalid.exists(), "Duplicate rejection left a published output")
    result["duplicate_control_rejected_without_output"] = True if nonempty_file else None
    invalid = work / "bad-schema.parquet"
    corrupt_schema(args.inputs[0], invalid)
    rejected = work / "invalid-result.parquet"
    cli("merge", invalid, src, "--output", rejected, error="Expected the 15-column Parquet schema")
    require(not rejected.exists(), "Schema rejection left a published output")
    result["invalid_schema_rejected_without_output"] = True

    a_dir = work / "a"
    cli("split", src, "--output-dir", a_dir)
    a = {n: read(a_dir / (n + ".parquet")) for n in SPLITS}
    flat = {k: v for rows in a.values() for k, v in rows.items()}
    require(sum(map(len, a.values())) == len(all_rows) and hashes(flat) == hashes(all_rows),
            "Splits changed a row or repeated a key")
    result["split_leakage"] = split_leakage(a)
    require(result["split_leakage"]["repo_and_path"]["groups_in_multiple_splits"] == 0, "Path leakage")
    result["split_rows"] = {n: {"rows": len(rows), "positives": sum(r.positive for r in rows.values()),
                                "by_repo": {repo: {"rows": sum(k[0] == repo for k in rows),
                                                  "positive": sum(k[0] == repo and v.positive for k,v in rows.items())}
                                            for repo in sorted(seen_repos)}} for n, rows in a.items()}
    result["strategies_identical_by_partition_all_fields"] = None
    if len(args.inputs) >= 2:
        dirs = [work / f"b-{i}" for i in range(len(args.inputs))]
        for path, target in zip(args.inputs, dirs):
            cli("split", path, "--output-dir", target)
        for name in SPLITS:
            dest = work / f"b-combined-{name}.parquet"
            cli("merge", *(d / (name + ".parquet") for d in dirs), "--output", dest)
            require(hashes(read(dest)) == hashes(a[name]), f"A/B produced different {name} membership/data")
        result["strategies_identical_by_partition_all_fields"] = True
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--jar", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--benchmarks", type=Path, default=Path("benchmarks"))
    parser.add_argument("--tokenizer-json", type=Path)
    parser.add_argument("--tokenizer-sha256", help="Pinned SHA-256 of the optional Qwen tokenizer.json")
    opts = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="aix-quality-") as tmp:
        output = run(opts, Path(tmp))
    opts.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
