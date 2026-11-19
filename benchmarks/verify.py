"""Run the packaged extraction CLI on the fixed Git history and compare every field."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from dataset import GOLDEN, inspect_dataset
from fixture import create_fixture


def git(repo, *args):
    # Caller GIT_DIR / GIT_INDEX_FILE must never redirect the staged fixture edit.
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_ATTR_NOSYSTEM="1")
    return subprocess.check_output(["git", "--no-optional-locks", "-C", str(repo), *args], env=env)


def snapshot(repo):
    # Keep exact bytes of every file in this tiny working tree, including untracked files.
    files = {p.relative_to(repo).as_posix(): p.read_bytes() for p in repo.rglob("*")
             if ".git" not in p.relative_to(repo).parts and p.is_file()}
    return {
        "head": git(repo, "symbolic-ref", "HEAD"),
        "refs": git(repo, "show-ref", "--head"),
        "objects": sorted(git(repo, "cat-file", "--batch-all-objects",
                              "--batch-check=%(objectname)").splitlines()),
        "index_entries": git(repo, "ls-files", "--stage", "-z"),
        "config": (repo / ".git/config").read_bytes(),
        "files": files,
    }


def verify(jar, java):
    with tempfile.TemporaryDirectory(prefix="aix-golden-") as directory:
        root = Path(directory)
        repo = create_fixture(root / "repo")
        # Include staged, unstaged, and untracked state in the non-mutation check.
        tracked = repo / "OneSide.java"
        tracked.write_bytes(b"// staged edit\n")
        git(repo, "add", "--", "OneSide.java")
        tracked.write_bytes(b"// later unstaged edit\n")
        (repo / "local-only.txt").write_bytes(b"private working copy\n")
        initial = snapshot(repo)
        observations = []
        for threads in (1, 4):
            parquet = root / f"threads-{threads}.parquet"
            try:
                subprocess.run([java, "-jar", str(jar), "extract", str(repo), "--threads",
                                str(threads), "--repo-id", "sprint0/fixture",
                                "--output", str(parquet)], check=True)
            finally:
                after = snapshot(repo)
                changed = [field for field in initial if after[field] != initial[field]]
                if changed:
                    raise AssertionError(f"Source repository changed: {changed}")
            report = inspect_dataset(jar, parquet, java=java, golden=GOLDEN)
            if (report["samples"], report["positive"], report["negative"]) != (4, 2, 2):
                raise AssertionError(f"Unexpected fixture counts: {report}")
            # A diagnostic only. Row order and container metadata may legitimately vary.
            byte_hash = hashlib.sha256(parquet.read_bytes()).hexdigest()
            observations.append(dict(threads=threads, file_sha256=byte_hash, **report))
        if observations[0]["logical_sha256"] != observations[1]["logical_sha256"]:
            raise AssertionError("Thread counts produced different logical data")
        return observations


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", type=Path, default=Path("build/libs/aix-preprocessor.jar"))
    parser.add_argument("--java", default="java")
    args = parser.parse_args()
    print(json.dumps(verify(args.jar.resolve(strict=True), args.java), indent=2))
