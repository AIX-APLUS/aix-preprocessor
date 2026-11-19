"""Verify preserved Actions results, optionally against downloaded ZIPs and the raw pilot log."""

import argparse
import base64
import gzip
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZipFile

EVIDENCE = Path(__file__).resolve().parent / "evidence"
SUMMARY = re.compile(r"(?:^|\s)SUMMARY (?P<name>[\w.-]+\.json) (?P<data>[A-Za-z0-9+/=]+)\s*$")


def check(value, expected, description):
    if value != expected:
        raise ValueError(f"{description}: expected {expected!r}, got {value!r}")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def verify_refs(data, member, files):
    name = member["name"]
    graph = json.loads(files[name.removesuffix(".refs.tsv.gz") + ".json"])
    refs = gzip.decompress(data)
    check(sha256(refs), member["uncompressed_sha256"], f"{name} uncompressed digest")
    check(sha256(refs), graph["refs_uncompressed_sha256"], f"{name} graph digest")
    rows = [row.split("\t") for row in refs.decode("utf-8").splitlines()]
    check(len(rows), member["ref_rows"], f"{name} ref count")
    refs_by_name = dict(rows)
    check(len(refs_by_name), len(rows), f"{name} distinct refs")
    check(refs_by_name["refs/heads/" + graph["default_branch"]], graph["fetched_default_tip"], f"{name} fetched default tip")
    for prefix, field in (("refs/heads/", "head_count"), ("refs/tags/", "tag_count")):
        check(sum(ref.startswith(prefix) for ref in refs_by_name), graph[field], f"{name} {field}")


def verify_archive(path, artifact, files):
    check(path.stat().st_size, artifact["archive_bytes"], f"{path.name} byte size")
    check(sha256(path.read_bytes()), artifact["github_zip_sha256"], f"{path.name} GitHub digest")
    with ZipFile(path) as archive:
        check(sorted(archive.namelist()), sorted(m["name"] for m in artifact["members"]), f"{path.name} members")
        for member in artifact["members"]:
            name = member["name"]
            data = archive.read(name)  # ZipFile reads and validates the member's CRC.
            check(len(data), member["bytes"], f"{name} ZIP member size")
            check(sha256(data), member["archive_member_sha256"], f"{name} ZIP member hash")
            if name.endswith(".gz"):
                check(gzip.decompress(data) == gzip.decompress(files[name]), True, f"{name} decompressed evidence equality")
            else:
                check(data == files[name], True, f"{name} exact evidence equality")


def verify_log(log, expected, files):
    seen = set()
    for line in log.read_text(encoding="utf-8-sig").splitlines():
        match = SUMMARY.search(line)
        if not match:
            continue
        name, encoded = match.group("name", "data")
        if name in seen or name not in expected:
            raise ValueError(f"unexpected or duplicate SUMMARY for {name}")
        seen.add(name)
        decoded = gzip.decompress(base64.b64decode(encoded, validate=True))
        json.loads(decoded.decode("utf-8"))
        check(sha256(decoded), expected[name]["decoded_sha256"], f"{name} decoded SUMMARY hash")
        check(decoded == files[name], True, f"{name} decoded SUMMARY vs evidence")
    check(sorted(seen), sorted(expected), "SUMMARY members")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provenance", type=Path, default=EVIDENCE / "run-44549292132-provenance.json")
    parser.add_argument("--evidence-dir", type=Path, default=EVIDENCE / "runs")
    parser.add_argument("--zip-dir", type=Path, help="directory with <artifact name>.zip downloads")
    parser.add_argument("--pilot-log", type=Path, help="decoded UTF-8 text of the pilot job log")
    args = parser.parse_args()
    manifest = json.loads(args.provenance.read_bytes())
    files = {}
    log_hashes = manifest["pilot_log_crosscheck"]["members"]
    for artifact in manifest["artifacts"]:
        for member in artifact["members"]:
            name = member["name"]
            if Path(name).name != name or name in files:
                raise ValueError(f"invalid or duplicate evidence file: {name}")
            files[name] = (args.evidence_dir / name).read_bytes()
            check(sha256(files[name]), member["evidence_sha256"], f"{name} preserved evidence hash")
            if name.endswith(".json"):
                json.loads(files[name].decode("utf-8"))
                check(sha256(files[name]), member["archive_member_sha256"], f"{name} recorded ZIP member hash")
        for member in artifact["members"]:
            if member["name"].endswith(".gz"):
                verify_refs(files[member["name"]], member, files)
        if args.zip_dir:
            verify_archive(args.zip_dir / (artifact["name"] + ".zip"), artifact, files)
    for name, record in log_hashes.items():
        check(sha256(files[name]), record["decoded_sha256"], f"{name} recorded SUMMARY hash")
    if args.pilot_log:
        verify_log(args.pilot_log, log_hashes, files)
    print(f"Verified {len(files)} preserved files for run {manifest['run_id']}.")
    if args.zip_dir:
        print(f"Verified {len(manifest['artifacts'])} downloaded ZIPs.")
    if args.pilot_log:
        print(f"Verified {len(log_hashes)} independently decoded SUMMARY entries.")


if __name__ == "__main__":
    main()
