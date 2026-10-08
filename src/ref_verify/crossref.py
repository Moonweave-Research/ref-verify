from __future__ import annotations

import html
import os
import re
import threading
from typing import Any
from urllib.parse import quote, urlencode

from ref_verify.cache import ResponseCache
from ref_verify.doi_check import normalize_doi
from ref_verify.http import USER_AGENT, fetch_json
from ref_verify.models import PaperRecord

# CrossRef's public pool answers one request at a time per client (x-concurrency-limit: 1)
# and returns 429 to the rest, so parallel workers take turns here.
_REQUEST_SLOT = threading.Semaphore(1)


class CrossrefClient:
    def __init__(self, timeout: float = 20.0, *, cache: ResponseCache | None = None) -> None:
        self.timeout = timeout
        self.cache = cache

    def fetch_work(self, doi: str) -> PaperRecord:
        encoded_doi = quote(normalize_doi(doi), safe="")
        with _REQUEST_SLOT:
            payload = fetch_json(
                f"https://api.crossref.org/works/{encoded_doi}",
                headers={"User-Agent": USER_AGENT},
                timeout=self.timeout,
                cache=self.cache,
            )
        return parse_crossref_work(payload["message"])

    def search_bibliographic(self, query: str, rows: int = 3) -> list[PaperRecord]:
        params = {"query.bibliographic": query, "rows": str(rows)}
        mailto = os.environ.get("REF_VERIFY_MAILTO")
        if mailto:
            params["mailto"] = mailto
        payload = fetch_json(
            "https://api.crossref.org/works?" + urlencode(params),
            headers={"User-Agent": USER_AGENT},
            timeout=self.timeout,
            cache=self.cache,
        )
        items = payload.get("message", {}).get("items", [])
        return [parse_crossref_work(item) for item in items if isinstance(item, dict)]


def parse_crossref_work(message: dict[str, Any]) -> PaperRecord:
    doi = str(message.get("DOI") or "")
    title = _first_string(message.get("title")) or "[title missing]"
    authors = [
        author_name
        for author in message.get("author", [])
        if (author_name := _crossref_author_name(author))
    ]
    year = _published_year(message)
    journal = _first_string(message.get("container-title"))
    abstract = _clean_abstract(message.get("abstract"))
    url = message.get("URL")

    return PaperRecord(
        doi=doi,
        title=title,
        authors=authors,
        year=year,
        abstract=abstract,
        source="CrossRef",
        journal=journal,
        url=str(url) if url else None,
        retraction_doi=_retraction_doi(message),
    )


_RETRACTION_UPDATE_TYPES = {"retraction", "withdrawal", "removal", "partial_retraction"}


def _retraction_doi(message: dict[str, Any]) -> str | None:
    # CrossRef lists retraction notices under `updated-by`; the retracted work itself
    # keeps its original DOI, so the metadata alone looks like a normal paper.
    for update in message.get("updated-by") or []:
        if not isinstance(update, dict):
            continue
        if str(update.get("type") or "").lower() in _RETRACTION_UPDATE_TYPES:
            return str(update.get("DOI") or "") or "unknown"
    return None


def _first_string(value: Any) -> str | None:
    if isinstance(value, list) and value:
        return str(value[0]).strip()
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _crossref_author_name(author: Any) -> str:
    if not isinstance(author, dict):
        return ""
    family = str(author.get("family") or "").strip()
    if family:
        return family
    return str(author.get("name") or "").strip()


def _published_year(message: dict[str, Any]) -> int | None:
    for key in ("published-print", "published-online", "published", "issued"):
        date_parts = message.get(key, {}).get("date-parts")
        # Search results sometimes carry `[[null]]` for a date CrossRef does not know.
        if date_parts and date_parts[0] and date_parts[0][0] is not None:
            return int(date_parts[0][0])
    return None


def _clean_abstract(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()
