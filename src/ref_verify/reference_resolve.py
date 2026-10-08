from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.error import HTTPError

from ref_verify.doi_check import (
    author_matches,
    author_tokens,
    hangul_surname_matches,
    record_titles,
    record_years,
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
# Below this share of the CrossRef title's words, plain reference text is about another paper.
_MAX_SWAPPED_TITLE_OVERLAP = 0.5
# Reference strings start with the author list, so the first author's family name should
# appear among the first few name tokens ("Pelrine R", "R. Pelrine", "Ronald E. Pelrine").
_FIRST_AUTHOR_TOKEN_WINDOW = 4
_HANGUL = re.compile(r"[\uac00-\ud7a3]")


class ReferenceClient(Protocol):
    def fetch_work(self, doi: str) -> PaperRecord:
        ...

    def search_bibliographic(self, query: str, rows: int = 3) -> list[PaperRecord]:
        ...

    def registration_agency(self, doi: str) -> str | None:
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
        return _missing_from_crossref(entry, doi, client)
    if fetched.retraction_doi:
        return _retracted(entry, fetched, resolved_doi=None)

    # Plain-text references carry no parsed title or author; accept them only when the
    # reference text itself shows the CrossRef title and first author for this DOI.
    text_title = next((title for title in record_titles(fetched) if title_in_text(title, entry.raw)), None)
    provided = CitationInput(
        doi=doi,
        title=entry.title or text_title,
        first_author=entry.first_author or _first_author_in_text(entry.raw, fetched),
        year=entry.year,
    )
    metadata = verify_doi_metadata(provided, fetched)
    if metadata.verdict == "PASS":
        status, reason = "VERIFIED", metadata.reason
    elif metadata.verdict == "WARN" and "metadata" in metadata.mismatches:
        if not entry.title and not text_title and _text_names_another_paper(entry.raw, fetched):
            status = "MISMATCH"
            reason = (
                f"This DOI belongs to {_describe(fetched)}, which this reference does not mention; "
                "the DOI may point to a different paper."
            )
        else:
            status, reason = "UNVERIFIED", _insufficient_reason(provided, fetched)
    else:
        status = "MISMATCH"
        lead = (
            "DOI resolves to a materially different paper than provided"
            if metadata.verdict == "REJECT"
            else "DOI matches, but"
        )
        separator = ": " if metadata.verdict == "REJECT" else " "
        details = _differences(metadata.mismatches, provided.year, provided.first_author, fetched)
        reason = f"{lead}{separator}{details}." if details else metadata.reason
    return ReferenceResult(
        entry=entry,
        status=status,
        verdict=metadata.verdict,
        reason=reason,
        mismatches=metadata.mismatches,
        fetched=fetched,
    )


def _missing_from_crossref(entry: ReferenceEntry, doi: str, client: ReferenceClient) -> ReferenceResult:
    try:
        agency = client.registration_agency(doi)
    except Exception:
        agency = None
    # arXiv, Zenodo, and many Korean (KISTI) or Japanese (JaLC) DOIs are registered with
    # another agency, so a CrossRef 404 alone does not make them dead.
    if agency and agency.casefold() != "crossref":
        return ReferenceResult(
            entry=entry,
            status="UNVERIFIED",
            verdict="WARN",
            reason=(
                f"This DOI is registered with {agency}, not CrossRef, so its title and authors "
                f"were not compared; open https://doi.org/{doi} to confirm it is this work."
            ),
            error_code="DOI_NOT_IN_CROSSREF",
        )
    return ReferenceResult(
        entry=entry,
        status="NOT_FOUND",
        verdict="REJECT",
        reason="CrossRef has no record for this DOI (HTTP 404), and doi.org does not list it either.",
        error_code="DOI_NOT_FOUND",
        mismatches=["doi"],
    )


def _text_names_another_paper(text: str, record: PaperRecord) -> bool:
    # Hangul text cannot be compared word-for-word with a romanized English record, so it
    # stays "could not confirm" rather than "different paper".
    if not text or _HANGUL.search(text):
        return False
    overlap = max(title_token_overlap(title, text) for title in record_titles(record))
    return overlap < _MAX_SWAPPED_TITLE_OVERLAP


def _insufficient_reason(provided: CitationInput, fetched: PaperRecord) -> str:
    if provided.title and not provided.first_author and fetched.authors:
        return (
            f"The DOI and title match CrossRef, but its first author ({fetched.authors[0]}) was not "
            "found in the reference; check the author names manually."
        )
    if provided.first_author and not provided.title:
        return (
            f'The DOI and first author match CrossRef, but its title ("{fetched.title}") was not '
            "found in the reference; check the title manually."
        )
    return _INSUFFICIENT_REASON


def _describe(record: PaperRecord) -> str:
    details = [part for part in (record.authors[0] if record.authors else None, record.year) if part]
    suffix = f" ({', '.join(str(part) for part in details)})" if details else ""
    return f'"{record.title}"{suffix}'


def _differences(
    mismatches: list[str],
    year: int | None,
    first_author: str | None,
    record: PaperRecord,
) -> str:
    parts = []
    if "title" in mismatches:
        parts.append(f'the title differs (CrossRef: "{record.title}")')
    if "first_author" in mismatches:
        crossref_author = record.authors[0] if record.authors else "none listed"
        reference = f"reference: {first_author}; " if first_author else ""
        parts.append(f"the first author differs ({reference}CrossRef: {crossref_author})")
    if "year" in mismatches:
        crossref_years = "/".join(str(value) for value in record_years(record)) or "none listed"
        reference = f"reference: {year}; " if year is not None else ""
        parts.append(f"the year differs ({reference}CrossRef: {crossref_years})")
    return " and ".join(parts)


def _resolve_reference(entry: ReferenceEntry, client: ReferenceClient) -> ReferenceResult:
    query = _bibliographic_query(entry)
    candidates = client.search_bibliographic(query, rows=3) if query else []
    for candidate in candidates:
        if not _candidate_matches(entry, candidate):
            continue
        if candidate.retraction_doi:
            return _retracted(entry, candidate, resolved_doi=candidate.doi)
        mismatches = []
        candidate_years = record_years(candidate)
        if entry.year is not None and candidate_years and entry.year not in candidate_years:
            mismatches.append("year")
        if not _first_author_matches(entry, candidate):
            mismatches.append("first_author")
        reason = f"Matched CrossRef record {candidate.doi} by bibliographic search."
        if mismatches:
            details = _differences(mismatches, entry.year, entry.first_author, candidate)
            reason = f"Matched CrossRef record {candidate.doi} by bibliographic search, but {details}."
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
    titles = record_titles(candidate)
    if entry.title:
        if not any(titles_match(entry.title, title) for title in titles):
            return False
    elif not any(
        title_in_text(title, entry.raw) or title_token_overlap(title, entry.raw) >= _MIN_TEXT_TITLE_OVERLAP
        for title in titles
    ):
        return False
    candidate_years = record_years(candidate)
    if entry.year is not None and candidate_years:
        return min(abs(entry.year - year) for year in candidate_years) <= 1
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
    if hangul_surname_matches(text, record.authors[0]):
        return record.authors[0]
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
