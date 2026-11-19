"""Render the three observed UTC windows. Requires Pillow and a Korean font.

python plot_parent_windows.py EVIDENCE_DIRECTORY OUTPUT.png
"""
import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PROJECTS = {
    "spring-projects/spring-boot": "Spring Boot", "quarkusio/quarkus": "Quarkus",
    "Card-Forge/forge": "Forge", "JabRef/jabref": "JabRef", "jenkinsci/jenkins": "Jenkins",
}


def records(directory):
    data = {}
    for f in ("historical-parent-counts.json", "recent-parent-counts.json"):
        batch = json.loads((directory / f).read_text(encoding="utf-8"))
        for row in batch["repositories"]:
            start = datetime.fromisoformat(row.get("utc_start", batch.get("utc_start")).replace("Z", "+00:00"))
            end = datetime.fromisoformat(row.get("utc_end", batch.get("utc_end")).replace("Z", "+00:00"))
            if (end - start + timedelta(seconds=1) != timedelta(days=30)
                    or (start.month, start.day, end.month, end.day) != (10, 20, 11, 18)):
                raise ValueError("Chart expects a full 30-day Oct 20 to Nov 18 window")
            key = (row["repository"], start.year)
            total, hist = row["commits"], row["parent_count_histogram"]
            if key in data or sum(hist.values()) != total or not total:
                raise ValueError(f"Inconsistent window {key}")
            data[key] = (hist.get("2", 0), total)
    expected = {(r,y) for r in PROJECTS for y in (2020, 2023, 2026)}
    if set(data) != expected:
        raise ValueError("Expected all five pinned repositories and three windows")
    return data


def available_font(override, bold):
    if override:
        return override
    fallbacks = [
        Path("C:/Windows/Fonts") / ("malgunbd.ttf" if bold else "malgun.ttf"),
        Path("/usr/share/fonts/opentype/noto") / ("NotoSansCJK-Bold.ttc" if bold else "NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/nanum") / ("NanumGothicBold.ttf" if bold else "NanumGothic.ttf"),
        Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
    ]
    for font in fallbacks:
        if font.is_file():
            return str(font)
    raise ValueError("Supply a Korean font with --font and --bold-font")


def render(data, output, regular, bold):
    canvas = Image.new("RGB", (1920,1080), "white")
    draw = ImageDraw.Draw(canvas)
    ink, secondary = "#15342f", "#3d5854"
    def text(x, y, value, size, *, strong=False, color=ink, anchor="lm"):
        font = ImageFont.truetype(bold if strong else regular, size)
        draw.text((x,y), value, font=font, fill=color, anchor=anchor, stroke_width=0)

    text(82, 84, "어느 프로젝트에 두 부모 병합이 많이 남아 있을까?", 59, strong=True)
    text(84, 161, "각 연도 10월 20일 ~ 11월 18일 (UTC)  ·  고정한 기본 브랜치 커밋에서 도달 가능한 이력", 31, color=secondary)
    pad, x0, cw, cols = 8, 500, 437, (2020, 2023, 2026)
    text(84, 265, "프로젝트", 32, strong=True)
    for j, year in enumerate(cols):
        text(x0+(j+.5)*cw, 265, str(year)+"년", 34, strong=True, anchor="mm")
    for i, (repo, project) in enumerate(PROJECTS.items()):
        top = 310 + i*109
        text(86, top+41, project, 36, strong=True)
        text(87, top+79, repo, 23, color=secondary)
        for j, year in enumerate(cols):
            count, total = data[repo,year]
            rate = count/total
            low, high = (242,247,246), (113,184,169)
            strength = min(rate/.55,1)
            fill = tuple(round(a+(b-a)*strength) for a,b in zip(low,high))
            left, mid = x0+j*cw, x0+(j+.5)*cw
            draw.rounded_rectangle((left+pad, top, left+cw-pad, top+99), radius=9, fill=fill)
            text(mid, top+36, f"{rate:.1%}", 42, strong=True, anchor="mm")
            text(mid, top+77, f"{count:,} / {total:,}", 25, color=secondary, anchor="mm")
    draw.line((84, 901, 1815, 901), fill="#c3d1cd", width=2)
    text(86, 944, "각 칸은 두 부모 병합 수 / 조사한 전체 커밋 수와 그 비율을 표시해요. 색이 진할수록 비율이 높아요.", 29)
    text(86, 999, "0%는 그 30일에 두 부모 병합이 0건이었다는 뜻이에요. 파일 충돌률은 병합을 재현해 따로 측정해요.", 27, color=secondary)
    canvas.save(output, dpi=(144,144), optimize=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("evidence", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--font")
    ap.add_argument("--bold-font")
    args = ap.parse_args()
    render(records(args.evidence), args.output, available_font(args.font, False),
           available_font(args.bold_font or args.font, True))
