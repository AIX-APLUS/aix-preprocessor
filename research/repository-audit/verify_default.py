"""Verify pinned Java file counts, GitHub commit pagination and latest-100 parent counts."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen


def get(repo, path):
    url = f"https://api.github.com/repos/{repo}/{path}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "aix-repository-audit"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    with urlopen(Request(url, headers=headers), timeout=75) as response:
        return json.load(response)


def java_paths(repo, tree):
    result = get(repo, f"git/trees/{tree}?recursive=1")
    if not result["truncated"]:
        return sum(entry["type"] == "blob" and entry["path"].endswith(".java") for entry in result["tree"])
    # The recursive response omitted entries. Partition at immediate child trees.
    children = get(repo, f"git/trees/{tree}")
    if children["truncated"]:
        raise ValueError(f"Unresolved truncated nonrecursive tree {tree}")
    return sum(java_paths(repo, entry["sha"]) if entry["type"] == "tree" else
               int(entry["type"] == "blob" and entry["path"].endswith(".java")) for entry in children["tree"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("default_evidence", type=Path)
    parser.add_argument("recent_evidence", type=Path)
    args = parser.parse_args()
    frozen = json.loads(args.default_evidence.read_text(encoding="utf-8"))["repos"]
    recent = {x["repository"]: x for x in json.loads(args.recent_evidence.read_text(encoding="utf-8"))["repos"]}
    for item in frozen:
        repo = item["repo"]
        sha = item["pinned_sha"]
        tree = get(repo, "git/commits/" + sha)["tree"]["sha"]
        if tree != item["tree"] or java_paths(repo, tree) != item["java_blob_paths"]:
            raise ValueError(f"{repo} tree / Java count mismatch")
        for param, n in (("", item["reachable_default_rest"]),
                         ("&since=2026-10-20T00:00:00Z", item["recent_since_2026_10_20"])):
            base = f"commits?sha={sha}{param}&per_page=1&page="
            if len(get(repo, base + str(n))) != 1 or get(repo, base + str(n + 1)):
                raise ValueError(f"{repo} commit pagination mismatch")
        sample = get(repo, f"commits?sha={sha}&per_page=100")
        counts = Counter(len(commit["parents"]) for commit in sample)
        observed = {"root": counts[0], "one": counts[1], "two": counts[2],
                    "octopus": sum(v for n, v in counts.items() if n > 2)}
        if observed != recent[repo]["parents"] or sample[-1]["sha"] != recent[repo]["last"]:
            raise ValueError(f"{repo} latest 100 commit sample mismatch")
        print(repo, sha, "verified")


if __name__ == "__main__":
    main()
