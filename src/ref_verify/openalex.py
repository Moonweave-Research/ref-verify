from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from ref_verify import __version__
from ref_verify.abstract_lookup import AbstractSourceError
from ref_verify.doi_check import normalize_doi
from ref_verify.models import PaperRecord


class OpenAlexClient:
    source_name = "openalex"

    def __init__(self, timeout: float = 20.0, mailto: str | None = None) -> None:
        self.timeout = timeout
        self.mailto = mailto or os.environ.get(
            "REF_VERIFY_OPENALEX_MAILTO",
            "verify@ref-verify.local",
        )

    def fetch_record(self, doi: str) -> PaperRecord | None:
        work_id = quote(f"doi:{normalize_doi(doi)}", safe=":")
        request = Request(
            f"https://api.openalex.org/works/{work_id}?"
            + urlencode({"mailto": self.mailto}),
            headers={
                "User-Agent": (
                    f"ref-verify/{__version__} "
                    "(+https://github.com/Moonweave-Research/ref-verify)"
                )
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 404:
                raise AbstractSourceError("NOT_FOUND", "OpenAlex had no work for the DOI.") from exc
            raise
        return parse_openalex_work(payload)


def parse_openalex_work(payload: dict[str, Any]) -> PaperRecord | None:
    doi = _string_or_none(payload.get("doi"))
    abstract_index = payload.get("abstract_inverted_index")
    abstract = reconstruct_openalex_abstract(abstract_index)
    if not doi or not abstract:
        return None

    return PaperRecord(
        doi=normalize_doi(doi),
        title=_string_or_none(payload.get("title")) or "[title missing]",
        authors=_authors(payload),
        year=_int_or_none(payload.get("publication_year")),
        abstract=abstract,
        source="OpenAlex",
        journal=_journal(payload),
        url=_string_or_none(payload.get("id")),
    )


def reconstruct_openalex_abstract(value: Any) -> str | None:
    if not isinstance(value, dict) or not value:
        return None
    positioned_tokens: list[tuple[int, str]] = []
    for token, positions in value.items():
        if not isinstance(token, str) or not isinstance(positions, list):
            continue
        for position in positions:
            if isinstance(position, int):
                positioned_tokens.append((position, token))
    if not positioned_tokens:
        return None
    tokens = [token for _, token in sorted(positioned_tokens)]
    return _normalize_abstract_spacing(" ".join(tokens))


def _authors(payload: dict[str, Any]) -> list[str]:
    authors = []
    for authorship in payload.get("authorships", []):
        if not isinstance(authorship, dict):
            continue
        author = authorship.get("author")
        if not isinstance(author, dict):
            continue
        name = _string_or_none(author.get("display_name"))
        if name:
            authors.append(name)
    return authors


def _journal(payload: dict[str, Any]) -> str | None:
    location = payload.get("primary_location")
    if not isinstance(location, dict):
        return None
    source = location.get("source")
    if not isinstance(source, dict):
        return None
    return _string_or_none(source.get("display_name"))


def _normalize_abstract_spacing(value: str) -> str:
    normalized = re.sub(r"\s+([,.;:!?%)\]])", r"\1", value)
    normalized = re.sub(r"([(])\s+", r"\1", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _string_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    return None
