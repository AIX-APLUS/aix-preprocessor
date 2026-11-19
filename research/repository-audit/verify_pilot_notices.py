"""Count explicit historical Java notices in the five hash-matched pilot datasets."""

import argparse
from collections import defaultdict
import io
import json
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
BENCHMARKS = HERE.parents[1] / "benchmarks"
sys.path.insert(0, str(BENCHMARKS))
import dataset


def notice(code):
    # Stop at the first Java token so string literals cannot count as notices.
    header = re.match(r"(?:\s+|/\*.*?\*/|//[^\n]*)*", code[:6000].lstrip("\ufeff"), re.S).group()
    header = re.sub(r"(?m)^\s*//", " ", header)
    header = " ".join(header.replace("*", " ").lower().split())
    for name, version, label in (
        ("gnu general public license", "2", "GPL-2.0-or-later"),
        ("gnu general public license", "3", "GPL-3.0-or-later"),
        ("gnu lesser general public license", "2.1", "LGPL-2.1-or-later"),
    ):
        if name in header and f"version {version} of the license, or (at your option) any later version" in header:
            return label
    if "licensed under the apache license, version 2.0" in header:
        return "Apache-2.0"
    if "permission is hereby granted, free of charge" in header and "without restriction" in header:
        return "MIT"
    return "no listed notice matched"


def count(pilot, parquet, git_dir, jar, java):
    repo = pilot["repository"]
    dump = subprocess.check_output([java, "--class-path", str(jar.resolve()), str(BENCHMARKS / "DumpParquet.java"),
                                    str(parquet.resolve())], encoding="ascii")
    rows = [dataset.decode_row(line) for line in dump.splitlines()]
    logical = dataset.summarize(rows)
    if logical != pilot["parquet_validation"] or any(r["repo_id"] != repo for r in rows):
        raise ValueError(f"{repo}: Parquet differs from the archived Ubuntu pilot")

    # Resolve the path in its historical tree and read the exact Git blob for each sample.
    specs = [f"{r['base_sha']}:{r['base_path']}" for r in rows]
    if any("\n" in spec or "\r" in spec for spec in specs):
        raise ValueError("newline in Git batch query")
    blobs = io.BytesIO(subprocess.check_output(["git", "-C", str(git_dir), "cat-file", "--batch"],
                                               input=("\n".join(specs) + "\n").encode()))
    groups = defaultdict(list)
    byte_matches = 0
    for row in rows:
        fields = blobs.readline().split()
        if len(fields) != 3:
            raise ValueError(f"{repo}: Git blob unavailable for {row['base_sha']}:{row['base_path']}")
        sha, kind, size = fields
        content = blobs.read(int(size))
        if (kind != b"blob" or sha.decode() != row["base_blob_sha"] or blobs.read(1) != b"\n"
                or content.decode("utf-8", errors="replace") != row["base_code"]):
            raise ValueError(f"{repo}: historical Git file differs at {dataset.identity(row)}")
        byte_matches += content == row["base_code"].encode("utf-8")
        groups[notice(row["base_code"])].append(row)
    notices = {}
    for label, group in sorted(groups.items()):
        positives = [row for row in group if row["has_text_conflict"]]
        example = min(positives or group, key=dataset.identity)
        notices[label] = {
            "rows": len(group), "positive": len(positives),
            "distinct_positive_paths": len({r["base_path"] for r in positives}),
            "example": {f: example[f] for f in ("merge_sha", "base_sha", "base_path", "base_blob_sha")},
        }
    return {**logical, "source_texts_matched": len(rows), "source_utf8_bytes_matched": byte_matches,
            "distinct_positive_paths": len({r["base_path"] for r in rows if r["has_text_conflict"]}),
            "notices": notices}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet-dir", required=True, type=Path)
    parser.add_argument("--jar", required=True, type=Path)
    parser.add_argument("--java", default="java")
    parser.add_argument("--git-dir", nargs=2, action="append", metavar=("OWNER/REPO", "PATH"), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    git_dirs = dict(args.git_dir)
    pilots = [json.loads(path.read_bytes()) for path in sorted((HERE / "evidence/runs").glob("pilot-*.json"))]
    if len(pilots) != 5 or set(git_dirs) != {p["repository"] for p in pilots} or len(args.git_dir) != 5:
        parser.error("supply one local Git directory for each of the five archived pilots")
    result = {"run_id": 44549292132, "artifact_id": 14543915089,
              "scope": "Listed notice markers in leading complete comments in the first 6000 Unicode characters of base_code. "
                       "Each repeated sample counts separately. No inference about unmarked files or permissions.",
              "repositories": {}}
    for pilot in pilots:
        repo = pilot["repository"]
        parquet = args.parquet_dir / (repo.replace("/", "__") + ".parquet")
        result["repositories"][repo] = count(pilot, parquet, git_dirs[repo], args.jar, args.java)
    encoded = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_bytes(encoded.encode())
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
