from __future__ import annotations

import re
import shutil
import textwrap
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.error import HTTPError, URLError

from ref_verify.doi_check import (
    author_matches,
    author_tokens,
    hangul_surname_matches,
    looks_like_group_author,
    record_titles,
    record_years,
    title_in_text,
    title_token_overlap,
    titles_match,
    verify_doi_metadata,
)
from ref_verify.http import retry_after_seconds as _retry_after_seconds
from ref_verify.models import CitationInput, PaperRecord
from ref_verify.reference_parse import DOI_PATTERN, ReferenceEntry

UNMATCHED_REASON = "No matching CrossRef record was found; verify this reference manually."
_INSUFFICIENT_REASON = (
    "DOI resolves, but the reference does not carry enough matching title and first-author "
    "text to confirm it is this paper; verify this reference manually."
)
_MIN_TEXT_TITLE_OVERLAP = 0.8
# Below this share of the CrossRef title's words, plain reference text is about another paper.
_MAX_SWAPPED_TITLE_OVERLAP = 0.5
# Reference strings start with the author list. The first author is the text before the
# first separator ("Pelrine R, ...", "R. Pelrine, ...", "Pelrine, R., ...", "A. G. Riess et
# al.", "Ronald E. Pelrine and ..."), and the family name sits within its first few words
# ("J. D. van der Waals").
_FIRST_AUTHOR_END = re.compile(r",|;|\(|\s(?:and|&)\s|\set\.?\s*al\b", re.IGNORECASE)
_FIRST_AUTHOR_TOKEN_WINDOW = 6
# Words that are neither title nor author in a citation such as
# "J. Bardeen, L. N. Cooper, and J. R. Schrieffer, Phys. Rev. 108, 1175 (1957)".
_CITATION_FILLER = {
    "al", "and", "et", "vol", "no", "pp", "doi", "https", "http", "org", "dx", "art", "article",
    "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
}
_JOURNAL_STOPWORDS = {"a", "an", "and", "de", "der", "des", "for", "in", "of", "on", "the", "und"}
_DEFAULT_RATE_LIMIT_PAUSE_SECONDS = 15.0
_MAX_RATE_LIMIT_PAUSE_SECONDS = 60.0
_sleep = time.sleep
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
        try:
            return _check_once(entry, client)
        except HTTPError as exc:
            if exc.code != 429:
                raise
            # The HTTP layer gives up when CrossRef asks for a long pause; take that pause
            # once for this reference instead of reporting it unchecked.
            _sleep(_rate_limit_pause(exc))
            return _check_once(entry, client)
    except Exception as exc:
        return ReferenceResult(
            entry=entry,
            status="UNVERIFIED",
            verdict="WARN",
            reason=_check_error_reason(exc),
            error_code="ROW_CHECK_ERROR",
        )


def _check_once(entry: ReferenceEntry, client: ReferenceClient) -> ReferenceResult:
    if entry.doi:
        return _check_doi_reference(entry, entry.doi, client)
    return _resolve_reference(entry, client)


def _rate_limit_pause(exc: HTTPError) -> float:
    retry_after = _retry_after_seconds(exc)
    if retry_after is None:
        return _DEFAULT_RATE_LIMIT_PAUSE_SECONDS
    return min(retry_after, _MAX_RATE_LIMIT_PAUSE_SECONDS)


def _check_error_reason(exc: Exception) -> str:
    if isinstance(exc, HTTPError) and exc.code == 429:
        return (
            "Not checked: CrossRef asked ref-verify to slow down (HTTP 429). Run the same command "
            "again in a minute; references already checked are cached."
        )
    if isinstance(exc, URLError) and not isinstance(exc, HTTPError):
        return f"Not checked: could not reach CrossRef ({exc.reason}). Check the internet connection and run again."
    return f"Reference could not be checked: {exc}"


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
        titleless = None if text_title else _titleless_differences(entry, fetched)
        if titleless == []:
            return ReferenceResult(
                entry=entry,
                status="VERIFIED",
                verdict="PASS",
                reason=(
                    "The reference has no article title; it matches CrossRef's record for this DOI on "
                    f"{_titleless_fields(fetched)}."
                ),
                fetched=fetched,
            )
        if titleless:
            status = "MISMATCH"
            reason = (
                "The reference has no article title, and CrossRef's record for this DOI differs in "
                f"{'; '.join(titleless)}."
            )
        elif not entry.title and not text_title and _text_names_another_paper(entry.raw, fetched):
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
            "found in the reference's first-author position; check the author names manually."
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
    # Five rows, because review reports and notices about a well-known paper can fill the
    # top three results ahead of the paper itself.
    candidates = client.search_bibliographic(query, rows=5) if query else []
    for candidate in candidates:
        if candidate.is_about_other_work:
            continue
        if not _candidate_matches(entry, candidate):
            if _titleless_differences(entry, candidate) == []:
                return ReferenceResult(
                    entry=entry,
                    status="RESOLVED",
                    verdict="PASS",
                    reason=(
                        f"Matched CrossRef record {candidate.doi} by bibliographic search; the reference has "
                        f"no article title, so it was matched on {_titleless_fields(candidate)}."
                    ),
                    error_code="REFERENCE_RESOLVED",
                    resolved_doi=candidate.doi,
                    fetched=candidate,
                )
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
    first_author = record.authors[0]
    if hangul_surname_matches(text, first_author):
        return first_author
    family = author_tokens(first_author)
    if not family:
        return None
    if looks_like_group_author(family):
        # A group author ("Writing Group for the ... Investigators") opens the reference whole.
        group = [token for token in family if token != "the"]
        opening = [token for token in author_tokens(text) if token != "the"][: len(group)]
        return first_author if opening == group else None
    # Only the first author's own name counts, so "Perlmutter S, Riess AG" does not pass for
    # a paper whose first author is Riess.
    first_name = _FIRST_AUTHOR_END.split(text, maxsplit=1)[0]
    if family[-1] in author_tokens(first_name)[:_FIRST_AUTHOR_TOKEN_WINDOW]:
        return first_author
    return None


def _titleless_differences(entry: ReferenceEntry, record: PaperRecord) -> list[str] | None:
    # A citation without an article title ("Phys. Rev. 108, 1175 (1957)") is compared on the
    # fields it does carry. None means it carries a title (words that are not authors,
    # journal, or numbers) or the record has no volume or page to compare; otherwise the list
    # names the fields that disagree, and an empty list means every field agrees.
    if entry.title or not (record.volume or record.first_page):
        return None
    tokens = _plain_tokens(DOI_PATTERN.sub(" ", entry.raw))
    journal_run = next(
        (
            run
            for journal in (record.journal, *record.journal_abbreviations)
            if journal and (run := _journal_run(journal, tokens))
        ),
        None,
    )
    author_words = {token for author in record.authors for token in author_tokens(author)}
    leftover = [
        token
        for index, token in enumerate(tokens)
        if not (journal_run and index in journal_run)
        and token not in author_words
        and token not in _CITATION_FILLER
        and not token.isdigit()
        and len(token) >= 3
    ]
    if len(leftover) >= 3:
        return None
    differences = []
    if not journal_run:
        differences.append(f"journal (CrossRef: {record.journal or 'none listed'})")
    if record.volume and record.volume.casefold() not in tokens:
        differences.append(f"volume (CrossRef: {record.volume})")
    if record.first_page and record.first_page.casefold() not in tokens:
        differences.append(f"first page (CrossRef: {record.first_page})")
    years = record_years(record)
    if entry.year is None or entry.year not in years:
        reference = f"reference: {entry.year}; " if entry.year is not None else ""
        crossref_years = "/".join(str(year) for year in years) or "none listed"
        differences.append(f"year ({reference}CrossRef: {crossref_years})")
    if _first_author_in_text(entry.raw, record) is None:
        differences.append(f"first author (CrossRef: {record.authors[0] if record.authors else 'none listed'})")
    return differences


def _titleless_fields(record: PaperRecord) -> str:
    fields = ["journal"]
    if record.volume:
        fields.append("volume")
    if record.first_page:
        fields.append("first page")
    fields.extend(["year", "first author"])
    return ", ".join(fields[:-1]) + f", and {fields[-1]}"


def _plain_tokens(text: str) -> list[str]:
    folded = "".join(
        char for char in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(char)
    )
    return re.findall(r"[a-z0-9]+", folded)


def _journal_run(journal: str, tokens: list[str]) -> set[int] | None:
    # Full name or a standard abbreviation: "Phys. Rev. Lett." matches "Physical Review
    # Letters" word by word, each abbreviated word being the start of the full one.
    words = [word for word in _plain_tokens(journal) if word not in _JOURNAL_STOPWORDS]
    if not words:
        return None
    positions = [index for index, token in enumerate(tokens) if token not in _JOURNAL_STOPWORDS]
    for start in range(len(positions) - len(words) + 1):
        window = positions[start : start + len(words)]
        if all(words[offset].startswith(tokens[index]) for offset, index in enumerate(window)):
            return set(range(window[0], window[-1] + 1))
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


TEXT_LEGEND = (
    "PASS: matches CrossRef. WARN: check the difference named under it. REJECT: dead DOI, "
    "a different paper, or retracted. UNVERIFIED: could not be confirmed automatically; "
    "that alone does not mean the reference is wrong."
)
_REFERENCE_COLUMN = 42


def render_reference_text(results: list[ReferenceResult], width: int | None = None) -> str:
    width = width or shutil.get_terminal_size((100, 24)).columns
    summary = summarize_references(results)
    rows = []
    for result in results:
        if result.entry.doi:
            doi = result.entry.doi
        elif result.resolved_doi:
            doi = f"{result.resolved_doi} (resolved)"
        else:
            doi = "-"
        # Same label as the report: a WARN that only means "could not confirm" reads apart
        # from a WARN about a real difference.
        label = "UNVERIFIED" if result.verdict == "WARN" and result.status == "UNVERIFIED" else result.verdict
        rows.append((label, _reference_label(result.entry), doi, result))
    label_width = max(len("VERDICT"), *(len(row[0]) for row in rows))
    reference_width = min(_REFERENCE_COLUMN, max(_display_width("REFERENCE"), *(_display_width(row[1]) for row in rows)))
    indent = " " * (label_width + 2)
    # Counted by the label shown, so the numbers add up to the total (JSON `warn` also
    # counts the UNVERIFIED rows).
    counts = {label: sum(row[0] == label for row in rows) for label in ("PASS", "WARN", "REJECT", "UNVERIFIED")}
    noun = "reference" if summary["total"] == 1 else "references"
    headline = f"{summary['total']} {noun}: " + ", ".join(f"{count} {label}" for label, count in counts.items())
    if summary["failed"]:
        headline += f" ({summary['failed']} could not be checked; run the same command again)"
    lines = [headline, ""]
    lines.append(f"{'VERDICT'.ljust(label_width)}  {_fit('REFERENCE', reference_width)}  DOI")
    for label, reference, doi, result in rows:
        lines.append(f"{label.ljust(label_width)}  {_fit(reference, reference_width)}  {doi}")
        # PASS reasons are boilerplate; everything else needs its reason to be acted on.
        if result.verdict != "PASS":
            lines.extend(textwrap.wrap(result.reason, width=max(width, 60), initial_indent=indent, subsequent_indent=indent))
    lines.append("")
    lines.extend(textwrap.wrap(TEXT_LEGEND, width=max(width, 60)))
    return "\n".join(lines)


def _reference_label(entry: ReferenceEntry) -> str:
    if entry.key and not entry.key.isdigit():
        return entry.key
    # Pasted lists have no citation keys, so show where the reference starts.
    number = f"[{entry.key}]" if entry.key else f"{entry.index}."
    return f"{number} {' '.join(entry.raw.split())}"


def _display_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(char) in ("W", "F") else 1 for char in text)


def _fit(text: str, width: int) -> str:
    if _display_width(text) > width:
        while _display_width(text) > width - 1:
            text = text[:-1]
        text = text.rstrip() + "…"
    return text + " " * (width - _display_width(text))
