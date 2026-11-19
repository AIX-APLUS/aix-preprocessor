"""Verify run 44549292132 from its small artifacts; the runner alone read the Parquets."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "benchmarks"))
from dataset import COLUMNS

EXTRACTOR = "06e755ebabed1707a3413ec99ffa2511b046c543"
THRESHOLDS = (4096, 8192, 32768)


def require(test, detail):
    if not test:
        raise ValueError(detail)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def checked_ratio(value, numerator, denominator):
    if not denominator:
        require(value is None, "undefined rate must be null")
    else:
        require(value is not None and math.isclose(value, numerator / denominator, rel_tol=1e-12),
                f"invalid fraction {value} for {numerator}/{denominator}")


def above_token_bounds(profile, threshold):
    """Bound strictly longer rows using the observed values of ordered observations."""
    n = profile["rows"]
    lengths = profile["base_code_tokens"]
    # quality.py uses the nearest-rank definition for each row-weighted quantile.
    lower, upper = 0, n
    for key, rank in (("min", 1), ("p50", (50*n+99)//100), ("p90", (90*n+99)//100),
                      ("p95", (95*n+99)//100), ("max", n)):
        if lengths[key] > threshold:
            lower = max(lower, n - rank + 1)
        else:
            upper = min(upper, n - rank)
    require(lower <= upper, "inconsistent token quantiles")
    return [lower, upper]


def verify_graph(run, slug, repo, branch, tip):
    graph = load(run / (slug + ".json"))
    require((graph["repository"], graph["default_branch"], graph["pinned_default_sha"])
            == (repo, branch, tip), "graph identity")
    require(graph["shallow"] is False and graph["fetch_refspecs"] == ["refs/heads/*", "refs/tags/*"],
            "graph scope")
    for scope in (graph["default"], graph["all_heads_tags"]):
        two = scope["two_parent_merges"]
        require(two + scope["octopus_merges"] == scope["all_merge_commits"] <= scope["total_commits"],
                "graph merge counts")
        require(sum(scope["two_parent_merge_bases"].values()) == two, "graph merge-base counts")
    raw = gzip.decompress((run / graph["ref_manifest"]).read_bytes())
    require(hashlib.sha256(raw).hexdigest() == graph["refs_uncompressed_sha256"], "graph ref digest")
    refs = dict(line.split("\t") for line in raw.decode("utf-8").splitlines())
    require(len(refs) == graph["head_count"] + graph["tag_count"] == len(raw.splitlines()),
            "graph ref manifest counts")
    require(refs["refs/heads/" + branch] == graph["fetched_default_tip"], "fetched branch manifest")
    return graph


def verify_pilot(run, repo, tip, profile, graph, ancestry):
    pilot = load(run / ("pilot-" + repo.replace("/", "__") + ".json"))
    require(pilot["repository"] == repo and pilot["default_tip"] == tip and
            pilot["extractor_sha"] == EXTRACTOR, "pilot identity")
    anchor = pilot["pilot_anchor"]
    require(re.fullmatch("[0-9a-f]{40}", anchor) and
            pilot["analyzed_refs"] == [anchor + " refs/heads/pilot"], "actual extract ref")
    require((ancestry["base"], ancestry["head"], ancestry["status"], ancestry["behind_by"])
            == (anchor, tip, "ahead", 0), "GitHub anchor reachability")
    require(ancestry["ahead_by"] + pilot["pilot_total_commits"] == graph["default"]["total_commits"],
            "GitHub ancestry delta differs from the two recorded history sizes")
    require(pilot["status"] == "success" and pilot["extraction_exit"] == 0 and
            pilot["source_refs_preserved"] is True and pilot["output_temp_clean"] is True,
            "extraction or cleanup failed")
    require(pilot["parquet_bytes"] > 0 and pilot["extraction_seconds"] > 0 and
            pilot["max_process_rss_kib"] > 0, "missing run measurements")
    require(pilot["parquet_schema_columns"] == list(COLUMNS), "Parquet schema")
    rows, pos, neg = (pilot[key] for key in ("eligible_samples", "positive_samples", "negative_samples"))
    require(min(rows, pos, neg) >= 0 and pos + neg == rows, "label counts")
    checked_ratio(pilot["positive_rate"], pos, rows)
    checked_ratio(profile["positive_fraction"], pos, rows)
    validation = pilot["parquet_validation"]
    require(re.fullmatch("[a-f0-9]{64}", validation["logical_sha256"]), "missing typed row digest")
    require((rows, pos, neg) == tuple(validation[k] for k in ("samples", "positive", "negative"))
            == tuple(profile[k] for k in ("rows", "positive", "negative")), "independent row counts")
    display_rate = profile["stats_positive_rate_display"]
    require(abs(float(display_rate.rstrip("%")) - 100 * pos / rows) <= .0050001,
            "CLI percentage")
    require(pilot["stats_stdout"].splitlines() == [f"Samples: {rows}", f"Positives: {pos}",
            "Positive rate: " + display_rate], "stats CLI disagrees")
    funnel = pilot["funnel"]
    two = funnel["two_parent_merges"]
    require(re.search(rf"^{two} two-parent merges, {rows} samples, {pos} positives\.",
                      pilot["extraction_stderr"], re.M), "extract stderr disagrees")
    require(two + pilot["pilot_octopus_merges"] == pilot["pilot_all_merges"] <= pilot["pilot_total_commits"]
            and pilot["pilot_total_commits"] <= graph["default"]["total_commits"], "pilot merge scope")
    caps = pilot["anchor_policy"]
    require(two <= caps["max_reachable_two_parent_merges"] and
            pilot["pilot_total_commits"] <= caps["max_reachable_commits"], "pilot cap")
    skipped_base = funnel["zero_base"] + funnel["multiple_bases"]
    require(skipped_base + funnel["unique_base"] == two and
            pilot["reported_skips"].get("no unique merge base", 0) == skipped_base, "base losses")
    require(sum(funnel[k] for k in ("parent_is_base", "left_has_no_java_edit", "no_joint_java_edit",
            "merges_with_joint_edits")) == funnel["unique_base"], "merge losses")
    file_skips = sum(v for k, v in pilot["reported_skips"].items() if k != "no unique merge base")
    require(funnel["joint_java_file_occurrences"] == rows + file_skips, "candidate file losses")
    require(profile["contributing_merges"] <= funnel["merges_with_joint_edits"], "yielding merges")
    if file_skips == 0:
        require(profile["contributing_merges"] == funnel["merges_with_joint_edits"], "all eligible overlaps")
    return {
        "repository": repo, "pilot_anchor": anchor, "rows": rows, "positive": pos, "negative": neg,
        "all_contributing_merges": profile["contributing_merges"],
        "distinct_positive_merges": 0 if not pos else None,
        "unique_paths": profile["unique_paths"], "rows_on_repeated_paths": profile["rows_on_repeated_paths"],
        "rows_per_two_parent_merge": rows / two,
        "positives_per_two_parent_merge": pos / two,
        "rows_per_timed_extraction_second": rows / pilot["extraction_seconds"],
        "strictly_longer_base_code_rows_bounds": {
            str(t): above_token_bounds(profile, t) for t in THRESHOLDS
        },
        "logical_sha256": validation["logical_sha256"]
    }


def verify(evidence):
    run = evidence / "runs"
    quality = load(run / "quality.json")
    require(quality["schema_columns_validated"] == list(COLUMNS) and len(COLUMNS) == 15,
            "aggregate schema order")
    require(quality["duplicate_control_rejected_without_output"] is True and
            quality["invalid_schema_rejected_without_output"] is True and
            quality["merged"]["full_rows_equal_in_input_order"] is True and
            quality["strategies_identical_by_partition_all_fields"] is True, "failed control")
    require(quality["quantile_method"] == "nearest rank, row weighted" and
            quality["tokenizer_json_sha256"] == "c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539",
            "unexpected quantile or tokenizer")
    pins = [line.split() for line in (HERE / "pins.tsv").read_text().splitlines() if line.strip()]
    profiles = {p["repo_id"]: p for p in quality["inputs"]}
    ancestry = {row["repository"]: row for row in
                load(evidence / "validation" / "anchor-ancestry.json")["comparisons"]}
    require(len(profiles) == len(quality["inputs"]) == len(pins) == 5 and
            set(profiles) == {repo for slug, repo, branch, tip in pins}, "quality input scope")
    records = []
    for slug, repo, branch, tip in pins:
        try:
            graph = verify_graph(run, slug, repo, branch, tip)
            require(profiles[repo]["filename"] == repo.replace("/", "__") + ".parquet", "quality filename")
            records.append(verify_pilot(run, repo, tip, profiles[repo], graph, ancestry[repo]))
        except (ValueError, KeyError) as err:
            raise ValueError(f"{repo}: {err}") from err
    combined = quality["combined_profile"]
    for key in ("rows", "positive", "negative", "contributing_merges", "unique_paths", "rows_on_repeated_paths"):
        require(combined[key] == sum(p[key] for p in profiles.values()), "combined " + key)
    checked_ratio(combined["positive_fraction"], combined["positive"], combined["rows"])
    parts = quality["split_rows"]
    require(set(parts) == {"train", "val", "test"}, "split names")
    for name, partition in parts.items():
        require(set(partition["by_repo"]) == set(profiles), name + " repositories")
        for key, group_key in (("rows", "rows"), ("positives", "positive")):
            require(partition[key] == sum(p[group_key] for p in partition["by_repo"].values()), name + " counts")
    for repo, prof in profiles.items():
        for key in ("rows", "positive"):
            require(sum(p["by_repo"][repo][key] for p in parts.values()) == prof[key], "split totals")
    bounds = {}
    for t in THRESHOLDS:
        lo, hi = above_token_bounds(combined, t)
        by_repo = [r["strictly_longer_base_code_rows_bounds"][str(t)] for r in records]
        bounds[str(t)] = [max(lo, sum(b[0] for b in by_repo)), min(hi, sum(b[1] for b in by_repo))]
        require(bounds[str(t)][0] <= bounds[str(t)][1], "aggregate length bounds")
    return {"workflow_run_id": 44549292132, "aggregate_artifact_id": 14543915089,
            "parquet_inspection": "On runner; local checks use its stats, typed row digests and quality aggregates.",
            "repositories": records, "combined": {
                "rows": combined["rows"], "positive": combined["positive"], "negative": combined["negative"],
                "strictly_longer_base_code_rows_bounds": bounds,
                "unique_paths": combined["unique_paths"], "contributing_merges": combined["contributing_merges"],
                "history_feature_distributions": None,
                "positive_contributing_merges": None}}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence", default=HERE / "evidence", type=Path)
    output = p.add_mutually_exclusive_group()
    output.add_argument("--output", type=Path, help="Write recalculated aggregate (UTF-8, LF)")
    output.add_argument("--check", type=Path, help="Fail if the saved aggregate differs")
    args = p.parse_args()
    result = verify(args.evidence)
    if args.check:
        require(result == load(args.check), "saved validation aggregate differs")
        print("Verified five pilot scopes, graph manifests, Parquet summaries, split totals and saved aggregate.")
    elif args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))
    else:
        print(json.dumps(result, indent=2))
