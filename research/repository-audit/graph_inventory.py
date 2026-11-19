"""Inventory complete commit ancestry with a tree-less, non-shallow fetch."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from datetime import datetime, timezone


def utc(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")


def inventory(args):
    repo = args.work_dir.resolve()
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", args.repository):
        raise ValueError("expected owner/name")
    if not re.fullmatch(r"[0-9a-f]{40}", args.sha):
        raise ValueError("expected a full SHA-1")
    repo.mkdir(parents=True, exist_ok=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_NO_REPLACE_OBJECTS": "1"}

    def git(*cli, check=True):
        return subprocess.run(["git", "-C", str(repo), *cli], env=env, check=check,
                              capture_output=True, encoding="utf-8", errors="replace")

    def run(*cli):
        proc = git(*cli, check=False)
        if proc.returncode:
            raise RuntimeError(f"git {cli[0]} ({proc.returncode}): {proc.stderr}")
        return proc.stdout.strip()

    git_version = run("version")
    started = time.monotonic()
    run("init", "--bare", "--initial-branch", args.branch, ".")
    run("remote", "add", "origin", f"https://github.com/{args.repository}.git")
    run("config", "--unset-all", "remote.origin.fetch")
    run("config", "remote.origin.promisor", "true")
    run("config", "remote.origin.partialclonefilter", "tree:0")
    run("fetch", "--no-tags", "--no-write-fetch-head", "--filter=tree:0", "origin",
        "+refs/heads/*:refs/heads/*", "+refs/tags/*:refs/tags/*")
    ref_snapshot = utc(time.time())
    fetch_seconds = time.monotonic() - started
    if run("rev-parse", "--is-shallow-repository") != "false":
        raise ValueError("shallow input")
    # Never add a local ref for the pinned commit; --all represents advertised heads/tags.
    if git("cat-file", "-e", f"{args.sha}^{{commit}}", check=False).returncode:
        run("fetch", "--no-tags", "--no-write-fetch-head", "--filter=tree:0", "origin", args.sha)
    refs = run("for-each-ref", "--sort=refname", "--format=%(refname)%09%(objectname)",
               "refs/heads/", "refs/tags/") + "\n"
    manifest = args.output.with_suffix(".refs.tsv.gz")
    with manifest.open("xb") as f:
        f.write(gzip.compress(refs.encode(), mtime=0))
    run("commit-graph", "write", "--reachable")
    # Parent SHA pairs suffice for merge-base. No tree, blob or checkout is needed.
    merged = {}
    if args.skip_merge_bases:
        merge_counts = {"unique": None, "multiple": None, "none": None}
    else:
        merge_counts = {"unique": 0, "multiple": 0, "none": 0}
    recent_from = int(datetime.fromisoformat(args.recent_from.replace("Z", "+00:00")).timestamp())

    def scope(revision):
        dates = []
        two = octopus = 0
        bases = dict(merge_counts)
        for line in run("rev-list", "--timestamp", "--parents", revision).splitlines():
            stamp, sha, *parents = line.split()
            dates.append(int(stamp))
            if len(parents) > 2:
                octopus += 1
            if len(parents) != 2:
                continue
            two += 1
            if args.skip_merge_bases:
                continue
            if sha not in merged:
                result = git("merge-base", "--all", *parents, check=False)
                if result.returncode not in (0, 1) or (result.returncode == 1 and result.stdout.strip()):
                    raise RuntimeError(f"merge-base {sha}: {result.stderr}")
                nbase = len(result.stdout.splitlines())
                merged[sha] = "none" if nbase == 0 else "unique" if nbase == 1 else "multiple"
            bases[merged[sha]] += 1
        return {"total_commits": len(dates), "two_parent_merges": two, "octopus_merges": octopus,
                "all_merge_commits": two + octopus, "two_parent_merge_bases": bases,
                "oldest_committer_time": utc(min(dates)), "newest_committer_time": utc(max(dates)),
                "commits_since_recent_from": sum(t >= recent_from for t in dates)}

    default = scope(args.sha)
    all_refs = scope("--all")
    files = (p for p in repo.rglob("*") if p.is_file())
    payload = {"repository": args.repository, "pinned_default_sha": args.sha,
               "default_branch": args.branch, "fetched_default_tip": run("rev-parse", "refs/heads/" + args.branch),
               "default": default, "all_heads_tags": all_refs,
               "fetch_refspecs": ["refs/heads/*", "refs/tags/*"], "shallow": False,
               "filter": "tree:0", "recent_from_inclusive": args.recent_from,
               "fetched_at_utc": ref_snapshot, "evidence_url": f"https://github.com/{args.repository}/commit/{args.sha}",
               "head_count": sum(line.startswith("refs/heads/") for line in refs.splitlines()),
               "tag_count": sum(line.startswith("refs/tags/") for line in refs.splitlines()),
               "ref_manifest": manifest.name, "refs_uncompressed_sha256": hashlib.sha256(refs.encode()).hexdigest(),
               "metadata_mirror_file_bytes": sum(p.stat().st_size for p in files),
               "git_version": git_version, "fetch_seconds": round(fetch_seconds, 3),
               "inventory_seconds": round(time.monotonic() - started, 3)}
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--recent-from", default="2026-10-20T00:00:00Z")
    parser.add_argument("--skip-merge-bases", action="store_true")
    inventory(parser.parse_args())
