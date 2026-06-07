from __future__ import annotations

import re
from difflib import SequenceMatcher

from ref_verify.models import CitationInput, MetadataCheckResult, PaperRecord


def verify_doi_metadata(
    provided: CitationInput,
    fetched: PaperRecord,
) -> MetadataCheckResult:
    mismatches: list[str] = []

    if not _has_comparison_metadata(provided):
        mismatches.append("metadata")

    if provided.title and not _titles_match(provided.title, fetched.title):
        mismatches.append("title")

    if provided.first_author and not _author_matches(
        provided.first_author,
        fetched.authors[0] if fetched.authors else None,
    ):
        mismatches.append("first_author")

    if provided.year is not None and (
        fetched.year is None or provided.year != fetched.year
    ):
        mismatches.append("year")

    if not mismatches:
        verdict = "PASS"
        reason = "Provided citation metadata matches the fetched CrossRef record."
    elif any(field in mismatches for field in ("title", "first_author")):
        verdict = "REJECT"
        reason = "DOI resolves to a materially different paper than provided."
    elif "metadata" in mismatches:
        verdict = "WARN"
        reason = "No citation metadata was provided to compare against the fetched CrossRef record."
    else:
        verdict = "WARN"
        reason = "DOI resolves, but minor metadata differs from the provided citation."

    return MetadataCheckResult(
        verdict=verdict,
        mismatches=mismatches,
        reason=reason,
        provided=provided,
        fetched=fetched,
    )


def _has_comparison_metadata(provided: CitationInput) -> bool:
    return bool(provided.title or provided.first_author or provided.year is not None)


def _titles_match(provided: str, fetched: str) -> bool:
    if _numbers(provided) != _numbers(fetched):
        return False

    normalized_provided = _normalize_text(provided)
    normalized_fetched = _normalize_text(fetched)
    if normalized_provided == normalized_fetched:
        return True
    return SequenceMatcher(None, normalized_provided, normalized_fetched).ratio() >= 0.88


def _author_matches(provided: str, fetched: str | None) -> bool:
    if not fetched:
        return False
    return _normalize_author(provided) == _normalize_author(fetched)


def _normalize_author(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z -]", " ", value).strip().lower()
    parts = [part for part in re.split(r"\s+", cleaned) if part]
    return parts[-1] if parts else ""


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def _numbers(value: str) -> list[str]:
    return [
        number.replace(",", "")
        for number in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", value)
    ]
