from __future__ import annotations

import time
from typing import Protocol

from ref_verify.doi_check import doi_matches
from ref_verify.models import AbstractLookupResult, AbstractSourceAttempt, PaperRecord


class AbstractSourceClient(Protocol):
    source_name: str

    def fetch_record(self, doi: str) -> PaperRecord | None:
        ...


class AbstractSourceError(Exception):
    def __init__(self, status: str, reason: str) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason


def lookup_abstract(
    requested_doi: str,
    crossref_record: PaperRecord,
    fallback_clients: list[AbstractSourceClient] | tuple[AbstractSourceClient, ...] = (),
    *,
    use_crossref_abstract: bool = True,
) -> AbstractLookupResult:
    attempts: list[AbstractSourceAttempt] = []

    if not doi_matches(requested_doi, crossref_record.doi):
        attempts.append(
            AbstractSourceAttempt(
                source="crossref",
                status="DOI_MISMATCH",
                reason="CrossRef returned a DOI that does not match the requested DOI.",
                doi=crossref_record.doi,
            )
        )
        return AbstractLookupResult(
            record=crossref_record,
            abstract_source=None,
            attempts=attempts,
            error_code="DOI_MISMATCH",
        )

    if crossref_record.abstract and use_crossref_abstract:
        attempts.append(
            AbstractSourceAttempt(
                source="crossref",
                status="FOUND",
                reason="CrossRef record included an abstract.",
                doi=crossref_record.doi,
            )
        )
        return AbstractLookupResult(
            record=crossref_record,
            abstract_source="crossref",
            attempts=attempts,
        )

    if crossref_record.abstract and not use_crossref_abstract:
        attempts.append(
            AbstractSourceAttempt(
                source="crossref",
                status="UNSUPPORTED",
                reason="CrossRef abstract was skipped by source selection.",
                doi=crossref_record.doi,
            )
        )
    else:
        attempts.append(
            AbstractSourceAttempt(
                source="crossref",
                status="NO_ABSTRACT",
                reason="CrossRef record had no abstract.",
                doi=crossref_record.doi,
            )
        )

    source_attempts, record, abstract_source = _lookup_fallback_sources(requested_doi, fallback_clients)
    attempts.extend(source_attempts)
    if record is not None:
        return AbstractLookupResult(
            record=record,
            abstract_source=abstract_source,
            attempts=attempts,
        )

    return AbstractLookupResult(
        record=crossref_record,
        abstract_source=None,
        attempts=attempts,
        error_code=_final_error_code(attempts, promote_doi_mismatch=False),
    )


def lookup_selected_abstract(
    requested_doi: str,
    source_clients: list[AbstractSourceClient] | tuple[AbstractSourceClient, ...],
) -> AbstractLookupResult:
    attempts, record, abstract_source = _lookup_fallback_sources(requested_doi, source_clients)
    if record is not None:
        return AbstractLookupResult(
            record=record,
            abstract_source=abstract_source,
            attempts=attempts,
        )
    return AbstractLookupResult(
        record=PaperRecord(
            doi=requested_doi,
            title="[title missing]",
            authors=[],
            year=None,
            abstract=None,
            source="selected abstract source",
        ),
        abstract_source=None,
        attempts=attempts,
        error_code=_final_error_code(attempts, promote_doi_mismatch=True),
    )


def _lookup_fallback_sources(
    requested_doi: str,
    fallback_clients: list[AbstractSourceClient] | tuple[AbstractSourceClient, ...],
) -> tuple[list[AbstractSourceAttempt], PaperRecord | None, str | None]:
    attempts: list[AbstractSourceAttempt] = []
    for client in fallback_clients:
        started = time.monotonic()
        try:
            record = client.fetch_record(requested_doi)
        except AbstractSourceError as exc:
            attempts.append(
                _attempt(client.source_name, exc.status, exc.reason, started)
            )
            continue
        except TimeoutError as exc:
            attempts.append(
                _attempt(client.source_name, "TIMEOUT", str(exc) or "Source lookup timed out.", started)
            )
            continue
        except Exception as exc:
            attempts.append(
                _attempt(client.source_name, "API_ERROR", str(exc) or "Source lookup failed.", started)
            )
            continue

        if record is None:
            attempts.append(
                _attempt(client.source_name, "NO_ABSTRACT", "Source returned no DOI-bound abstract.", started)
            )
            continue
        if not doi_matches(requested_doi, record.doi):
            attempts.append(
                _attempt(
                    client.source_name,
                    "DOI_MISMATCH",
                    "Source returned a DOI that does not match the requested DOI.",
                    started,
                    doi=record.doi,
                )
            )
            continue
        if not record.abstract:
            attempts.append(
                _attempt(
                    client.source_name,
                    "NO_ABSTRACT",
                    "Source record had no abstract.",
                    started,
                    doi=record.doi,
                )
            )
            continue

        attempts.append(
            _attempt(
                client.source_name,
                "FOUND",
                "Source returned a DOI-bound abstract.",
                started,
                doi=record.doi,
            )
        )
        return attempts, record, client.source_name

    return attempts, None, None


def _final_error_code(
    attempts: list[AbstractSourceAttempt],
    *,
    promote_doi_mismatch: bool,
) -> str:
    statuses = [attempt.status for attempt in attempts]
    if promote_doi_mismatch and "DOI_MISMATCH" in statuses:
        return "DOI_MISMATCH"
    if "API_ERROR" in statuses:
        return "SOURCE_API_ERROR"
    if "TIMEOUT" in statuses:
        return "SOURCE_TIMEOUT"
    if "RATE_LIMITED" in statuses:
        return "SOURCE_RATE_LIMITED"
    if "UNSUPPORTED" in statuses and "NO_ABSTRACT" not in statuses:
        return "SOURCE_UNSUPPORTED"
    if statuses and all(status == "NOT_FOUND" for status in statuses):
        return "DOI_NOT_FOUND"
    return "NO_ABSTRACT"


def _attempt(
    source: str,
    status: str,
    reason: str,
    started: float,
    *,
    doi: str | None = None,
) -> AbstractSourceAttempt:
    return AbstractSourceAttempt(
        source=source,
        status=status,
        reason=reason,
        doi=doi,
        elapsed_ms=max(0, round((time.monotonic() - started) * 1000)),
    )
