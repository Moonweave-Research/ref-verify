from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from ref_verify import __version__
from ref_verify.batch import BatchRowResult
from ref_verify.doi_check import normalize_doi
from ref_verify.reference_resolve import ReferenceResult

ReportFormat = Literal["html", "md"]

FOOTER_NOTE = (
    "This report compares references against public metadata and abstracts "
    "(CrossRef, OpenAlex, Semantic Scholar, PubMed). UNVERIFIED means the tool could "
    "not confirm it automatically, not that it is wrong."
)
_UNVERIFIED_STATUSES = {"UNVERIFIED", "UNVERIFIABLE"}
_TONES = {"PASS": "pass", "ACCEPT": "pass", "WARN": "warn", "REJECT": "reject", "UNVERIFIED": "unverified"}
# What each verdict asks the reader to do, shown above the tables in plain words.
_LEGENDS = {
    "check-bib": (
        ("PASS", "Title, first author, and year match the CrossRef record for the DOI (or the record found by search)."),
        ("WARN", "Found, but something differs; the reason says what. Compare that reference with the source."),
        ("REJECT", "The DOI exists nowhere, belongs to a different paper, or the paper is retracted. Fix or remove the citation."),
        (
            "UNVERIFIED",
            "Could not be confirmed automatically (theses, local conference abstracts, DOIs registered outside "
            "CrossRef). This does not mean it is wrong; look it up once yourself.",
        ),
    ),
    "check-file": (
        ("ACCEPT", "The paper's abstract explicitly supports the claim."),
        ("WARN", "The abstract was read but does not explicitly support this exact claim; check the full text."),
        ("REJECT", "Dead DOI, a different paper, contradicting evidence, or a retracted paper."),
        ("UNVERIFIED", "No abstract could be fetched, so the claim was not judged. This does not mean it is wrong."),
    ),
}


class ReportError(ValueError):
    pass


@dataclass(frozen=True)
class ReportRow:
    label: str
    tone: str
    key: str
    detail: str
    doi: str | None
    doi_note: str | None
    reason: str
    evidence: str


def report_format(path: Path) -> ReportFormat:
    suffix = path.suffix.lower()
    if suffix in (".html", ".htm"):
        return "html"
    if suffix == ".md":
        return "md"
    raise ReportError("Unsupported report format; use a .html or .md path for --report")


def rows_from_reference_results(results: list[ReferenceResult]) -> list[ReportRow]:
    rows = []
    for result in results:
        entry = result.entry
        label = _label(result.verdict, result.status)
        evidence = ""
        if result.fetched is not None:
            parts = [result.fetched.title, result.fetched.authors[0] if result.fetched.authors else None]
            parts.append(str(result.fetched.year) if result.fetched.year else None)
            evidence = "CrossRef: " + "; ".join(part for part in parts if part)
        rows.append(
            ReportRow(
                label=label,
                tone=_TONES.get(label, "warn"),
                key=entry.key or f"ref-{entry.index}",
                detail=entry.title or entry.raw,
                doi=entry.doi or result.resolved_doi,
                doi_note=None if entry.doi or not result.resolved_doi else "resolved",
                reason=result.reason,
                evidence=evidence,
            )
        )
    return rows


def rows_from_batch_results(results: list[BatchRowResult]) -> list[ReportRow]:
    rows = []
    for result in results:
        payload = result.payload
        label = _label(str(payload.get("verdict", "WARN")), str(payload.get("status", "")))
        rows.append(
            ReportRow(
                label=label,
                tone=_TONES.get(label, "warn"),
                key=result.row.id or f"row-{result.row.row_number}",
                detail=result.row.claim,
                doi=result.row.doi,
                doi_note=None,
                reason=str(payload.get("reason", "")),
                evidence=str(payload.get("evidence") or ""),
            )
        )
    return rows


def render_report(
    fmt: ReportFormat,
    *,
    command: str,
    source_name: str,
    summary: dict[str, int],
    rows: list[ReportRow],
    generated_at: datetime,
) -> str:
    stamp = f"Generated {generated_at.strftime('%Y-%m-%d %H:%M')} UTC by ref-verify {__version__}"
    if fmt == "html":
        return _render_html(command, source_name, summary, rows, stamp)
    return _render_markdown(command, source_name, summary, rows, stamp)


def write_report(path: Path, content: str) -> None:
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise ReportError(f"Could not write report: {exc}") from exc


def _label(verdict: str, status: str) -> str:
    # A WARN that only means "could not confirm" is shown apart from a WARN about a real
    # mismatch, so readers do not take it as evidence against the reference.
    if verdict == "WARN" and status in _UNVERIFIED_STATUSES:
        return "UNVERIFIED"
    return verdict


def _doi_href(doi: str) -> str | None:
    normalized = normalize_doi(doi)
    if not normalized.startswith("10."):
        return None
    return "https://doi.org/" + quote(normalized, safe="/:;()._-")


def _display_counts(command: str, summary: dict[str, int], rows: list[ReportRow]) -> list[tuple[str, int]]:
    # Counted by the label shown, so the boxes add up to the total; the JSON summary's
    # `warn` also includes the UNVERIFIED rows.
    labels = [label for label, _ in _LEGENDS.get(command, _LEGENDS["check-bib"])]
    counts = [("total", len(rows))] + [(label, sum(row.label == label for row in rows)) for label in labels]
    if summary.get("failed"):
        counts.append(("not checked, rerun", summary["failed"]))
    return counts


def _render_html(command: str, source_name: str, summary: dict[str, int], rows: list[ReportRow], stamp: str) -> str:
    esc = html.escape
    counts = "\n".join(
        f'      <div class="count"><span class="n">{value}</span> <span class="label">{esc(name)}</span></div>'
        for name, value in _display_counts(command, summary, rows)
    )
    legend = "\n".join(
        f'      <li><span class="badge {_TONES[label]}">{esc(label)}</span> {esc(text)}</li>'
        for label, text in _LEGENDS.get(command, _LEGENDS["check-bib"])
    )
    flagged = [row for row in rows if row.tone != "pass"]
    passed = [row for row in rows if row.tone == "pass"]
    sections = []
    if flagged:
        sections.append(_html_section(f"Needs a look ({len(flagged)})", flagged))
    else:
        sections.append(f"    <h2>Needs a look (0)</h2>\n    <p>Nothing to fix: every {_noun(command)} passed.</p>")
    if passed:
        sections.append(_html_section(f"Passed ({len(passed)})", passed))
    body = "\n".join(sections)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ref-verify report: {esc(command)}</title>
  <style>
    :root {{ --ink: #1d2127; --muted: #5d6673; --line: #d9dde3; --bg: #ffffff; --head: #f4f6f8;
      --pass: #1f7a3d; --pass-bg: #e3f4e8; --warn: #8a5a00; --warn-bg: #fdf0d5;
      --reject: #b42318; --reject-bg: #fde5e3; --unverified: #4b5563; --unverified-bg: #eceef1; }}
    @media (prefers-color-scheme: dark) {{
      :root {{ --ink: #e6e8eb; --muted: #a2a9b4; --line: #3a3f47; --bg: #16191d; --head: #20242a;
        --pass: #7fd69a; --pass-bg: #173322; --warn: #f2c36b; --warn-bg: #3a2c10;
        --reject: #f59a91; --reject-bg: #3d1a17; --unverified: #c3c8cf; --unverified-bg: #2b2f35; }}
    }}
    body {{ margin: 0; background: var(--bg); color: var(--ink);
      font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    main {{ max-width: 1100px; margin: 0 auto; padding: 32px 16px 48px; }}
    h1 {{ font-size: 22px; margin: 0 0 4px; }}
    h2 {{ font-size: 17px; margin: 28px 0 8px; }}
    .meta {{ color: var(--muted); margin: 0 0 24px; }}
    .summary {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }}
    .count {{ border: 1px solid var(--line); border-radius: 6px; padding: 8px 14px; min-width: 72px; }}
    .count .n {{ display: block; font-size: 22px; font-weight: 600; }}
    .count .label {{ color: var(--muted); font-size: 13px; }}
    .legend {{ list-style: none; padding: 0; margin: 0 0 8px; color: var(--muted); font-size: 14px; }}
    .legend li {{ margin: 4px 0; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; vertical-align: top; padding: 10px 8px; border-bottom: 1px solid var(--line); }}
    th {{ background: var(--head); font-size: 13px; }}
    td a {{ color: inherit; word-break: break-all; }}
    .detail, .evidence {{ color: var(--muted); font-size: 13px; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }}
    .badge.pass {{ color: var(--pass); background: var(--pass-bg); }}
    .badge.warn {{ color: var(--warn); background: var(--warn-bg); }}
    .badge.reject {{ color: var(--reject); background: var(--reject-bg); }}
    .badge.unverified {{ color: var(--unverified); background: var(--unverified-bg); }}
    footer {{ margin-top: 28px; color: var(--muted); font-size: 13px; }}
  </style>
</head>
<body>
  <main>
    <h1>ref-verify report: {esc(command)}</h1>
    <p class="meta">Input: {esc(source_name)}</p>
    <section class="summary">
{counts}
    </section>
    <ul class="legend">
{legend}
    </ul>
{body}
    <footer>
      <p>{esc(FOOTER_NOTE)}</p>
      <p>{esc(stamp)}</p>
    </footer>
  </main>
</body>
</html>
"""


def _noun(command: str) -> str:
    return "claim" if command == "check-file" else "reference"


def _html_section(heading: str, rows: list[ReportRow]) -> str:
    esc = html.escape
    body_rows = []
    for row in rows:
        href = _doi_href(row.doi) if row.doi else None
        if row.doi and href:
            doi_cell = f'<a href="{esc(href)}">{esc(row.doi)}</a>'
        else:
            doi_cell = esc(row.doi or "-")
        if row.doi_note:
            doi_cell += f" ({esc(row.doi_note)})"
        body_rows.append(
            f'        <tr class="{row.tone}">'
            f'<td><span class="badge {row.tone}">{esc(row.label)}</span></td>'
            f'<td><strong>{esc(row.key)}</strong><div class="detail">{esc(row.detail)}</div></td>'
            f"<td>{doi_cell}</td>"
            f"<td>{esc(row.reason)}</td>"
            f'<td class="evidence">{esc(row.evidence)}</td></tr>'
        )
    tbody = "\n".join(body_rows)
    return f"""    <h2>{esc(heading)}</h2>
    <div class="table-wrap">
    <table>
      <thead><tr><th>Status</th><th>Reference</th><th>DOI</th><th>Reason</th><th>Evidence</th></tr></thead>
      <tbody>
{tbody}
      </tbody>
    </table>
    </div>"""


def _render_markdown(command: str, source_name: str, summary: dict[str, int], rows: list[ReportRow], stamp: str) -> str:
    lines = [
        f"# ref-verify report: {_md_cell(command)}",
        "",
        f"Input: {_md_cell(source_name)}",
        "",
        "**Summary:** " + " · ".join(f"{name} {value}" for name, value in _display_counts(command, summary, rows)),
        "",
    ]
    lines.extend(f"- **{label}**: {_md_cell(text)}" for label, text in _LEGENDS.get(command, _LEGENDS["check-bib"]))
    flagged = [row for row in rows if row.tone != "pass"]
    passed = [row for row in rows if row.tone == "pass"]
    lines.extend(["", f"## Needs a look ({len(flagged)})", ""])
    if flagged:
        lines.extend(_md_table(flagged))
    else:
        lines.append(f"Nothing to fix: every {_noun(command)} passed.")
    if passed:
        lines.extend(["", f"## Passed ({len(passed)})", "", *_md_table(passed)])
    lines.extend(["", f"> {FOOTER_NOTE}", "", stamp, ""])
    return "\n".join(lines)


def _md_table(rows: list[ReportRow]) -> list[str]:
    lines = ["| Status | Reference | DOI | Reason | Evidence |", "|---|---|---|---|---|"]
    for row in rows:
        href = _doi_href(row.doi) if row.doi else None
        doi_cell = f"[{_md_cell(row.doi)}]({href})" if row.doi and href else _md_cell(row.doi or "-")
        if row.doi_note:
            doi_cell += f" ({row.doi_note})"
        reference = _md_cell(row.key) + (f" — {_md_cell(row.detail)}" if row.detail else "")
        lines.append(
            f"| {row.label} | {reference} | {doi_cell} | {_md_cell(row.reason)} | {_md_cell(row.evidence)} |"
        )
    return lines


def _md_cell(value: str) -> str:
    escaped = html.escape(value, quote=False).replace("|", "\\|")
    return " ".join(escaped.split())
