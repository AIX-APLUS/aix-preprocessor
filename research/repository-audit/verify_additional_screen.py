"""Check the secondary Java screen locally; --online repeats the pinned GitHub reads."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from verify_metadata import get


EVIDENCE = Path(__file__).parent / "evidence" / "additional"


def load(name):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def check(condition, detail):
    if not condition:
        raise ValueError(detail)


def fetch(url):
    parts = urlsplit(url)
    check(parts.netloc == "api.github.com", url)
    return get(parts.path.lstrip("/") + ("?" + parts.query if parts.query else ""))


def verify_tree_and_count(repo):
    url = repo["java_tree"]["url"]
    pinned = fetch(repo["pinned_commit_url"])
    tree = fetch(url)
    check(tree["sha"] == pinned["tree"]["sha"] == repo["java_tree"]["tree_sha"], url)
    check(not tree["truncated"], url)
    java = [e for e in tree["tree"] if e["type"] == "blob" and e["path"].endswith(".java")]
    check(len(java) == repo["java_files_at_pin"], url)
    check(sum(e["size"] for e in java) == repo["java_bytes_at_pin"], url)
    boundary = repo["commit_page_boundary"]
    base = repo["meta_url"] + "/commits?"
    for page, expected in [(repo["commits_at_pin"], [boundary["last_sha"]]),
                           (repo["commits_at_pin"] + 1, [])]:
        url = base + urlencode({"sha": repo["pin"], "per_page": 1, "page": page})
        check([e["sha"] for e in fetch(url)] == expected, url)


def verify_repository(repo, online):
    if online:
        verify_tree_and_count(repo)
    chosen = []
    for w in repo["windows"]:
        records = w["records"]
        merges = [v for v in records if len(v[1]) == 2]
        check(len(records) == w["commits"] == 25, w["url"])
        check(len(merges) == w["two_parent"], w["url"])
        check(len({v[0] for v in records}) == len(records), w["url"])
        if online:
            current = [[c["sha"], [p["sha"] for p in c["parents"]]] for c in fetch(w["url"])]
            check(current == records, w["url"])
        chosen.extend((w["name"], m, p) for m, p in merges[:2])
    check(sorted(chosen) == sorted((o["window"], o["merge"], o["parents"]) for o in repo["overlaps"]),
          repo["repository"])
    expected_probes = set()
    for o in repo["overlaps"]:
        if online:
            comparisons = [fetch(url + "?per_page=1") for url in o["compare_urls"]]
            check(all(c["merge_base_commit"]["sha"] == o["common_base"] for c in comparisons),
                  o["merge"])
            changes = [{f["filename"] for f in c["files"]
                        if f["status"] == "modified" and f["filename"].endswith(".java")}
                       for c in comparisons]
            check([len(c["files"]) for c in comparisons] == o["returned_files"], o["merge"])
            check(sorted(set.intersection(*changes)) == o["both_modified_java"], o["merge"])
        expected_probes.update((repo["repository"], o["merge"], path)
                               for path in o["both_modified_java"])
    return expected_probes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--online", action="store_true")
    args = parser.parse_args()
    expected = set()
    for repo in load("screen.json")["repositories"]:
        expected.update(verify_repository(repo, args.online))
    observed = {}
    for study in load("text-probe-input.json")["repositories"]:
        for merge in study["observations"]:
            for path in merge["overlaps"]:
                key = study["repository"], merge["merge"], path["original"]
                check(key not in observed, key)
                observed[key] = [b["sha"] for b in path["blobs"]]
    check(set(observed) == expected, "Probe manifest differs from observed intersections")
    results = load("text-probe.json")["observations"]
    check(len(results) == len(expected), "Unexpected probe count")
    for item in results:
        key = item["repo"], item["merge"], item["path"]
        check(observed.pop(key) == item["blob_ids_base_p1_p2"], key)
        check(0 <= item["returncode"] <= 127 and
              (item["returncode"] != 0) == item["file_text_conflict"], key)
    check(not observed, "Missing probe results")
    print(f"Verified {len(expected)} isolated file probes and five secondary screens.")


if __name__ == "__main__":
    main()
