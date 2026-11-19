"""Join observed scopes by canonical owner/repo. Unobserved values stay null."""
import argparse
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def nullable(path):
    return read(path) if path.exists() else {}


def collect(evidence):
    defaults = {r["repo"]: r for r in read(evidence / "github-default-evidence.json")["repos"]}
    refs = {r["repository"]: r for r in read(evidence / "api-refs/inventory.json")["repositories"]}
    current = {r["repository"]: r for r in read(evidence / "recent-parent-counts.json")["repositories"]}
    overlaps = {r["repository"]: r for r in read(evidence / "recent-overlaps.json")["repositories"]}
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
        if not passed:
            notes.append("No validated production Parquet in this scope.")
        records.append({
            "repository": repo, "github_url": api["url"], "pinned_sha": tip, "default_branch": branch,
            "analyzed_refs": {"default_git_graph": tip, "all_graph": graph.get("fetch_refspecs"),
                              "sample_parquet": study.get("analyzed_refs")},
            "total_commits": default.get("total_commits", api["reachable_default_rest"]),
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
            "extractor_sha":"06e755ebabed1707a3413ec99ffa2511b046c543", "extraction_status": study.get("status","unmeasured"),
            "evidence":[api["evidence"]["metadata"],api["evidence"]["tree"],recent["base_url"],pairs["url"]]
                        + ([f"evidence/runs/{slug}.json"] if graph else [])
                        + ([f"evidence/runs/pilot-{repo.replace('/', '__')}.json"] if study else []),
            "limitations":notes,
        })
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=Path(__file__).with_name("evidence"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(collect(args.evidence), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
