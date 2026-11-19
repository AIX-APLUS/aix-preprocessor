"""Replay only the three Git blobs for each observed overlap, outside any repository."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from verify_metadata import get


def measure(study, cache):
    observations = []
    for row in study["repositories"]:
        repo = row["repository"]
        for merge in row["observations"]:
            for candidate in merge["overlaps"]:
                with TemporaryDirectory(prefix="aix-merge-file-") as name:
                    folder = Path(name)
                    hashes = []
                    for role, item in zip(("base", "p1", "p2"), candidate["blobs"]):
                        sha = item["sha"]
                        encoded = cache[sha] if cache is not None else get(f"repos/{repo}/git/blobs/{sha}")["content"]
                        blob = base64.b64decode(encoded)
                        calculated = hashlib.sha1(f"blob {len(blob)}\0".encode("ascii") + blob).hexdigest()
                        if sha != calculated or b"\0" in blob:
                            raise ValueError("Git blob hash or text check failed for " + sha)
                        blob.decode("utf-8", errors="strict")
                        (folder / role).write_bytes(blob)
                        hashes.append(sha)
                    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
                    result = subprocess.run(["git", "merge-file", "--stdout", "p1", "base", "p2"],
                                            cwd=folder, env=env, stdout=subprocess.DEVNULL, capture_output=False,
                                            stderr=subprocess.PIPE, timeout=45)
                    if not 0 <= result.returncode <= 127 or result.stderr:
                        raise RuntimeError(f"merge-file failed with exit {result.returncode} in {merge['merge']}")
                    observations.append({"repo": repo, "merge": merge["merge"], "path": candidate["original"],
                                         "blob_ids_base_p1_p2": hashes, "returncode": result.returncode,
                                         "file_text_conflict": result.returncode > 0})
    return {"git_version": subprocess.check_output(["git", "--version"], text=True).strip(),
            "command": "git merge-file --stdout p1 base p2",
            "scope": "Default Git file merge on three verified UTF-8 non-NUL blobs in an empty directory. "
                     "No repository attributes, custom drivers, tree/rename/context replay, history or "
                     "production eligibility. These experimental flags are not extractor labels.",
            "observations": observations}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("overlaps", type=Path)
    parser.add_argument("--blob-cache", type=Path, help="Optional ephemeral REST blob mapping (SHA to base64)")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cache = json.loads(args.blob_cache.read_text("utf-8")) if args.blob_cache else None
    result = measure(json.loads(args.overlaps.read_text("utf-8")), cache)
    data = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data)


if __name__ == "__main__":
    main()
