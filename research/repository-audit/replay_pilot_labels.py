"""Replay the five archived pilot label sets from their complete single-ref Git inputs."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

AUDIT = Path(__file__).resolve().parent
BENCHMARKS = AUDIT.parents[1] / "benchmarks"
sys.path.insert(0, str(BENCHMARKS))
import dataset


def check(condition, detail):
    if not condition:
        raise ValueError(detail)


def changed_blobs(git, base, parent):
    raw = git("diff-tree", "-r", "--no-commit-id", "--raw", "-z", "--no-abbrev",
              "--find-renames", "--no-ext-diff", base, parent).stdout
    fields = iter(raw.split(b"\0")[:-1])
    changes = {}
    for header in fields:
        old_mode, new_mode, old_id, new_id, status = header.split()
        original = next(fields)
        dest = next(fields) if status[:1] in (b"R", b"C") else original
        if (status[:1] in (b"M", b"R") and old_mode.startswith(b":100") and new_mode.startswith(b"100")
                and original.endswith(b".java") and dest.endswith(b".java") and old_id != new_id):
            names = [name.decode("utf-8", "replace") for name in (original, dest)]
            if all("\ufffd" not in name for name in names):
                changes[names[0]] = (names[1], old_id.decode(), new_id.decode())
    return changes


def tree_conflicts(git, first, second):
    output = git("merge-tree", "--write-tree", "--name-only", "-z", first, second, ok=(0, 1))
    if output.returncode == 0:
        return set(), set()
    fields = iter(output.stdout.decode("utf-8", "replace").split("\0")[:-1])
    next(fields)  # merged tree ID
    unmerged = set(iter(lambda: next(fields), ""))
    text, other = set(), set()
    for count in fields:
        paths = [next(fields) for _ in range(int(count))]
        kind = next(fields)
        next(fields)  # human-readable message
        if kind == "CONFLICT (contents)":
            text.update(paths)
        elif kind != "Auto-merging":
            other.update(paths)
    return text, other | (unmerged - text)


def replay(bare, scratch, pilots, args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(LC_ALL="C", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_ATTR_NOSYSTEM="1",
               GIT_OBJECT_DIRECTORY=str(scratch), GIT_ALTERNATE_OBJECT_DIRECTORIES=str(bare / "objects"))

    def git(*argv, ok=(0,)):
        p = subprocess.run(["git", "--git-dir", str(bare), *argv], capture_output=True, env=env)
        if p.returncode not in ok:
            raise RuntimeError(f"git {argv} -> {p.returncode}: {p.stderr!r}")
        return p

    refs = git("for-each-ref", "--format=%(objectname) %(refname)").stdout.decode().splitlines()
    check(len(refs) == 1, f"{bare}: expected one ref, got {refs}")
    pilot = pilots[refs[0].split()[0]]
    repo = pilot["repository"]
    check(refs == pilot["analyzed_refs"], f"{repo}: wrong refs {refs}")
    parquet = args.datasets / (repo.replace("/", "__") + ".parquet")
    dump = subprocess.check_output([args.java, "--class-path", str(args.jar.resolve()),
                                    str(BENCHMARKS / "DumpParquet.java"), str(parquet.resolve())])
    rows = [dataset.decode_row(line) for line in dump.decode("ascii").splitlines()]
    checked = dataset.summarize(rows)  # rejects duplicate keys and hashes all 15 fields
    check(checked == pilot["parquet_validation"], f"{repo}: input differs from Ubuntu")
    expected = {dataset.identity(row): row for row in rows}
    seen = set()
    merges = git("rev-list", "--parents", "--min-parents=2", "--max-parents=2", pilot["pilot_anchor"])
    revisions = merges.stdout.decode().splitlines()
    check(len(revisions) == pilot["funnel"]["two_parent_merges"], f"{repo}: wrong history range")
    for revision in revisions:
        merge, first, second = revision.split()
        bases = git("merge-base", "--all", first, second, ok=(0, 1)).stdout.decode().split()
        if len(bases) != 1 or bases[0] in (first, second):
            continue
        base = bases[0]
        left = changed_blobs(git, base, first)
        if not left:
            continue
        right = changed_blobs(git, base, second)
        joint = left.keys() & right.keys()
        if not joint:
            continue
        conflicts, excluded = tree_conflicts(git, first, second)
        for path in joint:
            key = repo, merge, path
            left_path, blob, left_blob = left[path]
            right_path, right_base, right_blob = right[path]
            names = {path, left_path, right_path}
            # The archived pilots recorded no post-intersection exclusions. Fail on any difference.
            check(key in expected and not names & excluded, f"new or excluded candidate: {key}")
            row = expected[key]
            check([first, second, base, blob] == [row[c] for c in dataset.COLUMNS[2:5] + ("base_blob_sha",)]
                  and right_base == blob, f"wrong ancestry or base blob: {key}")
            code = row["base_code"].encode("utf-8")
            check(hashlib.sha1(b"blob " + str(len(code)).encode() + b"\0" + code).hexdigest() == blob,
                  f"base source differs from its Git object: {key}")
            check(bool(names & conflicts) == row["has_text_conflict"], f"merge-tree label: {key}")
            # Git returns 1..127 conflict hunks; fatal/binary/error exits are not labels.
            file_merge = git("merge-file", "--object-id", "--stdout", left_blob, blob, right_blob, ok=range(128))
            check(not file_merge.stderr and (file_merge.returncode > 0) == row["has_text_conflict"],
                  f"merge-file label or diagnostic: {key}, {file_merge.stderr!r}")
            seen.add(key)
    check(seen == expected.keys(), f"{repo}: missing {len(expected.keys() - seen)} rows")
    check(len(seen) == pilot["funnel"]["joint_java_file_occurrences"], f"{repo}: candidate count")
    return repo, {"anchor": pilot["pilot_anchor"], "two_parent_merges": len(revisions), **checked,
                  "candidate_keys_recovered": len(seen), "merge_tree_labels_matched": len(seen),
                  "merge_file_labels_matched": len(seen)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bare-dirs", required=True, type=Path, nargs=5)
    parser.add_argument("--datasets", required=True, type=Path, help="owner__repo.parquet directory")
    parser.add_argument("--jar", required=True, type=Path, help="extractor Parquet reader dependencies")
    parser.add_argument("--java", default="java")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    pilots = {}
    for path in (AUDIT / "evidence/runs").glob("pilot-*.json"):
        pilot = json.loads(path.read_bytes())
        pilots[pilot["pilot_anchor"]] = pilot
    with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for i, bare in enumerate(args.bare_dirs):
            scratch = Path(tmp) / str(i)
            scratch.mkdir()
            futures.append(executor.submit(replay, bare.resolve(), scratch, pilots, args))
        verified = dict(future.result() for future in futures)
    check(set(verified) == {p["repository"] for p in pilots.values()}, "incomplete repository set")
    report = {"source_run": 44549292132, "git_version": subprocess.check_output(["git", "--version"], text=True).strip(),
              "scope": "Single archived pilot ref per repository, default rename limit, labels from Git text merges.",
              "repositories": dict(sorted(verified.items()))}
    args.output.write_bytes((json.dumps(report, indent=2) + "\n").encode())


if __name__ == "__main__":
    main()
