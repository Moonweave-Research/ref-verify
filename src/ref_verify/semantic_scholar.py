from __future__ import annotations

import os
import threading
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote

from ref_verify.abstract_lookup import AbstractSourceError
from ref_verify.cache import ResponseCache
from ref_verify.doi_check import normalize_doi
from ref_verify.http import USER_AGENT, fetch_json
from ref_verify.models import PaperRecord

# Unauthenticated Semantic Scholar allows roughly one request per second, so parallel
# check-file workers take turns here instead of tripping each other's 429s.
_REQUEST_SLOT = threading.Semaphore(1)


class SemanticScholarClient:
    source_name = "semantic_scholar"

    def __init__(
        self,
        timeout: float = 20.0,
        *,
        max_retries: int = 3,
        cache: ResponseCache | None = None,
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.cache = cache

    def fetch_record(self, doi: str) -> PaperRecord | None:
        paper_id = quote(f"DOI:{normalize_doi(doi)}", safe=":")
        fields = "title,authors,year,abstract,externalIds,url,venue"
        headers = {"User-Agent": USER_AGENT}
        api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        if api_key:
            headers["x-api-key"] = api_key
        try:
            with _REQUEST_SLOT:
                payload = fetch_json(
                    f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}?fields={fields}",
                    headers=headers,
                    timeout=self.timeout,
                    cache=self.cache,
                    max_retries=self.max_retries,
                )
        except HTTPError as exc:
            if exc.code == 404:
                raise AbstractSourceError("NOT_FOUND", "Semantic Scholar had no paper for the DOI.") from exc
            if exc.code == 429:
                raise AbstractSourceError("RATE_LIMITED", "Semantic Scholar rate limit exceeded.") from exc
            raise
        return parse_semantic_scholar_paper(payload)


def parse_semantic_scholar_paper(payload: dict[str, Any]) -> PaperRecord | None:
    abstract = _string_or_none(payload.get("abstract"))
    if abstract is None:
        return None
    external_ids = payload.get("externalIds")
    doi = ""
    if isinstance(external_ids, dict):
        doi = _string_or_none(external_ids.get("DOI")) or ""
    if not doi:
        return None

    return PaperRecord(
        doi=doi,
        title=_string_or_none(payload.get("title")) or "[title missing]",
        authors=[
            name
            for author in payload.get("authors", [])
            if isinstance(author, dict)
            if (name := _string_or_none(author.get("name")))
        ],
        year=_int_or_none(payload.get("year")),
        abstract=abstract,
        source="Semantic Scholar",
        journal=_string_or_none(payload.get("venue")),
        url=_string_or_none(payload.get("url")),
    )


def _string_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    return None
