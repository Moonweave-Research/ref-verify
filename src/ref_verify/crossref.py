from __future__ import annotations

import html
import json
import re
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from ref_verify import __version__
from ref_verify.doi_check import normalize_doi
from ref_verify.models import PaperRecord


class CrossrefClient:
    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout

    def fetch_work(self, doi: str) -> PaperRecord:
        encoded_doi = quote(normalize_doi(doi), safe="")
        request = Request(
            f"https://api.crossref.org/works/{encoded_doi}",
            headers={
                "User-Agent": (
                    f"ref-verify/{__version__} "
                    "(+https://github.com/Moonweave-Research/ref-verify)"
                )
            },
        )
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return parse_crossref_work(payload["message"])


def parse_crossref_work(message: dict[str, Any]) -> PaperRecord:
    doi = str(message.get("DOI") or "")
    title = _first_string(message.get("title")) or "[title missing]"
    authors = [
        str(author.get("family") or "").strip()
        for author in message.get("author", [])
        if str(author.get("family") or "").strip()
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
    )


def _first_string(value: Any) -> str | None:
    if isinstance(value, list) and value:
        return str(value[0]).strip()
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _published_year(message: dict[str, Any]) -> int | None:
    for key in ("published-print", "published-online", "published", "issued"):
        date_parts = message.get(key, {}).get("date-parts")
        if date_parts and date_parts[0]:
            return int(date_parts[0][0])
    return None


def _clean_abstract(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()
