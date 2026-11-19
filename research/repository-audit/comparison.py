"""Join observed scopes by canonical owner/repo. Unobserved values stay null."""
import argparse
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def nullable(path):
    return read(path) if path.exists() else {}


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def pilot_measurements(repo, study, profile, columns):
    """The producer validated the Parquet itself; here we cross-check its two reports."""
    anchor = study["pilot_anchor"]
    rows, positive, negative = (study[k] for k in ("eligible_samples", "positive_samples", "negative_samples"))
    counts = (rows, positive, negative)
    validation = study["parquet_validation"]
    if (study["analyzed_refs"] != [f"{anchor} refs/heads/pilot"] or
            study["extraction_exit"] != 0 or not study["source_refs_preserved"]):
        raise ValueError("Unexpected extraction input or exit: " + repo)
    if (rows != positive + negative or study["positive_rate"] != ratio(positive, rows) or
            counts != tuple(validation[k] for k in ("samples", "positive", "negative")) or
            counts != tuple(profile[k] for k in ("rows", "positive", "negative"))):
        raise ValueError("Parquet counts disagree: " + repo)
    if len(columns) != 15 or columns != study["parquet_schema_columns"]:
        raise ValueError("Parquet and quality schemas disagree: " + repo)
    funnel = study["funnel"]
    merges = funnel["two_parent_merges"]
    seconds = study["extraction_seconds"]
    return {
        "pilot_total_commits": study["pilot_total_commits"],
        "pilot_all_merges": study["pilot_all_merges"],
        "pilot_octopus_merges": study["pilot_octopus_merges"],
        "pilot_tip_committed_at": study["pilot_tip_committed_at"],
        "pilot_anchor_policy": study["anchor_policy"],
        "pilot_milestone_used": study["milestone_used"],
        "pilot_funnel": funnel, "reported_skips": study["reported_skips"],
        "efficiency": {
            "rows_per_pilot_two_parent_merge": ratio(rows, merges),
            "positives_per_pilot_two_parent_merge": ratio(positive, merges),
            "rows_per_extraction_second": ratio(rows, seconds),
            "positives_per_extraction_second": ratio(positive, seconds),
        },
        "parquet_validation": validation,
        "schema_columns_validated": columns,
        "duplicate_sample_keys_in_pilot": 0,  # inspect_dataset fails on any repeated identity.
        "pilot_quality": {
            "measurement_source": "Ubuntu Actions aggregate-pilot-results (quality.json and pilot JSON)",
            **profile,
            "positive_contributing_merges": 0 if positive == 0 else None,
            "history_feature_distributions": None,
        },
        "full_default_rows": None, "full_default_positive": None, "full_default_positive_rate": None,
    }


def add_remeasurement(record, replay, source):
    """Only attach new metrics if the re-extracted dataset matches the Actions rows."""
    expected = (record["pilot_sha"], record["parquet_validation"]["logical_sha256"],
                record["eligible_samples"], record["positive_samples"], record["negative_samples"])
    observed = tuple(replay[k] for k in ("pilot_anchor", "logical_sha256", "rows", "positive_rows", "negative_rows"))
    repo = record["repository"]
    if expected != observed:
        raise ValueError("Local remeasurement does not match the archived dataset: " + repo)
    positive_merges = replay["unique_positive_merges"]
    positives = record["positive_samples"]
    if (bool(positive_merges) != bool(positives) or
            not 0 <= positive_merges <= min(positives, record["pilot_quality"]["contributing_merges"])):
        raise ValueError("Impossible distinct positive merge count: " + repo)
    if set(replay["history_features"]) != set(record["schema_columns_validated"][8:14]):
        raise ValueError("Missing or unexpected history features: " + repo)
    bounds = record["pilot_quality"].get("strictly_longer_base_code_rows_bounds", {})
    for cutoff, (low, high) in bounds.items():
        if not low <= replay["base_code_tokens_gt"][cutoff] <= high:
            raise ValueError(f"Exact token count exceeds the archived quantile bounds: {repo}, {cutoff}")
    record["pilot_remeasurement"] = {"measurement_source": source, **replay}
    record["evidence"].append(source)


def screened_candidate(repo, url, tip, branch, license_name, size_kib, commits, java_paths, screening, evidence):
    """API observations describe a screen; they do not establish extraction outcomes."""
    return {
        "record_type": "supplementary_candidate", "repository": repo, "github_url": url,
        "pinned_sha": tip, "default_branch": branch, "github_license_metadata": license_name,
        "github_size_kib": size_kib, "total_commits": commits,
        "total_commits_source": "github_rest" if commits is not None else None, "java_paths_at_tip": java_paths,
        "two_parent_merges": None, "pilot_sha": None, "pilot_two_parent_merges": None,
        "eligible_samples": None, "positive_samples": None, "negative_samples": None,
        "positive_rate": None, "extraction_seconds": None, "max_process_rss_kib": None,
        "parquet_bytes": None, "extraction_status": "unmeasured",
        "screening": screening, "evidence": evidence,
    }


def original_supplementary(evidence):
    source = "supplementary-screen.json"
    followup = "supplementary-followup/inventory.json"
    first = read(evidence / source)
    updates = {r["repo"]: r for r in nullable(evidence / followup).get("repositories", [])}
    for record in first["repositories"]:
        repo = record["repo"]
        checks = [item for item in first["both_parent_path_checks"] if item["repo"] == repo]
        later = updates.get(repo, {})
        if later and later["sha"] != record["sha"]:
            raise ValueError("Supplementary follow-up pin mismatch: " + repo)
        windows = [
            {"name": w["until"] or "pinned_tip", "commits": w["sample_n"],
             "two_parent": w["parent_count_histogram"].get("2", 0)}
            for w in record["windows"]
        ]
        links = ["evidence/" + source]
        if later:
            links.append("evidence/" + followup)
        screening = {
            "java_bytes": later.get("java_bytes"),
            "java_bytes_scope": "regular Java blob paths at the pinned tree" if later.get("java_bytes") is not None else None,
            "windows": windows,
            "bilateral_checked_merges": later.get("bilateral_checked_merges", len(checks)),
            "bilateral_merges_with_observed_paths": later.get("bilateral_merges_with_observed_paths"),
            "bilateral_path_pairs_observed_lower_bound": later.get(
                "bilateral_path_pairs_observed_lower_bound", sum(len(item["common"]) for item in checks) if checks else None),
            "isolated_text_probe_positive": later.get("isolated_text_probe_positive"),
            "isolated_text_probe_negative": later.get("isolated_text_probe_negative"),
        }
        yield screened_candidate(
            repo, "https://github.com/" + repo, record["sha"], record["branch"], record["license"],
            record["size_kib"], later.get("reachable_commits_pinned_api"), later.get("java_regular_paths"),
            screening, links,
        )


def additional_supplementary(evidence):
    source = "additional/screen.json"
    probe_source = "additional/text-probe.json"
    probes = nullable(evidence / probe_source).get("observations", [])
    for record in nullable(evidence / source).get("repositories", []):
        repo = record["repository"]
        checks = record["overlaps"]
        repo_probes = [p["file_text_conflict"] for p in probes if p["repo"] == repo]
        screening = {
            "java_bytes": record["java_bytes_at_pin"],
            "java_bytes_scope": "Java blob paths at the pinned tree",
            "windows": [{k: w[k] for k in ("name", "commits", "two_parent")} for w in record["windows"]],
            "bilateral_checked_merges": len(checks),
            "bilateral_merges_with_observed_paths": sum(bool(c["both_modified_java"]) for c in checks),
            "bilateral_path_pairs_observed_lower_bound": sum(len(c["both_modified_java"]) for c in checks),
            "comparisons_capped_or_failed": sum(c["capped_or_failed"] for c in checks),
            "isolated_text_probe_positive": repo_probes.count(True) if repo_probes else None,
            "isolated_text_probe_negative": repo_probes.count(False) if repo_probes else None,
        }
        links = ["evidence/" + source]
        if repo_probes:
            links.append("evidence/" + probe_source)
        yield screened_candidate(
            repo, record["url"], record["pin"], record["default_branch"], record["github_license_spdx_snapshot"],
            record["repo_size_kib_snapshot"], record["commits_at_pin"], record["java_files_at_pin"], screening, links,
        )


def collect(evidence):
    defaults = {r["repo"]: r for r in read(evidence / "github-default-evidence.json")["repos"]}
    refs = {r["repository"]: r for r in read(evidence / "api-refs/inventory.json")["repositories"]}
    current = {r["repository"]: r for r in read(evidence / "recent-parent-counts.json")["repositories"]}
    overlaps = {r["repository"]: r for r in read(evidence / "recent-overlaps.json")["repositories"]}
    provenance_name = "run-44549292132-provenance.json"
    provenance = nullable(evidence / provenance_name)
    artifacts = {a["name"]: a["id"] for a in provenance.get("artifacts", [])}
    quality = nullable(evidence / "runs/quality.json")
    profiles = {r["filename"]: r for r in quality.get("inputs", [])}
    integrity_source = "validation/pilot-integrity.json"
    integrity = {r["repository"]: r for r in nullable(evidence / integrity_source).get("repositories", [])}
    notice_source = "validation/pilot-notices.json"
    notices = nullable(evidence / notice_source).get("repositories", {})
    replay_source = "pilot-enrichment.json"
    enrichment = nullable(evidence / replay_source)
    replays = enrichment.get("repositories", {})
    if replays and (enrichment["source_run"] != provenance["run_id"] or
                    enrichment["tokenizer"]["tokenizer_json_sha256"] != quality["tokenizer_json_sha256"]):
        raise ValueError("Re-extraction run or tokenizer provenance differs from the archived pilot")
    records = []
    for line in (Path(__file__).with_name("pins.tsv")).read_text().splitlines():
        slug, repo, branch, tip = line.split()
        api, recent, pairs = defaults[repo], current[repo], overlaps[repo]
        graph = nullable(evidence / "runs" / (slug + ".json"))
        study = nullable(evidence / "runs" / ("pilot-" + repo.replace("/", "__") + ".json"))
        if graph and (graph["repository"] != repo or graph["pinned_default_sha"] != tip):
            raise ValueError("Graph scope mismatch: " + repo)
        if study and (study["repository"] != repo or study["default_tip"] != tip):
            raise ValueError("Pilot scope mismatch: " + repo)
        passed = study.get("status") == "success"
        if passed:
            if study["eligible_samples"] != study["positive_samples"] + study["negative_samples"]:
                raise ValueError("Label count mismatch: " + repo)
            if study["extractor_sha"] != "06e755ebabed1707a3413ec99ffa2511b046c543":
                raise ValueError("Unexpected extractor")
        default = graph.get("default", {})
        notes = ["Full default history and historical pilot are distinct populations.",
                 "Full-scope eligible rows, labels and current conflict prevalence were not measured."]
        # REST counts use the commit-list API. Git traversal is authoritative when both are available.
        if graph and default["total_commits"] != api["reachable_default_rest"]:
            notes.append("Pinned REST count differs from Git rev-list. See both raw values.")
        if graph and graph["fetched_default_tip"] != tip:
            notes.append("The advertised default ref had advanced. Default counts use the pinned SHA; all-heads/tags use the fetch-time manifest.")
        if not passed:
            notes.append("No validated production Parquet in this scope.")
        records.append({
            "repository": repo, "github_url": api["url"], "pinned_sha": tip, "default_branch": branch,
            "analyzed_refs": {"default_git_graph": graph.get("pinned_default_sha"), "all_graph": graph.get("fetch_refspecs"),
                              "sample_parquet": study.get("analyzed_refs")},
            "total_commits": default.get("total_commits", api["reachable_default_rest"]),
            "total_commits_source": "git_rev_list" if graph else "github_rest",
            "two_parent_merges": default.get("two_parent_merges"), "octopus_merges": default.get("octopus_merges"),
            "all_default_merges": default.get("all_merge_commits"),
            "default_unique_base_merges": default.get("two_parent_merge_bases", {}).get("unique"),
            "all_heads_tags": graph.get("all_heads_tags"),
            "github_size_kib": api["size_github_kib"], "java_paths_at_tip": api["java_blob_paths"],
            "public_heads": refs[repo]["head_count"], "public_tags": refs[repo]["tag_count"],
            "latest_closed_30d_total":recent["commits"],
            "latest_closed_30d_two_parent":recent["parent_count_histogram"].get("2", 0),
            "eight_merge_proxy": {"year":pairs["year"], "merges":pairs["sample_size"],
                                  "overlapping_java_paths":pairs["candidate_paths"]},
            "pilot_sha":study.get("pilot_anchor"), "pilot_two_parent_merges":study.get("funnel", {}).get("two_parent_merges"),
            "eligible_samples": study.get("eligible_samples") if passed else None,
            "positive_samples": study.get("positive_samples") if passed else None,
            "negative_samples": study.get("negative_samples") if passed else None,
            "positive_rate": study.get("positive_rate") if passed else None,
            "extraction_seconds": study.get("extraction_seconds"), "parquet_bytes": study.get("parquet_bytes"),
            "max_process_rss_kib": study.get("max_process_rss_kib"), "pilot_git_bytes":study.get("pilot_git_bytes"),
            "git_version": study.get("git_version", graph.get("git_version")),
            "extractor_sha": study.get("extractor_sha"), "extraction_status": study.get("status","unmeasured"),
            "evidence":[api["evidence"]["metadata"],api["evidence"]["tree"],recent["base_url"],pairs["url"]]
                        + ([f"evidence/runs/{slug}.json"] if graph else [])
                        + ([f"evidence/runs/pilot-{repo.replace('/', '__')}.json"] if study else []),
            "limitations":notes,
        })
        record = records[-1]
        record.update(
            record_type="primary_candidate",
            total_commits_pinned_rest=api["reachable_default_rest"],
            fetched_default_tip=graph.get("fetched_default_tip"),
            github_license_metadata=api["license"],
        )
        if passed:
            profile = profiles[repo.replace("/", "__") + ".parquet"]
            # Earlier empty Parquets had no row-level repo_id; the strict runner supplies the manifest ID.
            if profile["repo_id"] != repo and not (study["eligible_samples"] == 0 and profile["repo_id"] is None):
                raise ValueError("Quality file identifies a different repository: " + repo)
            record.update(pilot_measurements(repo, study, profile, quality["schema_columns_validated"]))
            record["pilot_two_parent_share_of_default"] = ratio(record["pilot_two_parent_merges"], record["two_parent_merges"])
            record["evidence"].append("evidence/runs/quality.json")
            if repo in integrity:
                validated = integrity[repo]
                if validated["logical_sha256"] != study["parquet_validation"]["logical_sha256"]:
                    raise ValueError("Token bounds refer to another dataset: " + repo)
                record["pilot_quality"]["strictly_longer_base_code_rows_bounds"] = validated["strictly_longer_base_code_rows_bounds"]
                record["evidence"].append("evidence/" + integrity_source)
            if provenance:
                record["ubuntu_run"] = {
                    "run_id": provenance["run_id"], "run_url": provenance["run_url"],
                    "research_sha": provenance["run_head"],
                    "pilot_artifact_id": artifacts["aggregate-pilot-results"],
                    "graph_artifact_id": artifacts["graph-" + slug],
                    "runner": provenance["pilot_runner"]["os_version"],
                    "extractor_threads": study["threads"],
                }
                record["evidence"].append("evidence/" + provenance_name)
            if repo in replays:
                add_remeasurement(record, replays[repo], "evidence/" + replay_source)
            if repo in notices:
                header_scan = notices[repo]
                if header_scan["logical_sha256"] != record["parquet_validation"]["logical_sha256"]:
                    raise ValueError("Historical notice scan used different rows: " + repo)
                record["historical_notice_rows"] = {
                    notice: {"rows": counts["rows"], "positive": counts["positive"]}
                    for notice, counts in header_scan["notices"].items()
                }
                record["evidence"].append("evidence/" + notice_source)
    records.extend(original_supplementary(evidence))
    records.extend(additional_supplementary(evidence))
    if len({r["repository"].lower() for r in records}) != len(records):
        raise ValueError("A primary or supplementary repository was counted twice")
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=Path(__file__).with_name("evidence"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.dumps(collect(args.evidence), ensure_ascii=False, allow_nan=False, indent=2)
    args.output.write_bytes((payload + "\n").encode("utf-8"))
