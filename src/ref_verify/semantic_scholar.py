from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from ref_verify import __version__
from ref_verify.abstract_lookup import AbstractSourceError
from ref_verify.doi_check import normalize_doi
from ref_verify.models import PaperRecord


class SemanticScholarClient:
    source_name = "semantic_scholar"

    def __init__(
        self,
        timeout: float = 20.0,
        *,
        max_retries: int = 1,
        retry_delay: float = 2.0,
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def fetch_record(self, doi: str) -> PaperRecord | None:
        paper_id = quote(f"DOI:{normalize_doi(doi)}", safe=":")
        fields = "title,authors,year,abstract,externalIds,url,venue"
        headers = {
            "User-Agent": (
                f"ref-verify/{__version__} "
                "(+https://github.com/Moonweave-Research/ref-verify)"
            )
        }
        api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        if api_key:
            headers["x-api-key"] = api_key
        request = Request(
            f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}?fields={fields}",
            headers=headers,
        )
        payload = self._fetch_json(request)
        return parse_semantic_scholar_paper(payload)

    def _fetch_json(self, request: Request) -> dict[str, Any]:
        for attempt in range(self.max_retries + 1):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                if exc.code == 404:
                    raise AbstractSourceError("NOT_FOUND", "Semantic Scholar had no paper for the DOI.") from exc
                if exc.code == 429:
                    if attempt < self.max_retries:
                        time.sleep(self.retry_delay)
                        continue
                    raise AbstractSourceError(
                        "RATE_LIMITED",
                        "Semantic Scholar rate limit exceeded.",
                    ) from exc
                raise
        raise AbstractSourceError("API_ERROR", "Semantic Scholar lookup failed.")


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
