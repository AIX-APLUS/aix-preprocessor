"""Time the unmodified extractor CLI against pinned local refs (Python 3.10+)."""

import argparse
from collections import deque
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
import tempfile
import time

from dataset import inspect_dataset
from fixture import create_fixture


HERE = Path(__file__).resolve().parent
SUMMARY = re.compile(r"(\d+) two-parent merges, (\d+) samples, (\d+) positives\. Skips: \{(.*)\}")


def git(repo, *args, checkout_config=False):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    if checkout_config:
        # Git status must use the checkout's real line-ending, attribute and ignore rules.
        # Keep its configuration sources, but never redirect the selected repository or index.
        env.update({k: v for k, v in os.environ.items()
                    if k.upper().startswith("GIT_CONFIG_") or k.upper() == "GIT_ATTR_NOSYSTEM"})
    else:
        # Dataset commands share the extractor's isolation from system/global config.
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_ATTR_NOSYSTEM="1")
    env.update(GIT_OPTIONAL_LOCKS="0", LC_ALL="C")
    return subprocess.check_output(["git", "-C", str(repo), *args], env=env,
                                   stderr=subprocess.DEVNULL if checkout_config else None)


def checkout_state(repo):
    # This identifies the harness checkout. The separately supplied JAR is identified by its bytes.
    try:
        top = git(repo, "rev-parse", "--show-toplevel", checkout_config=True)
        if not Path(os.fsdecode(top).rstrip("\r\n")).samefile(repo):
            return {"head": None, "dirty": None}
        head = git(repo, "rev-parse", "--verify", "HEAD", checkout_config=True)
        changes = git(repo, "status", "--porcelain", "--untracked-files=all", "-z", checkout_config=True)
    except (OSError, subprocess.CalledProcessError):
        return {"head": None, "dirty": None}
    return {"head": head.decode("ascii").strip(), "dirty": bool(changes)}


def manifest(repo):
    refs = git(repo, "for-each-ref", "--sort=refname", "--format=%(objectname) %(refname)")
    return {
        "refs": refs.decode("utf-8", errors="backslashreplace").splitlines(),
        "refs_sha256": hashlib.sha256(refs.replace(b"\r\n", b"\n")).hexdigest(),
        "head": git(repo, "rev-parse", "HEAD").decode("ascii").strip(),
    }


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hardware():
    cpu = platform.processor() or None
    memory = None
    if sys.platform.startswith("linux"):
        info = Path("/proc/cpuinfo")
        if info.is_file():
            for line in info.read_text(errors="replace").splitlines():
                if line.startswith("model name"):
                    cpu = line.partition(":")[2].strip()
                    break
        memory = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    elif os.name == "nt":
        import ctypes
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                cpu = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
        except OSError:
            pass  # The benchmark also runs with restricted registry permissions.

        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (field, ctypes.c_ulonglong) for field in
                ("total_physical", "available_physical", "total_page", "available_page",
                 "total_virtual", "available_virtual", "available_extended")]

        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            memory = status.total_physical
    return {"cpu": cpu, "logical_cpus": os.cpu_count(), "host_memory_bytes": memory}


def describe(values):
    return {"min": min(values), "median": statistics.median(values), "max": max(values),
            "sample_stdev": statistics.stdev(values) if len(values) > 1 else None}


def one_run(record, args, repo, repo_id, work, merges, golden, reference):
    parquet = work / "trial.parquet"
    log = work / "trial.log"
    command = [args.java, "-jar", str(args.jar), "extract", str(repo),
               "--repo-id", repo_id, "--threads", str(record["threads"]), "--output", str(parquet)]
    with log.open("wb") as out:
        start = time.perf_counter_ns()
        process = subprocess.run(command, stdout=out, stderr=subprocess.STDOUT)
        elapsed = (time.perf_counter_ns() - start) / 1e9
    record.update(exit_code=process.returncode, seconds=elapsed)
    counts = None
    tail = deque(maxlen=30)
    with log.open(encoding="utf-8", errors="replace") as out:
        for line in out:
            tail.append(line.rstrip())
            match = SUMMARY.fullmatch(line.rstrip())
            if match:
                counts = tuple(map(int, match.groups()[:3]))
                skip_text = match.group(4)
                record["reported_skips"] = {
                    reason: int(n) for reason, n in
                    (pair.rsplit("=", 1) for pair in skip_text.split(", ") if pair)
                }
    if process.returncode or counts is None:
        raise RuntimeError(f"CLI exit {process.returncode}, summary {counts}.\n" + "\n".join(tail))

    inspected = inspect_dataset(args.jar, parquet, java=args.java, golden=golden)
    expected = (merges, inspected["samples"], inspected["positive"])
    if counts != expected or inspected["negative"] != counts[1] - counts[2]:
        raise ValueError(f"CLI counts {counts} disagree with rev-list/Parquet {expected}")
    record.update(inspected, merges=merges, parquet_bytes=parquet.stat().st_size,
                  merges_per_second=merges / elapsed, samples_per_second=counts[1] / elapsed)
    if args.expect_samples is not None and inspected["samples"] != args.expect_samples:
        raise ValueError(f"Expected {args.expect_samples} samples, found {inspected['samples']}")
    if args.expect_logical_sha256 is not None and inspected["logical_sha256"] != args.expect_logical_sha256:
        raise ValueError(f"Logical SHA-256 differs from expected {args.expect_logical_sha256}")
    if reference is not None and reference != inspected["logical_sha256"]:
        raise ValueError("Logical dataset differs from the first trial")
    parquet.unlink()
    record["success"] = True
    return inspected["logical_sha256"]


def summarize(runs, *, complete):
    summary = {}
    threads = sorted({r["threads"] for r in runs if r["phase"] == "measured"})
    for t in threads:
        measured = [r for r in runs if r["phase"] == "measured" and r["threads"] == t]
        verified = [r for r in measured if r["success"]]
        group = {"verified": len(verified), "failed": len(measured) - len(verified)}
        # If any trial, cleanup or final input check failed, keep observations but withhold statistics.
        if complete and verified:
            for key in ("seconds", "merges_per_second", "samples_per_second"):
                group[key] = describe([r[key] for r in verified])
        summary[str(t)] = group
    return summary


def write_report(path, data):
    # Destination is exclusively claimed in main. Keep the previous checkpoint
    # readable even if a long external benchmark is interrupted during a write.
    with tempfile.NamedTemporaryFile("w", dir=path.parent, encoding="utf-8",
                                     delete=False) as output:
        name = Path(output.name)
        json.dump(data, output, indent=2, ensure_ascii=True, allow_nan=False)
        output.write("\n")
    try:
        os.replace(name, path)
    finally:
        name.unlink(missing_ok=True)


def run(args, work, result):
    if not args.jar.is_file():
        raise FileNotFoundError(f"Build the shadow JAR first: {args.jar}")
    java = subprocess.run([args.java, "-version"], capture_output=True, check=True)
    result["environment"] = {
        "platform": platform.platform(), "machine": platform.machine(), **hardware(),
        "python": platform.python_version(),
        "git": git(work, "--version").decode().strip(),
        "java": (java.stdout + java.stderr).decode(errors="replace").strip(),
        "jar_sha256": sha256_file(args.jar),
    }
    repo = work / "input"
    repo_id = args.repo_id or "sprint0/fixture"
    golden = None
    if args.repo:
        if git(args.repo, "rev-parse", "--is-shallow-repository").strip() != b"false":
            raise ValueError("A full local repository is required")
        input_refs = manifest(args.repo)
        # Pin every ref once in a disposable bare repository. The source is
        # only read; keep its object database present until all trials finish.
        git(work, "clone", "--quiet", "--mirror", "--shared", "--", str(args.repo), str(repo))
    else:
        create_fixture(repo)
        input_refs = manifest(repo)
        golden = HERE / "golden.json"
    if manifest(repo) != input_refs:
        raise ValueError("Snapshot does not match input HEAD and refs")
    merges = int(git(repo, "rev-list", "--all", "--min-parents=2", "--max-parents=2", "--count"))
    result["input"] = dict(input_refs, kind="local snapshot" if args.repo else "fixture",
                           repo_id=repo_id, two_parent_merges=merges)
    reference = None
    try:
        for phase, rounds in (("warmup", args.warmups), ("measured", args.repeats)):
            for i in range(rounds):
                # Rotate the starting thread count between rounds.
                start = i % len(args.threads)
                for threads in args.threads[start:] + args.threads[:start]:
                    trial = {"phase": phase, "round": i + 1, "threads": threads, "success": False}
                    result["runs"].append(trial)
                    print(f"{phase} {i + 1}, threads={threads}", flush=True)
                    try:
                        reference = one_run(trial, args, repo, repo_id, work, merges, golden, reference)
                    except Exception as exc:
                        trial["error"] = str(exc)
                        raise
                    write_report(args.report, result)
    finally:
        result["snapshot_refs_unchanged"] = manifest(repo) == input_refs
        if args.repo:
            result["source_refs_unchanged"] = manifest(args.repo) == input_refs
    if not result["snapshot_refs_unchanged"] or not result.get("source_refs_unchanged", True):
        raise RuntimeError("Input refs changed during the benchmark")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", type=Path, default=HERE.parent / "build/libs/aix-preprocessor.jar")
    parser.add_argument("--java", default="java")
    parser.add_argument("--threads", type=int, nargs="+", default=[1, 2])
    parser.add_argument("--warmups", type=int, default=1, help="fresh-JVM warmups per thread count")
    parser.add_argument("--repeats", type=int, default=3, help="measured fresh JVMs per thread count")
    parser.add_argument("--repo", type=Path, help="existing full local repository (default: fixture)")
    parser.add_argument("--repo-id", help="stable dataset ID (required with --repo)")
    parser.add_argument("--expect-samples", type=int, help="required row count on every trial")
    parser.add_argument("--expect-logical-sha256", type=str.lower,
                        help="required logical digest on every trial, including the first")
    parser.add_argument("--report", type=Path, required=True, help="new JSON report path")
    args = parser.parse_args()
    if args.repeats < 1 or args.warmups < 0 or min(args.threads) < 1:
        parser.error("repeats and threads must be positive; warmups must be non-negative")
    if args.expect_samples is not None and args.expect_samples < 0:
        parser.error("--expect-samples must be non-negative")
    if args.expect_logical_sha256 is not None and not re.fullmatch("[0-9a-f]{64}", args.expect_logical_sha256):
        parser.error("--expect-logical-sha256 requires 64 hexadecimal digits")
    if len(set(args.threads)) != len(args.threads):
        parser.error("thread counts must be distinct")
    if args.repo and not args.repo_id:
        parser.error("--repo requires a stable --repo-id")
    if not args.repo and args.repo_id not in (None, "sprint0/fixture"):
        parser.error("the fixture golden requires --repo-id sprint0/fixture")
    args.jar = args.jar.resolve()
    args.report = args.report.resolve()
    if args.repo:
        args.repo = args.repo.resolve()
        for destination in (args.report, Path(tempfile.gettempdir()).resolve()):
            if destination.is_relative_to(args.repo):
                parser.error("keep reports and temporary files outside the input repository")
    # Sample the checkout before creating a report that could itself appear as an untracked file.
    checkout = checkout_state(HERE.parent)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    try:
        args.report.touch(exist_ok=False)
    except FileExistsError:
        parser.error(f"report already exists: {args.report}")
    result = {"format_version": 2, "started_utc": datetime.now(timezone.utc).isoformat(),
              "success": False, "threads": args.threads,
              "benchmark_checkout": checkout,
              "validation": {"fixture_golden": args.repo is None,
                             "expected_samples": args.expect_samples,
                             "expected_logical_sha256": args.expect_logical_sha256,
                             "repeatability_only": bool(args.repo and args.expect_samples is None
                                                        and args.expect_logical_sha256 is None)},
              "warmups_per_setting": args.warmups, "repeats_per_setting": args.repeats, "runs": [],
              "timing": "whole fresh JVM CLI, including JIT, mirror, Parquet publication and cleanup",
              "cache": "OS/filesystem caches uncontrolled; no cache flush between warmup or measured runs",
              "unmeasured": {"peak_memory": "no process-tree memory instrumentation",
                             "git_calls": "no wrapper or tracing during timed runs",
                             "stage_times": "no production probes"}}
    try:
        with tempfile.TemporaryDirectory(prefix="aix-bench-") as name:
            run(args, Path(name), result)
        result["success"] = True
    except (Exception, KeyboardInterrupt) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        print(result["error"], file=sys.stderr)
    finally:
        result["summary_by_threads"] = summarize(result["runs"], complete=result["success"])
        write_report(args.report, result)
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
