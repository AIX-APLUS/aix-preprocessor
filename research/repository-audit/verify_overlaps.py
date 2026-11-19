"""Replay the frozen small parent-overlap study via GitHub REST, using GITHUB_TOKEN if set."""

import argparse
import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from verify_metadata import get


def compare(repo, opposite, tip):
    info = get(f"repos/{repo}/compare/{opposite}...{tip}", {"page": 1, "per_page": 1})
    if info["base_commit"]["sha"] != opposite:
        raise ValueError("Unexpected comparison base")
    files = info["files"]
    changed = {}
    for item in files:
        if item["status"] not in ("modified", "renamed"):
            continue
        new = item["filename"]
        old = item.get("previous_filename", new)
        if new.endswith(".java") and old.endswith(".java") and "\ufffd" not in old + new:
            changed[old] = [new, item["sha"]]
    return info["merge_base_commit"]["sha"], len(files), changed


@lru_cache(maxsize=1024)
def tree(repo, revision, directory):
    # Read the directory's Git tree so modes and blob IDs can be checked without source downloads.
    parent, _, name = directory.rpartition("/")
    if not directory:
        tree_id = get(f"repos/{repo}/git/commits/{revision}")["tree"]["sha"]
    else:
        entries = get(f"repos/{repo}/contents/{quote(parent)}", {"ref": revision})
        if len(entries) >= 1000:
            raise ValueError("Incomplete directory listing")
        tree_id = next(entry["sha"] for entry in entries if entry["name"] == name and entry["type"] == "dir")
    listing = get(f"repos/{repo}/git/trees/{tree_id}")
    if listing["truncated"]:
        raise ValueError("Incomplete Git tree")
    return tree_id, {entry["path"]: entry for entry in listing["tree"]}


def blob(repo, ref, path):
    directory, _, name = path.rpartition("/")
    folder_tree, files = tree(repo, ref, directory)
    entry = files[name]  # A deleted or renamed-away original leaves a capped comparison unresolved.
    if not entry["mode"].startswith("100"):
        raise ValueError(f"Not a regular blob in {ref}: {path}")
    return {"mode": entry["mode"], "sha": entry["sha"], "folder_tree": folder_tree}


def verify_merge(repo, row):
    left, right = row["parents"]
    lbase, ln, le = compare(repo, right, left)
    rbase, rn, re = compare(repo, left, right)
    if (lbase != rbase or lbase != row["merge_base"]
            or ln != row["first_parent_diff"]["returned_files"]
            or rn != row["second_parent_diff"]["returned_files"]
            or len(le) != row["first_parent_diff"]["returned_java_edits"]
            or len(re) != row["second_parent_diff"]["returned_java_edits"]):
        raise ValueError("Compare response differs in " + row["merge"])
    if min(ln, rn) >= 300:
        raise ValueError("Both diffs may be truncated")
    if max(ln, rn) < 300:
        common = sorted(le.keys() & re.keys())
    else:
        small = re if ln >= 300 else le
        tip = left if ln >= 300 else right
        common = []
        for old in sorted(small):
            if blob(repo, lbase, old)["sha"] != blob(repo, tip, old)["sha"]:
                common.append(old)
    if common != sorted(path["original"] for path in row["overlaps"]):
        raise ValueError("Overlaps differ in " + row["merge"])
    for path in row["overlaps"]:
        objects = [blob(repo, ref, name) for ref, name in
                   zip((lbase, left, right), (path["original"], path["left"][0], path["right"][0]))]
        if (objects != path["blobs"] or objects[0]["sha"] in {objects[1]["sha"], objects[2]["sha"]}
                or objects[1]["sha"] != path["left"][1] or objects[2]["sha"] != path["right"][1]):
            raise ValueError("Blob or mode differs in " + row["merge"])


def verify_repository(data):
    repo, year = data["repository"], data["year"]
    selected = []
    page = 1
    while len(selected) < data["sample_size"]:
        commits = get(f"repos/{repo}/commits", {
            "sha": data["pinned_sha"], "since": f"{year}-10-20T00:00:00Z",
            "until": f"{year}-11-18T23:59:59Z", "per_page": 100, "page": page})
        selected.extend(c for c in commits if len(c["parents"]) == 2)
        if len(commits) < 100:
            break
        page += 1
    expected = data["observations"]
    if [c["sha"] for c in selected[:len(expected)]] != [o["merge"] for o in expected]:
        raise ValueError("Selection differs for " + repo)
    for commit, observation in zip(selected, expected):
        if [p["sha"] for p in commit["parents"]] != observation["parents"]:
            raise ValueError("Parent pair differs")
        verify_merge(repo, observation)
    print(repo, len(expected), "two-parent merges;", data["candidate_paths"], "overlapping paths")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", nargs="?", type=Path, default=Path(__file__).with_name("evidence") / "recent-overlaps.json")
    parser.add_argument("--repo", help="Limit API requests to one owner/name")
    args = parser.parse_args()
    source = json.loads(args.evidence.read_text("utf-8"))
    matches = [row for row in source["repositories"] if args.repo is None or row["repository"] == args.repo]
    if not matches:
        parser.error("No matching repository in the evidence")
    for row in matches:
        verify_repository(row)


if __name__ == "__main__":
    main()
