from __future__ import annotations

import re
from urllib.parse import unquote

from ref_verify.models import CitationInput, MetadataCheckResult, PaperRecord


def verify_doi_metadata(
    provided: CitationInput,
    fetched: PaperRecord,
) -> MetadataCheckResult:
    mismatches: list[str] = []

    if provided.doi and not doi_matches(provided.doi, fetched.doi):
        mismatches.append("doi")

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
    elif any(field in mismatches for field in ("doi", "title", "first_author")):
        verdict = "REJECT"
        reason = "DOI resolves to a materially different paper than provided."
    elif "metadata" in mismatches:
        verdict = "WARN"
        reason = "Insufficient citation metadata was provided to verify the fetched CrossRef record."
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
    return bool(provided.title and provided.first_author)


def doi_matches(provided: str, fetched: str) -> bool:
    return normalize_doi(provided) == normalize_doi(fetched)


def normalize_doi(value: str) -> str:
    normalized = value.strip().casefold()
    normalized = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", normalized)
    normalized = re.sub(r"^doi:\s*", "", normalized)
    normalized = unquote(normalized)
    return _strip_trailing_doi_punctuation(normalized)


def _strip_trailing_doi_punctuation(value: str) -> str:
    stripped = value.strip()
    while stripped:
        without_sentence_punctuation = stripped.rstrip(".,;:")
        if without_sentence_punctuation != stripped:
            stripped = without_sentence_punctuation.rstrip()
            continue
        if stripped.endswith(")") and stripped.count(")") > stripped.count("("):
            stripped = stripped[:-1].rstrip()
            continue
        return stripped
    return stripped


def _titles_match(provided: str, fetched: str) -> bool:
    if _numbers(provided) != _numbers(fetched):
        return False

    return _title_tokens(provided) == _title_tokens(fetched)


def _author_matches(provided: str, fetched: str | None) -> bool:
    if not fetched:
        return False
    return _normalize_author(provided) == _normalize_author(fetched)


def _normalize_author(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z -]", " ", value).strip().lower()
    parts = [part for part in re.split(r"\s+", cleaned) if part]
    return parts[-1] if parts else ""


def _numbers(value: str) -> list[str]:
    return [
        number.replace(",", "")
        for number in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", value)
    ]


def _title_tokens(value: str) -> list[str]:
    return [_singularize(token) for token in re.findall(r"[^\W_]+", value.casefold())]


def _singularize(token: str) -> str:
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token
