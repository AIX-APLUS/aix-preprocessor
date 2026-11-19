"""Print recoverable SUMMARY records only after validating the entire pilot artifact."""
import base64
import gzip
import json
from pathlib import Path
import sys

from quality import QWEN_SHA256, require, study_pilots


def summaries(directory):
    payloads = {p.name: p.read_bytes() for p in sorted(directory.glob("*.json"))}
    quality = json.loads(payloads["quality.json"])
    require(quality["tokenizer_json_sha256"] == QWEN_SHA256, "Missing pinned token analysis")
    profiles = quality["inputs"]
    reports = study_pilots(directory, [Path(p["filename"]) for p in profiles], payloads=payloads)
    expected = {"quality.json", *("pilot-" + Path(name).stem + ".json" for name in reports)}
    require(payloads.keys() == expected, "Unexpected aggregate members")
    for profile in profiles:
        report = reports[profile["filename"]]
        counts = (report["eligible_samples"], report["positive_samples"], report["negative_samples"])
        require(profile["repo_id"] == report["repository"] and
                tuple(profile[k] for k in ("rows", "positive", "negative")) == counts,
                f"{report['repository']}: quality profile differs")
    for key in ("rows", "positive", "negative"):
        require(sum(p[key] for p in profiles) == quality["combined_profile"][key], "Invalid total " + key)
    combined = quality["combined_profile"]
    token_mode = "measured" if combined["rows"] else "no_rows"
    # The original hosted result predates the explicit mode field.
    require(quality.get("token_analysis", token_mode) == token_mode and
            (combined["base_code_tokens"] is not None) == bool(combined["rows"]), "Incomplete token analysis")
    for name, data in payloads.items():
        yield "SUMMARY", name, base64.b64encode(gzip.compress(data, mtime=0)).decode("ascii")


if __name__ == "__main__":
    for summary in summaries(Path(sys.argv[1])):
        print(*summary)
