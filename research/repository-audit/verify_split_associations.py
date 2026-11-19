"""Count shared merges in the pinned CLI's split outputs for Actions run 44549292132."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
BENCHMARKS = HERE.parents[1] / "benchmarks"
sys.path.insert(0, str(BENCHMARKS))
import dataset


def measure(split_dir, jar):
    runs = HERE / "evidence" / "runs"
    quality = json.loads((runs / "quality.json").read_bytes())
    rows_by_repo = defaultdict(list)
    labels_by_merge = defaultdict(list)
    splits_by_merge = defaultdict(set)
    split_by_path = {}
    part_rows = {}
    for part in ("train", "val", "test"):
        path = split_dir / (part + ".parquet")
        dump = subprocess.check_output(["java", "--class-path", str(jar.resolve()),
                                        str(BENCHMARKS / "DumpParquet.java"), str(path.resolve())],
                                       encoding="ascii")
        part_rows[part] = []
        for line in dump.splitlines():
            row = dataset.decode_row(line)
            repo, merge, path = dataset.identity(row)
            if split_by_path.setdefault((repo, path), part) != part:
                raise ValueError(f"{repo}/{path} appears in multiple splits")
            positive = row["has_text_conflict"]
            rows_by_repo[repo].append(row)
            labels_by_merge[repo, merge].append(positive)
            splits_by_merge[repo, merge].add(part)
            part_rows[part].append(((repo, merge), positive))
        expected = quality["split_rows"][part]
        rows = part_rows[part]
        if (len(rows), sum(pos for _, pos in rows)) != (expected["rows"], expected["positives"]):
            raise ValueError(f"{part} split counts differ from the archived counts")
        for repo, counts in expected["by_repo"].items():
            labels = [pos for (owner, _), pos in rows if owner == repo]
            if (len(labels), sum(labels)) != (counts["rows"], counts["positive"]):
                raise ValueError(f"{repo} {part} split counts differ from the archived counts")

    # The pinned schema reader checks all 15 columns. summarize rejects duplicate keys.
    expected_repos = {line.split()[1] for line in (HERE / "pins.tsv").read_text().splitlines()}
    if set(rows_by_repo) != expected_repos:
        raise ValueError("Split outputs do not cover exactly the five pinned repositories")
    for repo, rows in rows_by_repo.items():
        record = runs / ("pilot-" + repo.replace("/", "__") + ".json")
        if dataset.summarize(rows) != json.loads(record.read_bytes())["parquet_validation"]:
            raise ValueError(f"{repo} split rows differ from the archived typed rows")

    train_merges = {merge for merge, _ in part_rows["train"]}
    repeated = [labels for labels in labels_by_merge.values() if len(labels) > 1]
    return {
        "source_run": 44549292132,
        "verified_repository_digests": len(rows_by_repo),
        "merges_in_multiple_splits": sum(len(parts) > 1 for parts in splits_by_merge.values()),
        "multiple_row_merges": len(repeated),
        "multiple_row_merges_with_mixed_labels": sum(any(labels) and not all(labels) for labels in repeated),
        "splits": {part: {"rows": len(rows), "positives": sum(pos for _, pos in rows)}
                   for part, rows in part_rows.items()},
        "held_out": {
            part: {"merges": len({merge for merge, _ in rows}),
                   "merges_also_in_train": len({merge for merge, _ in rows} & train_merges),
                   "rows_whose_merge_is_in_train": sum(merge in train_merges for merge, _ in rows),
                   "positive_rows_whose_merge_is_in_train": sum(pos and merge in train_merges for merge, pos in rows)}
            for part, rows in part_rows.items() if part != "train"
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-dir", type=Path, required=True, help="fresh CLI split of the combined five pilot Parquets")
    parser.add_argument("--jar", type=Path, required=True, help="extractor JAR with Parquet dependencies")
    parser.add_argument("--check", type=Path, help="compare against a saved report")
    args = parser.parse_args()
    result = measure(args.split_dir, args.jar)
    if args.check and json.loads(args.check.read_bytes()) != result:
        raise SystemExit("Split association evidence mismatch")
    print(json.dumps(result, indent=2))
