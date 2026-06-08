from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ref_verify import __version__
from ref_verify.abstract_lookup import AbstractSourceError
from ref_verify.doi_check import normalize_doi
from ref_verify.models import PaperRecord


class PubMedClient:
    source_name = "pubmed"

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout

    def fetch_record(self, doi: str) -> PaperRecord | None:
        normalized = normalize_doi(doi)
        pmids = self._search_pmids(normalized)
        if not pmids:
            raise AbstractSourceError("NOT_FOUND", "PubMed had no record for the DOI.")
        if len(pmids) != 1:
            raise AbstractSourceError("UNSUPPORTED", "PubMed returned multiple records for the DOI.")
        request = Request(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?"
            + urlencode({"db": "pubmed", "id": pmids[0], "retmode": "xml"}),
            headers={
                "User-Agent": (
                    f"ref-verify/{__version__} "
                    "(+https://github.com/Moonweave-Research/ref-verify)"
                )
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                xml_payload = response.read().decode("utf-8")
        except HTTPError as exc:
            if exc.code == 404:
                raise AbstractSourceError("NOT_FOUND", "PubMed had no record for the DOI.") from exc
            raise
        return parse_pubmed_article(xml_payload)

    def _search_pmids(self, doi: str) -> list[str]:
        request = Request(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"
            + urlencode(
                {
                    "db": "pubmed",
                    "term": f"{doi}[AID]",
                    "retmode": "json",
                    "retmax": "2",
                }
            ),
            headers={
                "User-Agent": (
                    f"ref-verify/{__version__} "
                    "(+https://github.com/Moonweave-Research/ref-verify)"
                )
            },
        )
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        ids = payload.get("esearchresult", {}).get("idlist", [])
        return [str(value) for value in ids if str(value).strip()]


def parse_pubmed_article(xml_payload: str) -> PaperRecord | None:
    root = ET.fromstring(xml_payload)
    article = root.find(".//PubmedArticle")
    if article is None:
        return None

    doi = _article_doi(article)
    abstract = _abstract_text(article)
    if not doi or not abstract:
        return None

    return PaperRecord(
        doi=doi,
        title=_text(article.find(".//ArticleTitle")) or "[title missing]",
        authors=_authors(article),
        year=_publication_year(article),
        abstract=abstract,
        source="PubMed",
        journal=_text(article.find(".//Journal/Title")),
        url=f"https://pubmed.ncbi.nlm.nih.gov/{_pmid(article)}/" if _pmid(article) else None,
    )


def _article_doi(article: ET.Element) -> str | None:
    for element in article.findall(".//ArticleId"):
        if element.attrib.get("IdType", "").lower() == "doi":
            return _text(element)
    for element in article.findall(".//ELocationID"):
        if element.attrib.get("EIdType", "").lower() == "doi":
            return _text(element)
    return None


def _abstract_text(article: ET.Element) -> str | None:
    parts = []
    for element in article.findall(".//Abstract/AbstractText"):
        label = element.attrib.get("Label")
        text = _flatten_text(element)
        if not text:
            continue
        parts.append(f"{label}: {text}" if label else text)
    if not parts:
        return None
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _authors(article: ET.Element) -> list[str]:
    names: list[str] = []
    for author in article.findall(".//AuthorList/Author"):
        collective = _text(author.find("CollectiveName"))
        if collective:
            names.append(collective)
            continue
        last_name = _text(author.find("LastName"))
        if last_name:
            names.append(last_name)
    return names


def _publication_year(article: ET.Element) -> int | None:
    for path in (".//ArticleDate/Year", ".//JournalIssue/PubDate/Year"):
        value = _text(article.find(path))
        if value and value.isdigit():
            return int(value)
    medline_date = _text(article.find(".//JournalIssue/PubDate/MedlineDate"))
    if medline_date:
        match = re.search(r"\b(19|20)\d{2}\b", medline_date)
        if match:
            return int(match.group(0))
    return None


def _pmid(article: ET.Element) -> str | None:
    return _text(article.find(".//PMID"))


def _text(element: ET.Element | None) -> str | None:
    if element is None or element.text is None or not element.text.strip():
        return None
    return element.text.strip()


def _flatten_text(element: ET.Element) -> str:
    return "".join(element.itertext()).strip()
