"""Join two historical license observations to hash-matched pilot Parquet records."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
BENCHMARKS = HERE.parents[1] / "benchmarks"
sys.path.insert(0, str(BENCHMARKS))
import dataset


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def inspect(pilot, historical, parquet, java, jar):
    repository = pilot["repository"]
    matches = []
    positive_paths = set()
    checks = {} if not historical else {
        (repository, historical["observed_merge"], f["path"]): f
        for f in historical["source_checks"]
        if f["sha"] == historical["github_reported_merge_base"] and f["path"].endswith(".java")
    }

    def visit(lines):
        for line in lines:
            row = dataset.decode_row(line)
            if row["repo_id"] != repository:
                raise ValueError(f"Unexpected repo_id in {parquet.name}")
            if row["has_text_conflict"]:
                positive_paths.add(row["base_path"])
            key = dataset.identity(row)
            if key in checks:
                checked = checks[key]
                source = row["base_code"].encode("utf-8")
                sha256 = hashlib.sha256(source).hexdigest()
                git_sha = hashlib.sha1(f"blob {len(source)}\0".encode("ascii") + source).hexdigest()
                matches.append({
                    "sample_key_repo_merge_path": list(key), "base_sha": row["base_sha"],
                    "base_blob_sha": row["base_blob_sha"], "base_code_sha256": sha256,
                    "parents_in_order": [row["parent1_sha"], row["parent2_sha"]],
                    "has_text_conflict": row["has_text_conflict"], "source_url": checked["url"],
                    "observed_notice": checked["observed_notice"],
                    "parents_match": [row["parent1_sha"], row["parent2_sha"]] == historical["two_parents"],
                    "base_matches": row["base_sha"] == checked["sha"],
                    "blob_matches": git_sha == row["base_blob_sha"] == checked["git_blob_sha"],
                    "source_bytes_match": sha256 == checked["sha256"] and len(source) == checked["bytes"],
                })
            yield row

    command = [str(java), "--class-path", str(jar.resolve()), str(BENCHMARKS / "DumpParquet.java"),
               str(parquet.resolve())]
    with subprocess.Popen(command, stdout=subprocess.PIPE, text=True, encoding="ascii") as process:
        try:
            logical = dataset.summarize(visit(process.stdout))
            if process.wait():
                raise RuntimeError(f"Parquet reader failed on {parquet.name}")
        finally:
            if process.poll() is None:
                process.kill()
            process.stdout.close()
    if logical != pilot["parquet_validation"]:
        raise ValueError(f"Logical data differs from workflow for {repository}")
    fields = ("parents_match", "base_matches", "blob_matches", "source_bytes_match")
    if len(matches) != len(checks) or any(not all(m[f] for f in fields) for m in matches):
        raise ValueError(f"Historical source observations did not match {repository}")
    return {"repository": repository, "pilot_anchor": pilot["pilot_anchor"],
            "reference": "runs/pilot-" + parquet.stem + ".json", "logical_validation": logical,
            "unique_positive_base_paths": len(positive_paths), "historical_keys_checked": len(checks),
            "matched": matches}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet-dir", required=True, type=Path, help="owner__repo.parquet inputs")
    parser.add_argument("--jar", required=True, type=Path)
    parser.add_argument("--java", default="java")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    ev = HERE / "evidence"
    history = load(ev / "historical-license-spot-check.json")
    checks = {r["repository"]: r for r in history["repositories"]}
    entries = []
    for path in sorted((ev / "runs").glob("pilot-*.json")):
        if path.name.endswith(".quality.json"):
            continue
        pilot = load(path)
        repo = pilot["repository"]
        spot = checks.get(repo)
        if spot and pilot["pilot_anchor"] != spot["pilot_anchor"]:
            raise ValueError(f"Historical anchor differs from workflow for {repo}")
        entries.append(inspect(pilot, spot, args.parquet_dir / (repo.replace("/", "__") + ".parquet"),
                               args.java, args.jar))
    if len(entries) != 5:
        raise ValueError("Expected the five frozen pilot inputs")
    result = {"workflow_run_id": history["workflow_run_id"], "artifact_id": history["artifact_id"],
              "scope": "Local replay data whose 15-column canonical logical digests and class counts "
                       "match Ubuntu pilot aggregates; distinct positive base_path strings per repository. "
                       "Header evidence covers only the matched historical source files.",
              "repositories": entries}
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_bytes(text.encode("utf-8"))
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
