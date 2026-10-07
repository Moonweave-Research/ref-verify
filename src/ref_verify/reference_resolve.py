from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.error import HTTPError

from ref_verify.doi_check import (
    author_matches,
    author_tokens,
    title_in_text,
    title_token_overlap,
    titles_match,
    verify_doi_metadata,
)
from ref_verify.models import CitationInput, PaperRecord
from ref_verify.reference_parse import ReferenceEntry

UNMATCHED_REASON = "No matching CrossRef record was found; verify this reference manually."
_INSUFFICIENT_REASON = (
    "DOI resolves, but the reference does not carry enough matching title and first-author "
    "text to confirm it is this paper; verify this reference manually."
)
_MIN_TEXT_TITLE_OVERLAP = 0.8
# Reference strings start with the author list, so the first author's family name should
# appear among the first few name tokens ("Pelrine R", "R. Pelrine", "Ronald E. Pelrine").
_FIRST_AUTHOR_TOKEN_WINDOW = 4
_MISMATCH_LABELS = {"year": "the year", "first_author": "the first author"}


class ReferenceClient(Protocol):
    def fetch_work(self, doi: str) -> PaperRecord:
        ...

    def search_bibliographic(self, query: str, rows: int = 3) -> list[PaperRecord]:
        ...


@dataclass(frozen=True)
class ReferenceResult:
    entry: ReferenceEntry
    status: str
    verdict: str
    reason: str
    error_code: str | None = None
    mismatches: list[str] = field(default_factory=list)
    resolved_doi: str | None = None
    fetched: PaperRecord | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.entry.index,
            "key": self.entry.key,
            "doi": self.entry.doi,
            "status": self.status,
            "verdict": self.verdict,
            "reason": self.reason,
            "error_code": self.error_code,
            "mismatches": list(self.mismatches),
            "resolved_doi": self.resolved_doi,
            "reference": self.entry.to_dict(),
            "fetched": self.fetched.to_dict() if self.fetched else None,
        }


def check_reference(entry: ReferenceEntry, client: ReferenceClient) -> ReferenceResult:
    try:
        if entry.doi:
            return _check_doi_reference(entry, entry.doi, client)
        return _resolve_reference(entry, client)
    except Exception as exc:
        return ReferenceResult(
            entry=entry,
            status="UNVERIFIED",
            verdict="WARN",
            reason=f"Reference could not be checked: {exc}",
            error_code="ROW_CHECK_ERROR",
        )


def _check_doi_reference(entry: ReferenceEntry, doi: str, client: ReferenceClient) -> ReferenceResult:
    try:
        fetched = client.fetch_work(doi)
    except HTTPError as exc:
        if exc.code != 404:
            raise
        return ReferenceResult(
            entry=entry,
            status="NOT_FOUND",
            verdict="REJECT",
            reason="CrossRef has no record for this DOI (HTTP 404).",
            error_code="DOI_NOT_FOUND",
            mismatches=["doi"],
        )
    if fetched.retraction_doi:
        return _retracted(entry, fetched, resolved_doi=None)

    # Plain-text references carry no parsed title or author; accept them only when the
    # reference text itself shows the CrossRef title and first author for this DOI.
    provided = CitationInput(
        doi=doi,
        title=entry.title or (fetched.title if title_in_text(fetched.title, entry.raw) else None),
        first_author=entry.first_author or _first_author_in_text(entry.raw, fetched),
        year=entry.year,
    )
    metadata = verify_doi_metadata(provided, fetched)
    if metadata.verdict == "PASS":
        status, reason = "VERIFIED", metadata.reason
    elif metadata.verdict == "WARN" and "metadata" in metadata.mismatches:
        status, reason = "UNVERIFIED", _INSUFFICIENT_REASON
    else:
        status, reason = "MISMATCH", metadata.reason
    return ReferenceResult(
        entry=entry,
        status=status,
        verdict=metadata.verdict,
        reason=reason,
        mismatches=metadata.mismatches,
        fetched=fetched,
    )


def _resolve_reference(entry: ReferenceEntry, client: ReferenceClient) -> ReferenceResult:
    query = _bibliographic_query(entry)
    candidates = client.search_bibliographic(query, rows=3) if query else []
    for candidate in candidates:
        if not _candidate_matches(entry, candidate):
            continue
        if candidate.retraction_doi:
            return _retracted(entry, candidate, resolved_doi=candidate.doi)
        mismatches = []
        if entry.year is not None and candidate.year is not None and entry.year != candidate.year:
            mismatches.append("year")
        if not _first_author_matches(entry, candidate):
            mismatches.append("first_author")
        reason = f"Matched CrossRef record {candidate.doi} by bibliographic search."
        if mismatches:
            labels = [_MISMATCH_LABELS[name] for name in mismatches]
            verb = "differ" if len(labels) > 1 else "differs"
            reason = (
                f"Matched CrossRef record {candidate.doi} by bibliographic search, but "
                f"{' and '.join(labels)} {verb} from the reference."
            )
        return ReferenceResult(
            entry=entry,
            status="RESOLVED",
            verdict="WARN" if mismatches else "PASS",
            reason=reason,
            error_code="REFERENCE_RESOLVED",
            mismatches=mismatches,
            resolved_doi=candidate.doi,
            fetched=candidate,
        )
    return ReferenceResult(
        entry=entry,
        status="UNVERIFIED",
        verdict="WARN",
        reason=UNMATCHED_REASON,
        error_code="REFERENCE_UNMATCHED",
    )


def _bibliographic_query(entry: ReferenceEntry) -> str:
    if entry.title:
        parts = (entry.title, entry.first_author, entry.year, entry.journal)
        return " ".join(str(part) for part in parts if part)
    return entry.raw.strip()


def _candidate_matches(entry: ReferenceEntry, candidate: PaperRecord) -> bool:
    if entry.title:
        if not titles_match(entry.title, candidate.title):
            return False
    elif title_token_overlap(candidate.title, entry.raw) < _MIN_TEXT_TITLE_OVERLAP:
        return False
    if entry.year is not None and candidate.year is not None:
        return abs(entry.year - candidate.year) <= 1
    return True


def _first_author_matches(entry: ReferenceEntry, candidate: PaperRecord) -> bool:
    if entry.first_author:
        return author_matches(entry.first_author, candidate.authors[0] if candidate.authors else None)
    if entry.title:
        # A structured entry without an author field has nothing to compare.
        return True
    return _first_author_in_text(entry.raw, candidate) is not None


def _first_author_in_text(text: str, record: PaperRecord) -> str | None:
    if not text or not record.authors:
        return None
    family = author_tokens(record.authors[0])
    if family and family[-1] in author_tokens(text)[:_FIRST_AUTHOR_TOKEN_WINDOW]:
        return record.authors[0]
    return None


def _retracted(entry: ReferenceEntry, record: PaperRecord, *, resolved_doi: str | None) -> ReferenceResult:
    return ReferenceResult(
        entry=entry,
        status="RETRACTED",
        verdict="REJECT",
        reason=(
            "CrossRef records this paper as retracted "
            f"(notice DOI {record.retraction_doi}); do not use it as a source."
        ),
        error_code="PAPER_RETRACTED",
        mismatches=["retracted"],
        resolved_doi=resolved_doi,
        fetched=record,
    )


def summarize_references(results: list[ReferenceResult]) -> dict[str, int]:
    return {
        "total": len(results),
        "pass": sum(result.verdict == "PASS" for result in results),
        "warn": sum(result.verdict == "WARN" for result in results),
        "reject": sum(result.verdict == "REJECT" for result in results),
        "unverified": sum(result.status == "UNVERIFIED" for result in results),
        "failed": sum(result.error_code == "ROW_CHECK_ERROR" for result in results),
    }


def reference_payload(results: list[ReferenceResult]) -> dict[str, Any]:
    return {
        "summary": summarize_references(results),
        "results": [result.to_dict() for result in results],
    }


def render_reference_text(results: list[ReferenceResult]) -> str:
    summary = summarize_references(results)
    rows = [("VERDICT", "KEY", "DOI", "REASON")]
    for result in results:
        if result.entry.doi:
            doi = result.entry.doi
        elif result.resolved_doi:
            doi = f"{result.resolved_doi} (resolved)"
        else:
            doi = "-"
        rows.append((result.verdict, result.entry.key or f"ref-{result.entry.index}", doi, result.reason))
    widths = [max(len(row[column]) for row in rows) for column in range(3)]
    lines = ["Summary: " + " ".join(f"{name}={count}" for name, count in summary.items()), ""]
    for row in rows:
        lines.append("  ".join(cell.ljust(width) for cell, width in zip(row[:3], widths)) + "  " + row[3])
    return "\n".join(lines)
