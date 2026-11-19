"""Replay a bounded, complete ancestral prefix with the unmodified AIX extractor."""

import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time


def process(args, **options):
    return subprocess.run([str(a) for a in args], capture_output=True, **options)


def run(args):
    p = process(args)
    if p.returncode:
        raise RuntimeError(f"{args[0:3]} failed ({p.returncode}): "
                           + p.stderr.decode("utf-8", "replace")[-3000:])
    return p.stdout


def git(repo, *args):
    return run(["git", "-C", repo, *args])


def refs(repo):
    return git(repo, "for-each-ref", "--format=%(objectname) %(refname)").decode().splitlines()


def byte_size(repo):
    return sum(p.stat().st_size for p in repo.rglob("*") if p.is_file())


def git_count(repo, rev, *args):
    return int(git(repo, "rev-list", "--count", *args, rev))


def choose_anchor(graph, tip, wanted, max_commits, max_merges):
    # Selection uses only topology. Reversed first-parent order follows one linear lineage.
    milestones = git(graph, "rev-list", "--reverse", "--first-parent", "--min-parents=2",
                     "--max-parents=2", tip).decode().splitlines()
    if not milestones:
        if (git_count(graph, tip) > max_commits or
                git_count(graph, tip, "--min-parents=2", "--max-parents=2") > max_merges):
            raise ValueError("no eligible first-parent anchor within policy; no extraction")
        return tip, 0, 0
    index = min(len(milestones), wanted)
    while index:
        sha = milestones[index - 1]
        if git_count(graph, sha) <= max_commits and git_count(
                graph, sha, "--min-parents=2", "--max-parents=2") <= max_merges:
            return sha, index, len(milestones)
        index //= 2
    raise ValueError("even first milestone exceeds the registered resource cap; no extraction")


def java_edits(repo, base, tip):
    parts = iter(git(repo, "diff", "--raw", "-z", "--no-abbrev", "--find-renames",
                     "--no-ext-diff", base, tip).split(b"\0"))
    result = set()
    for header in parts:
        if not header:
            break
        oldmode, newmode, old_id, new_id, status = header.split()
        original = next(parts).decode("utf-8", "replace")
        dest = next(parts).decode("utf-8", "replace") if status[:1] in (b"R", b"C") else original
        if (status[:1] in (b"R", b"M") and oldmode.startswith(b":100")
                and newmode.startswith(b"100") and old_id != new_id
                and "\ufffd" not in original and "\ufffd" not in dest
                and original.endswith(".java") and dest.endswith(".java")):
            result.add(original)
    return result


def funnel(repo):
    merges = git(repo, "rev-list", "--all", "--parents", "--min-parents=2",
                 "--max-parents=2").decode().splitlines()
    counters = dict.fromkeys(["two_parent_merges", "zero_base", "multiple_bases",
                              "unique_base", "parent_is_base", "left_has_no_java_edit",
                              "no_joint_java_edit", "merges_with_joint_edits",
                              "joint_java_file_occurrences"], 0)
    counters["two_parent_merges"] = len(merges)
    for merge in merges:
        _, first, second = merge.split()
        call = process(["git", "-C", repo, "merge-base", "--all", first, second])
        if call.returncode not in (0, 1):
            raise RuntimeError(call.stderr.decode("utf-8", "replace"))
        bases = call.stdout.decode().splitlines()
        if len(bases) != 1:
            counters["multiple_bases" if bases else "zero_base"] += 1
            continue
        counters["unique_base"] += 1
        base = bases[0]
        if base in (first, second):
            counters["parent_is_base"] += 1
            continue
        left = java_edits(repo, base, first)
        if not left:
            counters["left_has_no_java_edit"] += 1
            continue
        overlap = left.intersection(java_edits(repo, base, second))
        if not overlap:
            counters["no_joint_java_edit"] += 1
            continue
        counters["merges_with_joint_edits"] += 1
        counters["joint_java_file_occurrences"] += len(overlap)
    return counters


def main(args, meta):
    source = args.source.resolve()
    work = args.work.resolve()
    data = work / "datasets"
    data.mkdir(parents=True, exist_ok=True)
    jar = args.jar.resolve() if args.jar else source / "build" / "libs" / "aix-preprocessor.jar"
    if not jar.is_file():
        raise FileNotFoundError(jar)
    label = args.repository.replace("/", "__")
    root = work / label
    root.mkdir(exist_ok=False)
    url = f"https://github.com/{args.repository}.git"
    tip = args.tip
    meta.update(extractor_sha=git(source, "rev-parse", "HEAD").decode().strip(),
                git_version=run(["git", "--version"]).decode().strip(),
                java_version=process(["java", "-version"]).stderr.decode().strip(),
                python_version=platform.python_version(), platform=platform.platform(), cpu=os.cpu_count(),
                disk_free_at_start=shutil.disk_usage(root).free, threads=args.threads,
                anchor_policy={"first_parent_two_parent_milestone": args.milestone,
                               "max_reachable_commits": args.max_commits,
                               "max_reachable_two_parent_merges": args.max_merges})
    graph = args.graph.resolve() if args.graph else root / "graph.git"
    if not args.graph:
        run(["git", "init", "--bare", graph])
        git(graph, "-c", "gc.auto=0", "fetch", "--no-tags", "--filter=tree:0", url, tip)
    if git(graph, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise ValueError("shallow graph")
    if git(graph, "rev-parse", tip + "^{commit}").decode().strip() != tip:
        raise ValueError("unavailable pinned default commit")
    anchor, index, num = choose_anchor(graph, tip, args.milestone, args.max_commits, args.max_merges)
    meta.update(pilot_anchor=anchor, milestone_used=index, available_first_parent_milestones=num)
    input_repo = root / "input.git"
    run(["git", "init", "--bare", input_repo])
    git(input_repo, "symbolic-ref", "HEAD", "refs/heads/pilot")
    # A *new*, full fetch: no shallow boundaries, no filters, no original branches/tags.
    git(input_repo, "-c", "gc.auto=0", "fetch", "--no-tags", url, f"{anchor}:refs/heads/pilot")
    reference = refs(input_repo)
    if reference != [f"{anchor} refs/heads/pilot"]:
        raise ValueError(f"unexpected refs {reference}")
    if git(input_repo, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise ValueError("shallow pilot input")
    git(input_repo, "fsck", "--connectivity-only", "--no-dangling")
    meta.update(analyzed_refs=reference, pilot_git_bytes=byte_size(input_repo),
                pilot_total_commits=git_count(input_repo, "--all"),
                pilot_all_merges=git_count(input_repo, "--all", "--min-parents=2"),
                pilot_octopus_merges=git_count(input_repo, "--all", "--min-parents=3"),
                pilot_tip_committed_at=git(input_repo, "show", "-s", "--format=%cI", anchor).decode().strip())
    # Keep simultaneous runs in independent temp/output parents; expose only validated input to combine.
    dataset = root / "pilot.parquet"
    cmd = ["java", "-Xmx2g", "-jar", jar, "extract", input_repo, "--threads",
           args.threads, "--repo-id", args.repository, "--output", dataset]
    rss = root / "peak-kib.txt"
    if sys.platform.startswith("linux") and Path("/usr/bin/time").is_file():
        cmd = ["/usr/bin/time", "-f", "%M", "-o", rss, *cmd]
    started = time.perf_counter()
    execution = process(cmd)
    if rss.exists() and execution.returncode == 0:
        meta["max_process_rss_kib"] = int(rss.read_text().strip())
    meta.update(extraction_seconds=round(time.perf_counter() - started, 6),
                extraction_exit=execution.returncode,
                extraction_stderr=execution.stderr.decode("utf-8", "replace")[-8000:])
    if execution.returncode != 0:
        raise RuntimeError(f"extract exit {execution.returncode}: {meta['extraction_stderr']}")
    meta.update(parquet_bytes=dataset.stat().st_size, stats_stdout=run(
        ["java", "-jar", jar, "stats", dataset]).decode().strip())
    lines = meta["stats_stdout"].splitlines()
    rows = int(next(line.removeprefix("Samples: ") for line in lines if line.startswith("Samples: ")))
    positives = int(next(line.removeprefix("Positives: ") for line in lines if line.startswith("Positives: ")))
    meta.update(eligible_samples=rows, positive_samples=positives, negative_samples=rows - positives,
                positive_rate=positives / rows if rows else None)
    sys.path.insert(0, str(source / "benchmarks"))
    import dataset as parquet
    verified = parquet.inspect_dataset(jar, dataset)
    if (verified["samples"], verified["positive"]) != (rows, positives):
        raise ValueError("CLI stats and independent Parquet counts differ")
    meta.update(parquet_validation=verified, parquet_schema_columns=list(parquet.COLUMNS),
                funnel=funnel(input_repo))
    skip_match = re.search(r"Skips: \{([^}]*)\}", meta["extraction_stderr"])
    skips = dict((name, int(count)) for name, count in re.findall(
        r"(?:^|, )([^=]+)=(\d+)", skip_match.group(1) if skip_match else ""))
    if meta["funnel"]["joint_java_file_occurrences"] != rows + sum(
            value for key, value in skips.items() if key != "no unique merge base"):
        raise ValueError("candidate funnel and production counts differ")
    meta.update(reported_skips=skips, source_refs_preserved=reference == refs(input_repo),
                output_temp_clean=not any(root.glob(".aix-*")))
    if not meta["source_refs_preserved"] or not meta["output_temp_clean"]:
        raise ValueError("source refs changed or extraction temp directory remained")
    os.link(dataset, data / (label + ".parquet"))
    meta["status"] = "success"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run"])
    parser.add_argument("repository", help="owner/repo")
    parser.add_argument("tip", help="observed full default branch commit SHA")
    parser.add_argument("--source", default=Path.cwd(), type=Path, help="pinned extractor checkout")
    parser.add_argument("--jar", type=Path)
    parser.add_argument("--work", type=Path, required=True, help="private scratch, one clean directory per run")
    parser.add_argument("--out", type=Path, required=True, help="aggregate JSON directory")
    parser.add_argument("--graph", type=Path, help="optional existing complete-ancestry Git graph containing tip")
    parser.add_argument("--milestone", type=int, default=100)
    parser.add_argument("--max-commits", type=int, default=14000)
    parser.add_argument("--max-merges", type=int, default=450)
    parser.add_argument("--threads", type=int, default=2)
    arg = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", arg.repository):
        parser.error("invalid owner/repo")
    if not re.fullmatch("[0-9a-f]{40}", arg.tip):
        parser.error("tip must be a 40-character lowercase Git commit SHA")
    if min(arg.milestone, arg.max_commits, arg.max_merges, arg.threads) < 1:
        parser.error("all numeric options must be positive")
    arg.out.mkdir(parents=True, exist_ok=True)
    result = {"repository": arg.repository, "default_tip": arg.tip, "status": "failed",
              "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    path = arg.out / ("pilot-" + arg.repository.replace("/", "__") + ".json")
    if path.exists():
        raise FileExistsError(path)
    try:
        main(arg, result)
    except Exception as error:
        result["error"] = str(error)
        raise
    finally:
        # A hard timeout may interrupt any write. Publish only a closed, complete JSON, exclusively.
        fp = tempfile.NamedTemporaryFile(mode="w", dir=arg.out, encoding="utf-8", delete=False)
        try:
            with fp:
                json.dump(result, fp, ensure_ascii=False, indent=2)
                fp.write("\n")
            if os.name == "nt":
                os.rename(fp.name, path)  # Windows rename fails if the destination exists.
            else:
                os.link(fp.name, path)
        finally:
            Path(fp.name).unlink(missing_ok=True)
