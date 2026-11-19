"""Render/check the two pilot tables in the research report and its presentation figure."""

import argparse
import json
from pathlib import Path


DOCS = Path(__file__).resolve().parents[2] / "docs" / "research"
NAMES = {
    "spring-projects/spring-boot": "Spring Boot",
    "jenkinsci/jenkins": "Jenkins",
    "Card-Forge/forge": "Card Forge",
    "JabRef/jabref": "JabRef",
    "quarkusio/quarkus": "Quarkus",
}
START = "<!-- pilot-tables:start -->"
END = "<!-- pilot-tables:end -->"


def tables(records):
    history = [
        "| 저장소 | 기본 tip 커밋 / 두 부모 병합 | 전체 heads·tags 커밋 / 두 부모 병합 | 파일럿 ref 끝점 | 파일럿 커밋 / 두 부모 병합 | 기본 tip 두 부모 병합 중 파일럿 비율 | 행을 낸 병합 |",
        "|---|---:|---:|---|---:|---:|---:|",
    ]
    samples = [
        "| 저장소 | 유효 행 | 양성 | 음성 | 양성률 | 추출(초) | 최대 RSS(KiB) | Parquet(B) | 행/병합 | 행/초 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in records:
        repo = r["repository"]
        name = NAMES[repo]
        all_refs = r["all_heads_tags"]
        p = json.loads((Path(__file__).with_name("evidence") / "runs" /
                        f"pilot-{repo.replace('/', '__')}.json").read_text(encoding="utf-8"))
        n, pos, neg = (r[k] for k in ("eligible_samples", "positive_samples", "negative_samples"))
        m, sec = r["pilot_two_parent_merges"], r["extraction_seconds"]
        if n != pos + neg or p["parquet_validation"]["samples"] != n:
            raise ValueError(f"Inconsistent label counts in {repo}")
        anchor = r["pilot_sha"]
        date = p["pilot_tip_committed_at"][:10]
        history.append(f"| {name} | {r['total_commits']:,} / {r['two_parent_merges']:,} | "
                       f"{all_refs['total_commits']:,} / {all_refs['two_parent_merges']:,} | "
                       f"[{date} · `{anchor[:8]}`](https://github.com/{repo}/commit/{anchor}) | "
                       f"{p['pilot_total_commits']:,} / {m:,} | {m / r['two_parent_merges']:.2%} | "
                       f"{p['funnel']['merges_with_joint_edits']} |")
        samples.append(f"| {name} | {n} | {pos} | {neg} | {pos / n:.2%} | {sec:.3f} | "
                       f"{r['max_process_rss_kib']:,} | {r['parquet_bytes']:,} | {n / m:.3f} | {n / sec:.2f} |")
    return "\n".join(history) + "\n\n" + "\n".join(samples)


def screening_table(data):
    header = [
        "| 조사 후보 | 고정 tip 커밋 | Java 파일 | 두 부모 병합 (tip / 2025 / 2018) | 검사한 병합 | 확인한 쌍방 수정 Java 건수 | 파일 단위 충돌 / 깨끗한 병합 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in sorted((row for row in data if row.get("record_type") == "supplementary_candidate"),
                    key=lambda row: row["repository"].lower()):
        s = r["screening"]
        windows = s["windows"]
        if len(windows) != 3 or any(w["commits"] != 25 for w in windows):
            raise ValueError("Expected three windows of 25 commits")
        counts = " / ".join(str(w["two_parent"]) for w in windows)
        pairs = s["bilateral_path_pairs_observed_lower_bound"]
        pos, neg = s["isolated_text_probe_positive"], s["isolated_text_probe_negative"]
        outcome = f"{pos} / {neg}" if pos is not None and neg is not None else "미실행"
        header.append(f"| [{r['repository']}]({r['github_url']}) | {r['total_commits']:,} | "
                      f"{r['java_paths_at_tip']:,} | {counts} | {s['bilateral_checked_merges']} | "
                      f"{pairs if pairs is not None else '미측정'} | {outcome} |")
    if len(header) != 12:
        raise ValueError("Expected ten supplementary candidates")
    return "\n".join(header)


def chart(records, path):
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import font_manager, pyplot as plt
    from matplotlib.patches import Patch

    available = {f.name for f in font_manager.fontManager.ttflist}
    font = next((f for f in ("Malgun Gothic", "Noto Sans CJK KR", "NanumGothic", "AppleGothic")
                 if f in available), None)
    if font is None:
        raise RuntimeError("A Korean font is required to render the presentation figure.")
    plt.rcParams.update({"font.family": font, "font.size": 12})
    ordered = sorted(records, key=lambda r: -r["eligible_samples"])
    positive, negative = "#a94c28", "#72a3ae"
    fig, ax = plt.subplots(figsize=(10, 5.4))
    fig.subplots_adjust(left=.16, right=.95, bottom=.21, top=.78)
    fig.text(.035, .93, "과거 병합에서 확보한 Java 파일 학습 사례", fontsize=20, weight="bold")
    total = sum(r["eligible_samples"] for r in records)
    fig.text(.035, .858, f"저장소마다 다른 과거 시점까지 추출한 {total}행   ·   단위  파일 × 병합", fontsize=12)
    for i, r in enumerate(ordered):
        pos, neg = r["positive_samples"], r["negative_samples"]
        ax.barh(i, pos, color=positive, height=.55)
        ax.barh(i, neg, left=pos, color=negative, height=.55)
        ax.text(pos + neg + 2.5, i, f"{pos} / {neg}", va="center", fontsize=11)
    ax.set_yticks(range(len(ordered)), [NAMES[r["repository"]] for r in ordered])
    ax.invert_yaxis()
    ax.set_xlim(0, max(r["eligible_samples"] for r in ordered) * 1.18)
    ax.set_xlabel("유효 학습 사례 수")
    ax.xaxis.grid(True, color="#dce4e6", linewidth=.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0, pad=7)
    ax.spines[:].set_visible(False)
    fig.legend(handles=[Patch(color=positive, label="충돌 양성"), Patch(color=negative, label="음성")],
               loc="upper right", bbox_to_anchor=(.98, .84), frameon=False, ncol=2, fontsize=10)
    fig.text(.035, .045, "막대 옆은 양성 / 음성 행 수.   출처  AIX Ubuntu 연구 실행 44549292132",
             fontsize=10, color="#47565a")
    fig.savefig(path, dpi=150, facecolor="white")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if report tables differ")
    parser.add_argument("--figure", type=Path, help="optional PNG output (requires matplotlib)")
    args = parser.parse_args()
    data = json.loads((DOCS / "repository-suitability.json").read_text(encoding="utf-8"))
    by_repo = {r["repository"]: r for r in data}
    records = [by_repo[repo] for repo in NAMES]
    path = DOCS / "repository-suitability.md"
    original = path.read_text(encoding="utf-8")
    rendered = original
    for start, end, body in [
        (START, END, tables(records)),
        ("<!-- screening:start -->", "<!-- screening:end -->", screening_table(data)),
    ]:
        if rendered.count(start) != 1 or rendered.count(end) != 1:
            raise ValueError(f"Expected one generated section for {start}")
        before, rest = rendered.split(start)
        _, after = rest.split(end)
        rendered = before + start + "\n\n" + body + "\n\n" + end + after
    if args.check:
        if original != rendered:
            raise SystemExit("Report tables differ from JSON.")
        print("Tables for five pilots and ten screened candidates match the JSON and run records.")
    else:
        path.write_bytes(rendered.encode("utf-8"))
    if args.figure:
        chart(records, args.figure)


if __name__ == "__main__":
    main()
