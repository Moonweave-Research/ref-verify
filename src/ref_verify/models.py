from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CitationInput:
    doi: str
    title: str | None = None
    first_author: str | None = None
    year: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PaperRecord:
    doi: str
    title: str
    authors: list[str]
    year: int | None
    abstract: str | None
    source: str
    journal: str | None = None
    url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MetadataCheckResult:
    verdict: str
    mismatches: list[str]
    reason: str
    provided: CitationInput
    fetched: PaperRecord

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["provided"] = self.provided.to_dict()
        payload["fetched"] = self.fetched.to_dict()
        return payload


@dataclass(frozen=True)
class ClaimSupportResult:
    status: str
    verdict: str
    reason: str
    evidence: str
    paper: PaperRecord
    claim: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["paper"] = self.paper.to_dict()
        return payload
