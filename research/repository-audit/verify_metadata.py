"""Re-read the frozen REST evidence; metadata comes from the adjacent JSON.

Run with Python 3.10+. GITHUB_TOKEN is optional. Only sends GET requests to
api.github.com. Repository size and the moving branch pointer can change.
"""

import argparse
import json
import os
import urllib.request
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode


def get(path, params=None):
    url = "https://api.github.com/" + path
    if params:
        url += "?" + urlencode(params)
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "aix-repository-audit"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=45) as response:
        return json.load(response)


def verify_repository(repository):
    key = repository["repo"]
    root = "repos/" + key
    source = get(root)
    pinned = get(root + "/git/commits/" + repository["sha"])
    window = repository["recent_commits"]
    params = {"sha": pinned["sha"], "since": window["since"], "until": window["until"], "per_page": 1}
    last = get(root + "/commits", {**params, "page": window["count"]})
    following = get(root + "/commits", {**params, "page": window["count"] + 1})
    if pinned["tree"]["sha"] != repository["tree"] or len(last) != 1 or following:
        raise ValueError(f"Frozen commit tree or bounded commit count differs for {key}")
    print(key, pinned["sha"], "commits in fixed period", window["count"],
          "current reported repository size (KiB)", source["size"])


def verify_pr(pr):
    root = "repos/" + pr["repo"]
    source = get(f'{root}/pulls/{pr["pr"]}')
    target = get(f'{root}/git/commits/{pr["merge_commit_sha"]}')
    if (source["merge_commit_sha"] != pr["merge_commit_sha"]
            or [item["sha"] for item in target["parents"]] != pr["parent_shas"]):
        raise ValueError(f'PR result differs for {pr["url"]}')
    print(pr["url"], "parents", len(target["parents"]), "reported merge method", source.get("merge_method"))


def verify_period(evidence):
    for repo in evidence["repositories"]:
        counts = Counter()
        seen = set()
        for page in range(1, repo["page_count"] + 1):
            items = get("repos/" + repo["repository"] + "/commits", {
                "sha": repo["pinned_sha"],
                "since": repo.get("utc_start", evidence.get("utc_start")),
                "until": repo.get("utc_end", evidence.get("utc_end")),
                "page": page, "per_page": 100,
            })
            for item in items:
                if item["sha"] in seen:
                    raise ValueError("Repeated commit on consecutive pages: " + item["sha"])
                seen.add(item["sha"])
                counts[str(len(item["parents"]))] += 1
        if counts != repo["parent_count_histogram"] or len(seen) != repo["commits"]:
            raise ValueError("Period histogram differs for " + repo["repository"])
        print(repo["repository"], "parent counts", counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path, nargs="?",
                        default=Path(__file__).with_name("evidence") / "github-metadata.json")
    parser.add_argument("--period", action="append", type=Path, default=[],
                        help="Optional recent-parent-counts.json or historical-parent-counts.json; repeatable")
    args = parser.parse_args()
    data = json.loads(args.evidence.read_text(encoding="utf-8"))
    for repository in data["repositories"]:
        verify_repository(repository)
    for pr in data["pull_requests"]:
        verify_pr(pr)
    for period in args.period:
        verify_period(json.loads(period.read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
