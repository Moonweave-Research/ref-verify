from __future__ import annotations

import re
import unicodedata
from urllib.parse import unquote

from ref_verify.models import CitationInput, MetadataCheckResult, PaperRecord

_GREEK_LETTER_NAMES = {
    "\u03b1": "alpha",
    "\u03b2": "beta",
    "\u03b3": "gamma",
    "\u03b4": "delta",
    "\u03b5": "epsilon",
    "\u03b6": "zeta",
    "\u03b7": "eta",
    "\u03b8": "theta",
    "\u03b9": "iota",
    "\u03ba": "kappa",
    "\u03bb": "lambda",
    "\u03bc": "mu",
    "\u03bd": "nu",
    "\u03be": "xi",
    "\u03bf": "omicron",
    "\u03c0": "pi",
    "\u03c1": "rho",
    "\u03c2": "sigma",
    "\u03c3": "sigma",
    "\u03c4": "tau",
    "\u03c5": "upsilon",
    "\u03c6": "phi",
    "\u03c7": "chi",
    "\u03c8": "psi",
    "\u03c9": "omega",
}

_GROUP_AUTHOR_TERMS = {
    "association",
    "collaboration",
    "committee",
    "consortium",
    "group",
    "network",
    "organisation",
    "organization",
    "society",
    "team",
    "working",
}


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
    provided_tokens = _author_tokens(provided)
    fetched_tokens = _author_tokens(fetched)
    if not provided_tokens or not fetched_tokens:
        return False
    if _looks_like_group_author(provided_tokens) or _looks_like_group_author(
        fetched_tokens,
    ):
        return provided_tokens == fetched_tokens
    return provided_tokens[-1] == fetched_tokens[-1]


def _author_tokens(value: str) -> list[str]:
    normalized = _strip_diacritics(value.casefold())
    cleaned = re.sub(r"[^a-z -]", " ", normalized).strip()
    return [part for part in re.split(r"\s+", cleaned) if part]


def _looks_like_group_author(tokens: list[str]) -> bool:
    return bool(set(tokens) & _GROUP_AUTHOR_TERMS)


def _numbers(value: str) -> list[str]:
    return [
        number.replace(",", "")
        for number in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", value)
    ]


def _title_tokens(value: str) -> list[str]:
    normalized = _transliterate_greek_letters(_strip_diacritics(value.casefold()))
    return [_singularize(token) for token in re.findall(r"[^\W_]+", normalized)]


def _singularize(token: str) -> str:
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token


def _strip_diacritics(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )


def _transliterate_greek_letters(value: str) -> str:
    return "".join(
        f" {_GREEK_LETTER_NAMES[char]} " if char in _GREEK_LETTER_NAMES else char
        for char in value
    )
