"""Run the packaged extraction CLI on the fixed Git history and compare every field."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
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
    """Describe the tiny disposable fixture, including the physical files under .git."""
    entries = {}
    pending = [repo]
    while pending:
        path = pending.pop()
        info = path.lstat()
        mode = info.st_mode
        attributes = getattr(info, "st_file_attributes", 0)
        reparse_point = attributes and attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
        if stat.S_ISLNK(mode) or reparse_point:
            # Include dangling links and Windows junctions without reading outside the fixture.
            content = os.readlink(path)
        elif stat.S_ISDIR(mode):
            pending.extend(path.iterdir())
            content = None
        elif stat.S_ISREG(mode):
            content = hashlib.sha256(path.read_bytes()).digest()
        else:
            raise ValueError(f"Unexpected fixture entry: {path}")
        # Reading can change access times. Compare names, types, mode/readonly and content.
        readonly = bool(attributes and attributes & stat.FILE_ATTRIBUTE_READONLY)
        entries[path.relative_to(repo).as_posix()] = (mode, readonly, content)
    return entries


def check_workspace(repo, initial, output_dir):
    after = snapshot(repo)
    changed = sorted(path for path in initial.keys() | after.keys()
                     if initial.get(path) != after.get(path))
    if changed:
        raise AssertionError(f"Source repository changed: {changed}")
    leftovers = [entry.name for entry in output_dir.glob(".aix-*")]
    if leftovers:
        raise AssertionError(f"Temporary extraction paths remain: {leftovers}")


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
        command = [java, "-jar", str(jar), "extract", str(repo), "--repo-id", "sprint0/fixture"]
        for threads in (1, 4):
            parquet = root / f"threads-{threads}.parquet"
            try:
                subprocess.run([*command, "--threads", str(threads), "--output", str(parquet)], check=True)
            except subprocess.CalledProcessError as failed:
                if parquet.is_file():
                    # A late cleanup failure can follow a successful atomic publication.
                    published = inspect_dataset(jar, parquet, java=java, golden=GOLDEN)
                    print(f"CLI exited {failed.returncode} with a published Parquet: {published}", flush=True)
                raise
            finally:
                check_workspace(repo, initial, root)
            report = inspect_dataset(jar, parquet, java=java, golden=GOLDEN)
            if (report["samples"], report["positive"], report["negative"]) != (4, 2, 2):
                raise AssertionError(f"Unexpected fixture counts: {report}")
            # A diagnostic only. Row order and container metadata may legitimately vary.
            byte_hash = hashlib.sha256(parquet.read_bytes()).hexdigest()
            observations.append(dict(threads=threads, file_sha256=byte_hash, **report))
        if observations[0]["logical_sha256"] != observations[1]["logical_sha256"]:
            raise AssertionError("Thread counts produced different logical data")

        # A distinct sentinel detects a clobber even if repeated extractions produce identical bytes.
        existing = root / "existing.parquet"
        sentinel = b"pre-existing output\n"
        existing.write_bytes(sentinel)
        refused = subprocess.run([*command, "--threads", "1", "--output", str(existing)],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if refused.returncode == 0 or existing.read_bytes() != sentinel:
            raise AssertionError(f"Existing output was accepted or changed (exit {refused.returncode})")
        if b"FileAlreadyExistsException" not in refused.stdout:
            raise AssertionError(f"Unexpected failure with existing output: {refused.stdout!r}")
        check_workspace(repo, initial, root)
        return observations


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", type=Path, default=Path("build/libs/aix-preprocessor.jar"))
    parser.add_argument("--java", default="java")
    args = parser.parse_args()
    print(json.dumps(verify(args.jar.resolve(strict=True), args.java), indent=2))
