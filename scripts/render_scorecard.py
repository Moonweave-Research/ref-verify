"""Render the README scorecard chart (light and dark SVG) from a benchmark results file."""

from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = REPO_ROOT / ".github" / "assets"

WIDTH = 830
LABEL_X = 24
BAR_X = 216
BAR_WIDTH = 350
HEADLINE_X = BAR_X + BAR_WIDTH + 16
BAR_HEIGHT = 24
ROW_PITCH = 64
TOP = 118
FONT = "system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"

# One blue ordinal ramp: the verdict is ordered by severity (pass < warn < reject), and
# whether a verdict is good depends on the row, so no green/red is implied. Dark mode
# flips the anchor so the strongest verdict stays the highest-contrast step.
THEMES = {
    "light": {
        "surface": "#fcfcfb",
        "ink": "#0b0b0b",
        "ink2": "#52514e",
        "muted": "#898781",
        "track": "#e1e0d9",
        "pass": "#86b6ef",
        "warn": "#2a78d6",
        "reject": "#104281",
        "on_pass": "#0b0b0b",
        "on_warn": "#ffffff",
        "on_reject": "#ffffff",
    },
    "dark": {
        "surface": "#1a1a19",
        "ink": "#ffffff",
        "ink2": "#c3c2b7",
        "muted": "#898781",
        "track": "#2c2c2a",
        "pass": "#184f95",
        "warn": "#3987e5",
        "reject": "#9ec5f4",
        "on_pass": "#ffffff",
        "on_warn": "#0b0b0b",
        "on_reject": "#0b0b0b",
    },
}

ROWS = (
    ("REAL", "Real papers", "real_clean_pass", "passed cleanly", "PASS only"),
    ("FABRICATED", "Fabricated references", "fabricated_flagged", "flagged", "WARN or REJECT"),
    ("RETRACTED", "Retracted papers", "retracted_rejected", "caught as retracted", "PAPER_RETRACTED"),
    ("NOT_IN_CROSSREF", "Real, not in CrossRef", "unindexed_rejected", "wrongly rejected", "should be WARN"),
)
SEGMENTS = (
    ("pass", "PASS"),
    ("warn", "WARN · check by hand"),
    ("reject", "REJECT"),
)


def _text(x: float, y: float, body: str, *, fill: str, size: int = 14, weight: int = 400, anchor: str = "start") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" font-weight="{weight}" '
        f'text-anchor="{anchor}">{escape(body)}</text>'
    )


def _segment_path(x: float, y: float, width: float, height: float, round_right: bool) -> str:
    # Square at the baseline, 4px rounded data end.
    r = min(4.0, width / 2) if round_right else 0.0
    return (
        f"M{x:.2f},{y:.2f} H{x + width - r:.2f} "
        f"Q{x + width:.2f},{y:.2f} {x + width:.2f},{y + r:.2f} "
        f"V{y + height - r:.2f} Q{x + width:.2f},{y + height:.2f} {x + width - r:.2f},{y + height:.2f} "
        f"H{x:.2f} Z"
    )


def _headline(aggregates: dict[str, Any], key: str, suffix: str) -> str:
    rate = aggregates[key]
    if key == "unindexed_rejected":
        return f"{rate['k']} of {rate['n']} {suffix}"
    return f"{round(100 * rate['rate'])}% {suffix}"


def _interval(aggregates: dict[str, Any], key: str) -> str:
    low, high = aggregates[key]["ci95"]
    return f"95% CI {round(100 * low)}–{round(100 * high)}%"


def _dev_summary(dev: dict[str, Any]) -> tuple[str, str]:
    a = dev["aggregates"]
    parts = (
        f"real {a['real_clean_pass']['k']}/{a['real_clean_pass']['n']} PASS",
        f"fabricated {a['fabricated_flagged']['k']}/{a['fabricated_flagged']['n']} flagged",
        f"retracted {a['retracted_rejected']['k']}/{a['retracted_rejected']['n']} caught",
        f"unindexed {a['unindexed_rejected']['k']}/{a['unindexed_rejected']['n']} rejected",
    )
    return f"Development set ({len(dev['results'])} refs, used while fixing the tool, in-sample): " + " · ".join(parts[:2]), " · ".join(parts[2:])


def render_svg(results: dict[str, Any], theme_name: str, dev: dict[str, Any] | None = None) -> str:
    theme = THEMES[theme_name]
    aggregates = results["aggregates"]
    composition = aggregates["composition"]
    total = len(results["results"])
    height = TOP + ROW_PITCH * len(ROWS) + (84 if dev else 40)
    parts: list[str] = []

    title = f"How check-bib judged {total} held-out references"
    subtitle = (
        f"ref-verify {results['tool_version']} · commit {results['commit']} · {results['date']} · "
        "live CrossRef · set frozen before the run"
    )
    parts.append(_text(LABEL_X, 34, title, fill=theme["ink"], size=20, weight=600))
    parts.append(_text(LABEL_X, 58, subtitle, fill=theme["ink2"], size=14))

    legend_x = float(LABEL_X)
    for key, label in SEGMENTS:
        parts.append(
            f'<rect x="{legend_x:.1f}" y="78" width="12" height="12" rx="2" fill="{theme[key]}"/>'
        )
        parts.append(_text(legend_x + 18, 89, label, fill=theme["ink2"], size=13))
        # ~7px per character at 13px in the system sans.
        legend_x += 18 + 7 * len(label) + 24

    for index, (category, label, key, suffix, rule) in enumerate(ROWS):
        counts = composition.get(category, {"n": 0, "pass": 0, "warn": 0, "reject": 0})
        y = TOP + index * ROW_PITCH
        parts.append(_text(LABEL_X, y + 12, label, fill=theme["ink"], size=15, weight=600))
        # Retractions CrossRef cannot mark (DOIs at other agencies) are in the bar but not in
        # the rate, so the label and headline say which denominator the rate uses.
        unmarked = aggregates.get("retracted_not_marked_by_crossref", 0) if category == "RETRACTED" else 0
        size_label = f"n = {counts['n']} ({unmarked} unmarked)" if unmarked else f"n = {counts['n']}"
        parts.append(_text(LABEL_X, y + 31, size_label, fill=theme["muted"], size=13))

        nonzero = [(seg, counts[seg]) for seg, _ in SEGMENTS if counts[seg]]
        gap = 2.0
        usable = BAR_WIDTH - gap * (len(nonzero) - 1)
        x = float(BAR_X)
        bar_y = y + 2
        for position, (seg, count) in enumerate(nonzero):
            width = usable * count / counts["n"]
            last = position == len(nonzero) - 1
            share = round(100 * count / counts["n"])
            parts.append(
                f'<path d="{_segment_path(x, bar_y, width, BAR_HEIGHT, last)}" fill="{theme[seg]}">'
                f"<title>{escape(label)}: {count} of {counts['n']} {seg.upper()} ({share}%)</title></path>"
            )
            label_text = str(count)
            if width >= 8 * len(label_text) + 12:
                parts.append(
                    _text(
                        x + width / 2,
                        bar_y + 17,
                        label_text,
                        fill=theme[f"on_{seg}"],
                        size=13,
                        weight=600,
                        anchor="middle",
                    )
                )
            x += width + gap

        headline = _headline(aggregates, key, suffix)
        if unmarked:
            headline = f"{aggregates[key]['k']}/{aggregates[key]['n']} marked ones caught"
        parts.append(_text(HEADLINE_X, y + 12, headline, fill=theme["ink"], size=15, weight=600))
        parts.append(
            _text(HEADLINE_X, y + 31, f"{rule} · {_interval(aggregates, key)}", fill=theme["muted"], size=13)
        )

    timing = results["timing"]
    footer = (
        f"Whole set: {timing['first_run_seconds']:.0f} s on a cold cache, "
        f"{timing['cached_run_seconds']:.1f} s cached · {results['workers']} workers"
    )
    footer_y = height - (60 if dev else 16)
    parts.append(_text(LABEL_X, footer_y, footer, fill=theme["muted"], size=13))
    if dev:
        for offset, line in zip((22, 40), _dev_summary(dev)):
            parts.append(_text(LABEL_X, footer_y + offset, line, fill=theme["muted"], size=13))

    description = "; ".join(
        f"{label}: {composition.get(category, {}).get('pass', 0)} pass, "
        f"{composition.get(category, {}).get('warn', 0)} warn, "
        f"{composition.get(category, {}).get('reject', 0)} reject"
        for category, label, *_ in ROWS
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" aria-labelledby="t d" font-family="{FONT}">\n'
        f'<title id="t">{escape(title)}</title>\n<desc id="d">{escape(description)}</desc>\n'
        f'<rect width="{WIDTH}" height="{height}" rx="8" fill="{theme["surface"]}"/>\n'
        + "\n".join(parts)
        + "\n</svg>\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path, help="held-out results: benchmarks/results/<date>-<sha>-holdout-v1.json")
    parser.add_argument("--dev", type=Path, help="development-set results, shown as a footnote")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)

    results = json.loads(args.results.read_text(encoding="utf-8"))
    dev = json.loads(args.dev.read_text(encoding="utf-8")) if args.dev else None
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        path = args.out_dir / f"scorecard-{theme}.svg"
        path.write_text(render_svg(results, theme, dev), encoding="utf-8")
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
