from __future__ import annotations

import html
import os
import re
import threading
import time
from typing import Any
from urllib.parse import quote, urlencode

from ref_verify.cache import ResponseCache
from ref_verify.doi_check import normalize_doi
from ref_verify.http import USER_AGENT, fetch_json
from ref_verify.models import PaperRecord

# CrossRef's public pool answers one request at a time per client (x-concurrency-limit: 1)
# and returns 429 to the rest, so parallel workers take turns here. Requests that carry a
# `mailto` go to the "polite" pool, which allows three at a time.
_REQUEST_SLOT = threading.Semaphore(1)
_POLITE_REQUEST_SLOT = threading.Semaphore(3)
# Searches are further limited to 1 per second (3 in the polite pool); spacing them out
# avoids a 429 and its backoff, which cost more than the wait.
_SEARCH_INTERVAL_SECONDS = 1.0
_POLITE_SEARCH_INTERVAL_SECONDS = 0.34
_SEARCH_PACING = threading.Lock()
_last_search_started = [float("-inf")]


class CrossrefClient:
    def __init__(self, timeout: float = 20.0, *, cache: ResponseCache | None = None) -> None:
        self.timeout = timeout
        self.cache = cache

    def fetch_work(self, doi: str) -> PaperRecord:
        encoded_doi = quote(normalize_doi(doi), safe="")
        url = f"https://api.crossref.org/works/{encoded_doi}"
        mailto = os.environ.get("REF_VERIFY_MAILTO")
        if mailto:
            url += "?" + urlencode({"mailto": mailto})
        with _POLITE_REQUEST_SLOT if mailto else _REQUEST_SLOT:
            payload = fetch_json(
                url,
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
        url = "https://api.crossref.org/works?" + urlencode(params)
        with _POLITE_REQUEST_SLOT if mailto else _REQUEST_SLOT:
            if self.cache is None or self.cache.get(url) is None:
                _pace_search(_POLITE_SEARCH_INTERVAL_SECONDS if mailto else _SEARCH_INTERVAL_SECONDS)
            payload = fetch_json(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=self.timeout,
                cache=self.cache,
            )
        items = payload.get("message", {}).get("items", [])
        return [parse_crossref_work(item) for item in items if isinstance(item, dict)]

    def registration_agency(self, doi: str) -> str | None:
        # doi.org names the agency that registered a DOI ("Crossref", "DataCite", ...),
        # or reports that the DOI does not exist at all.
        payload = fetch_json(
            "https://doi.org/ra/" + quote(normalize_doi(doi), safe="/"),
            headers={"User-Agent": USER_AGENT},
            timeout=self.timeout,
            cache=self.cache,
        )
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            agency = payload[0].get("RA")
            return str(agency) if agency else None
        return None


def _pace_search(interval: float) -> None:
    with _SEARCH_PACING:
        wait = _last_search_started[0] + interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_search_started[0] = time.monotonic()


def parse_crossref_work(message: dict[str, Any]) -> PaperRecord:
    doi = str(message.get("DOI") or "")
    title = _clean_title(_first_string(message.get("title"))) or "[title missing]"
    subtitle = _clean_title(_first_string(message.get("subtitle")))
    alt_titles = [
        cleaned
        for value in message.get("original-title") or []
        if isinstance(value, str) and (cleaned := _clean_title(value))
    ]
    if subtitle:
        alt_titles.append(f"{title}: {subtitle}")
    # An edited book has editors and no authors; citations list the editors in that place.
    authors = [
        author_name
        for author in message.get("author") or message.get("editor") or []
        if (author_name := _crossref_author_name(author))
    ]
    years = _published_years(message)
    year = years[0] if years else None
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
        alt_titles=alt_titles,
        alt_years=years[1:],
        work_type=str(message["type"]) if message.get("type") else None,
        is_about_other_work=_is_about_other_work(message, title),
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


_TAG = re.compile(r"</?[A-Za-z][^<>]*>")


def _clean_title(value: str | None) -> str | None:
    if not value:
        return None
    # Titles carry JATS markup ("Ti<sub>3</sub>C<sub>2</sub>"), sometimes HTML-escaped
    # ("&lt;title&gt;...&lt;/title&gt;"); readers and citations see only the text.
    text = _TAG.sub("", html.unescape(_TAG.sub("", value)))
    return " ".join(text.split()) or None


# Records that share a paper's title without being the paper: peer-review reports, Faculty
# Opinions recommendations, and correction notices ("Addendum: <title>").
_ABOUT_OTHER_WORK_RELATIONS = {"is-review-of", "is-comment-on"}
_ABOUT_OTHER_WORK_TITLE = re.compile(
    r"^\s*(?:review (?:of|for)\b|decision letter\b|author response\b|reviewer report\b|"
    r"faculty opinions recommendation\b|(?:addendum|erratum|corrigendum|correction)\b\s*(?::|to\b|for\b))",
    re.IGNORECASE,
)


def _is_about_other_work(message: dict[str, Any], title: str) -> bool:
    if message.get("type") == "peer-review":
        return True
    relations = message.get("relation")
    if isinstance(relations, dict) and _ABOUT_OTHER_WORK_RELATIONS & set(relations):
        return True
    return bool(_ABOUT_OTHER_WORK_TITLE.match(title))


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


def _published_years(message: dict[str, Any]) -> list[int]:
    # Print year first; an online-first year that differs is kept too, because citations
    # (and reference managers) use either one.
    years: list[int] = []
    for key in ("published-print", "published-online", "published", "issued"):
        date_parts = (message.get(key) or {}).get("date-parts")
        # Search results sometimes carry `[[null]]` for a date CrossRef does not know.
        if date_parts and date_parts[0] and date_parts[0][0] is not None:
            year = int(date_parts[0][0])
            if year not in years:
                years.append(year)
    return years


def _clean_abstract(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()
