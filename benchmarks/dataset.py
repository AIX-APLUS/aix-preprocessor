"""Read and compare logical records in a Sprint 0 Parquet dataset (Python 3.8+, JDK 17+)."""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
GOLDEN = HERE / "golden.json"
COLUMNS = (
    "repo_id", "merge_sha", "parent1_sha", "parent2_sha", "base_sha",
    "base_path", "base_blob_sha", "base_code", "commit_count_90d",
    "days_since_last_change", "author_count_90d", "top_author_share_90d",
    "lines_added_90d", "lines_deleted_90d", "has_text_conflict",
)


def identity(row):
    return row["repo_id"], row["merge_sha"], row["base_path"]


def read_golden(path):
    expected = {}
    for row in json.loads(Path(path).read_text(encoding="utf-8")):
        key = identity(row)
        if set(row) != set(COLUMNS) or key in expected:
            raise ValueError(f"Invalid golden fields or duplicate key: {key!r}")
        expected[key] = row
    return expected


def decode_row(line):
    fields = line.rstrip("\r\n").split("\t")
    if len(fields) != len(COLUMNS) or fields[-1] not in ("true", "false"):
        raise ValueError("Invalid output from the Parquet reader")
    values = [base64.b64decode(value, validate=True).decode("utf-8") for value in fields[:8]]
    values.extend(int(value) for value in fields[8:11])
    values.extend([float(fields[11]), int(fields[12]), int(fields[13]), fields[14] == "true"])
    return dict(zip(COLUMNS, values))


def summarize(rows, expected=None):
    """Hash full typed rows, retaining only identifiers and row digests in memory."""
    digests = {}
    positive = 0
    for row in rows:
        key = identity(row)
        if key in digests:
            raise ValueError(f"Duplicate sample: {key!r}")
        if expected is not None:
            if key not in expected:
                raise ValueError(f"Unexpected sample: {key!r}")
            changed = [name for name in COLUMNS if row[name] != expected[key][name]]
            if changed:
                raise ValueError(f"Changed sample {key!r}: {', '.join(changed)}")

        canonical = json.dumps([row[name] for name in COLUMNS], ensure_ascii=False,
                               separators=(",", ":"), allow_nan=False).encode("utf-8")
        digests[key] = hashlib.sha256(canonical).digest()
        positive += row["has_text_conflict"]
    if expected is not None and len(expected) != len(digests):
        missing = sorted(expected.keys() - digests.keys())
        raise ValueError(f"Missing {len(missing)} sample(s), first: {missing[0]!r}")

    digest = hashlib.sha256(b"aix-merge-sample-v1\n")
    for key in sorted(digests):
        digest.update(digests[key])
    return {"samples": len(digests), "positive": positive, "negative": len(digests) - positive,
            "logical_sha256": digest.hexdigest()}


def inspect_dataset(jar, parquet, *, java="java", golden=None):
    """Validate the footer schema and all records outside the extraction timer."""
    expected = read_golden(golden) if golden is not None else None
    command = [str(java), "--class-path", str(Path(jar).resolve()),
               str(HERE / "DumpParquet.java"), str(Path(parquet).resolve())]
    with subprocess.Popen(command, stdout=subprocess.PIPE, text=True, encoding="ascii") as reader:
        def records():
            for line in reader.stdout:
                yield decode_row(line)
            if reader.wait() != 0:
                raise RuntimeError(f"Parquet reader exited with status {reader.returncode}")

        try:
            return summarize(records(), expected)
        except BaseException:
            # A rejected row can leave a large writer blocked waiting for the pipe.
            if reader.poll() is None:
                reader.terminate()
            raise
        finally:
            reader.stdout.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parquet", type=Path)
    parser.add_argument("--jar", type=Path, default=HERE.parent / "build/libs/aix-preprocessor.jar")
    parser.add_argument("--java", default="java")
    parser.add_argument("--golden", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect_dataset(args.jar, args.parquet, java=args.java, golden=args.golden),
                     indent=2))
