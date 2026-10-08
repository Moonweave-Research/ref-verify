from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence, TypeVar
from urllib.error import HTTPError

from ref_verify.abstract_lookup import (
    AbstractSourceClient,
    lookup_abstract,
    lookup_selected_abstract,
)
from ref_verify.batch import (
    BatchInputError,
    BatchRowResult,
    ClaimInputRow,
    batch_payload,
    parse_claim_file,
    render_batch_text,
)
from ref_verify.cache import ResponseCache, default_cache
from ref_verify.claim_check import check_claim_support, retracted_claim_result
from ref_verify.crossref import CrossrefClient
from ref_verify.doi_check import normalize_doi, verify_doi_metadata
from ref_verify.models import CitationInput, ClaimSupportResult
from ref_verify.openalex import OpenAlexClient
from ref_verify.pubmed import PubMedClient
from ref_verify.reference_parse import ReferenceEntry, ReferenceInputError, parse_reference_file
from ref_verify.reference_resolve import (
    ReferenceResult,
    check_reference,
    reference_payload,
    render_reference_text,
)
from ref_verify.report import (
    ReportError,
    ReportFormat,
    ReportRow,
    render_report,
    report_format,
    rows_from_batch_results,
    rows_from_reference_results,
    write_report,
)
from ref_verify.semantic_scholar import SemanticScholarClient

T = TypeVar("T")
R = TypeVar("R")


def main(
    argv: Sequence[str] | None = None,
    *,
    client: CrossrefClient | None = None,
    abstract_clients: Sequence[AbstractSourceClient] | None = None,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    cache = None if args.no_cache else default_cache()
    lookup_client = client or CrossrefClient(cache=cache)
    fallback_clients = (
        list(abstract_clients) if abstract_clients is not None else _default_abstract_clients(cache)
    )

    try:
        if args.command == "verify-doi":
            return _verify_doi(args, lookup_client)
        if args.command == "check-claim":
            return _check_claim(args, lookup_client, fallback_clients)
        if args.command == "check-file":
            return _check_file(args, lookup_client, fallback_clients)
        if args.command == "check-bib":
            return _check_bib(args, lookup_client)
    except KeyboardInterrupt:
        resume = " Finished lookups are cached, so rerunning the same command resumes quickly." if cache else ""
        print(f"\nInterrupted.{resume}", file=sys.stderr)
        return 130
    except Exception as exc:
        _emit({"error": str(exc)}, as_json=getattr(args, "json", False))
        return 1

    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ref-verify",
        description="Verify citation metadata and abstract-grounded claims.",
    )
    no_cache_help = "Skip the on-disk HTTP response cache (same as REF_VERIFY_NO_CACHE=1)."
    parser.add_argument("--no-cache", action="store_true", help=no_cache_help)
    # Also accept the flag after the subcommand; SUPPRESS keeps the subparser from
    # resetting a top-level --no-cache back to False.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--no-cache", action="store_true", default=argparse.SUPPRESS, help=no_cache_help)
    report_help = "Also write a self-contained verdict report; .html or .md picks the format."
    subparsers = parser.add_subparsers(dest="command")

    verify = subparsers.add_parser("verify-doi", help="Check DOI metadata", parents=[common])
    verify.add_argument("doi")
    verify.add_argument("--title")
    verify.add_argument("--first-author")
    verify.add_argument("--year", type=int)
    verify.add_argument("--json", action="store_true")

    claim = subparsers.add_parser(
        "check-claim",
        help="Check a claim against a DOI abstract",
        parents=[common],
    )
    claim.add_argument("doi")
    claim.add_argument("--claim", required=True)
    claim.add_argument(
        "--source",
        choices=("auto", "crossref", "openalex", "semantic-scholar", "pubmed"),
        default="auto",
        help="Select an abstract source for debugging; default tries DOI-bound fallback sources.",
    )
    claim.add_argument("--json", action="store_true")

    check_file = subparsers.add_parser(
        "check-file",
        help="Check claims from a JSONL or CSV file",
        parents=[common],
    )
    check_file.add_argument("path")
    check_file.add_argument("--format", choices=("jsonl", "csv"))
    check_file.add_argument(
        "--workers",
        type=_positive_int,
        default=4,
        help="Rows checked in parallel (default 4); output keeps input order.",
    )
    check_file.add_argument("--report", help=report_help)
    check_file.add_argument("--json", action="store_true")

    check_bib = subparsers.add_parser(
        "check-bib",
        help="Check a BibTeX, RIS, or plain-text reference list against CrossRef",
        parents=[common],
    )
    check_bib.add_argument("path")
    check_bib.add_argument(
        "--format",
        choices=("bib", "ris", "txt"),
        help="Input format; default is inferred from .bib, .ris, .txt, or .md.",
    )
    check_bib.add_argument(
        "--workers",
        type=_positive_int,
        default=4,
        help="References checked in parallel (default 4); output keeps input order.",
    )
    check_bib.add_argument("--report", help=report_help)
    check_bib.add_argument("--json", action="store_true")

    return parser


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {value!r}") from None
    if number < 1:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {value!r}")
    return number


def _verify_doi(args: argparse.Namespace, client: CrossrefClient) -> int:
    lookup_doi = normalize_doi(args.doi)
    provided = CitationInput(
        doi=args.doi,
        title=args.title,
        first_author=args.first_author,
        year=args.year,
    )
    try:
        fetched = client.fetch_work(lookup_doi)
    except HTTPError as exc:
        if not _is_not_found(exc):
            raise
        # A dead DOI is a verdict, not a tool failure; keep the `verdict` key so
        # callers that parse JSON do not have to special-case the error shape.
        _emit(
            {
                "verdict": "REJECT",
                "mismatches": ["doi"],
                "reason": "CrossRef has no record for this DOI (HTTP 404).",
                "provided": provided.to_dict(),
                "fetched": None,
                "error_code": "DOI_NOT_FOUND",
            },
            as_json=args.json,
        )
        return 2
    result = verify_doi_metadata(provided, fetched)
    _emit(result.to_dict(), as_json=args.json)
    return 0 if result.verdict == "PASS" else 2


def _check_claim(
    args: argparse.Namespace,
    client: CrossrefClient,
    fallback_clients: Sequence[AbstractSourceClient],
) -> int:
    payload = _run_claim_check(args.doi, args.claim, args.source, client, fallback_clients)
    _emit(payload, as_json=args.json)
    return 0 if payload.get("verdict") == "ACCEPT" else 2


def _check_file(
    args: argparse.Namespace,
    client: CrossrefClient,
    fallback_clients: Sequence[AbstractSourceClient],
) -> int:
    try:
        report = _report_target(args)
        rows = parse_claim_file(Path(args.path), args.format)
    except (BatchInputError, ReportError) as exc:
        _emit({"error": str(exc)}, as_json=args.json)
        return 1

    def check_row(row: ClaimInputRow) -> BatchRowResult:
        try:
            payload = _run_claim_check(row.doi, row.claim, row.source, client, fallback_clients)
        except Exception as exc:
            payload = _row_error_payload(row.claim, exc)
        return BatchRowResult(row=row, payload=payload)

    results = _run_parallel(check_row, rows, args.workers, progress=_progress_label(args, "claims"))
    payload = batch_payload(results)
    if report is not None:
        try:
            _write_report(
                report,
                "check-file",
                Path(args.path).name,
                payload["summary"],
                rows_from_batch_results(results),
            )
        except ReportError as exc:
            _emit({"error": str(exc)}, as_json=args.json)
            return 1
    if args.json:
        _emit(payload, as_json=True)
    else:
        print(render_batch_text(results))
    summary = payload["summary"]
    return 0 if summary["total"] == summary["accept"] else 2


def _check_bib(args: argparse.Namespace, client: CrossrefClient) -> int:
    try:
        report = _report_target(args)
        entries = parse_reference_file(Path(args.path), args.format)
    except (ReferenceInputError, ReportError) as exc:
        _emit({"error": str(exc)}, as_json=args.json)
        return 1

    def check_entry(entry: ReferenceEntry) -> ReferenceResult:
        return check_reference(entry, client)

    results = _run_parallel(check_entry, entries, args.workers, progress=_progress_label(args, "references"))
    payload = reference_payload(results)
    if report is not None:
        try:
            _write_report(
                report,
                "check-bib",
                Path(args.path).name,
                payload["summary"],
                rows_from_reference_results(results),
            )
        except ReportError as exc:
            _emit({"error": str(exc)}, as_json=args.json)
            return 1
    if args.json:
        _emit(payload, as_json=True)
    else:
        print(render_reference_text(results))
    summary = payload["summary"]
    return 0 if summary["total"] == summary["pass"] else 2


def _report_target(args: argparse.Namespace) -> tuple[Path, ReportFormat] | None:
    if not args.report:
        return None
    path = Path(args.report)
    return path, report_format(path)


def _write_report(
    target: tuple[Path, ReportFormat],
    command: str,
    source_name: str,
    summary: dict[str, int],
    rows: list[ReportRow],
) -> None:
    path, fmt = target
    content = render_report(
        fmt,
        command=command,
        source_name=source_name,
        summary=summary,
        rows=rows,
        generated_at=datetime.now(timezone.utc),
    )
    write_report(path, content)


def _progress_label(args: argparse.Namespace, noun: str) -> str | None:
    # Progress goes to stderr and only to a terminal, so JSON and piped output stay clean.
    if args.json or not sys.stderr.isatty():
        return None
    return f"Checking {noun}"


def _run_parallel(
    function: Callable[[T], R],
    items: Sequence[T],
    workers: int,
    *,
    progress: str | None = None,
) -> list[R]:
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(function, item) for item in items]
        try:
            if progress:
                for done, _ in enumerate(as_completed(futures), start=1):
                    sys.stderr.write(f"\r{progress}: {done}/{len(futures)}")
                    sys.stderr.flush()
                sys.stderr.write("\r\033[K")
                sys.stderr.flush()
            return [future.result() for future in futures]
        except BaseException:
            # Without this, Ctrl-C would wait for every queued item before exiting.
            for future in futures:
                future.cancel()
            raise


def _run_claim_check(
    doi: str,
    claim: str,
    source: str,
    client: CrossrefClient,
    fallback_clients: Sequence[AbstractSourceClient],
) -> dict:
    lookup_doi = normalize_doi(doi)
    selected_clients = _select_abstract_clients(fallback_clients, source)
    if source in ("auto", "crossref"):
        try:
            fetched = client.fetch_work(lookup_doi)
        except HTTPError as exc:
            if not _is_not_found(exc):
                raise
            return _doi_not_found_payload(claim)
        if fetched.retraction_doi:
            # Fallback abstract sources would drop the retraction flag, so decide here.
            result = retracted_claim_result(fetched, claim)
            payload = result.to_dict()
            payload["abstract_source"] = None
            payload["source_attempts"] = []
            payload["error_code"] = "PAPER_RETRACTED"
            return payload
        lookup_result = lookup_abstract(lookup_doi, fetched, selected_clients)
    else:
        lookup_result = lookup_selected_abstract(lookup_doi, selected_clients)
    if lookup_result.error_code == "DOI_MISMATCH":
        result = ClaimSupportResult(
            status="UNVERIFIABLE",
            verdict="WARN",
            reason="Fetched DOI does not match the requested DOI.",
            evidence="",
            paper=lookup_result.record,
            claim=claim,
        )
        return _claim_payload(result, lookup_result)

    result = check_claim_support(lookup_result.record, claim)
    return _claim_payload(result, lookup_result)


def _is_not_found(exc: HTTPError) -> bool:
    return getattr(exc, "code", None) == 404


def _doi_not_found_payload(claim: str) -> dict:
    return {
        "status": "UNVERIFIABLE",
        "verdict": "REJECT",
        "reason": "CrossRef has no record for this DOI (HTTP 404).",
        "evidence": "",
        "paper": None,
        "claim": claim,
        "abstract_source": None,
        "source_attempts": [],
        "error_code": "DOI_NOT_FOUND",
    }


def _row_error_payload(claim: str, exc: Exception) -> dict:
    return {
        "status": "UNVERIFIABLE",
        "verdict": "WARN",
        "reason": f"Row could not be checked: {exc}",
        "evidence": "",
        "claim": claim,
        "abstract_source": None,
        "source_attempts": [],
        "error_code": "ROW_CHECK_ERROR",
    }


def _claim_payload(result: ClaimSupportResult, lookup_result) -> dict:
    payload = result.to_dict()
    payload["abstract_source"] = lookup_result.abstract_source
    payload["source_attempts"] = [attempt.to_dict() for attempt in lookup_result.attempts]
    payload["error_code"] = lookup_result.error_code or _claim_error_code(result)
    return payload


def _claim_error_code(result: ClaimSupportResult) -> str:
    if result.verdict == "ACCEPT":
        return "CLAIM_SUPPORTED"
    if result.status == "RETRACTED":
        return "PAPER_RETRACTED"
    if result.status == "UNVERIFIABLE":
        return "NO_ABSTRACT"
    if result.status == "PARTIAL":
        if "does not explicitly support" in result.reason:
            return "CLAIM_NOT_EXPLICIT"
        return "CLAIM_AMBIGUOUS"
    return "CLAIM_NOT_EXPLICIT"


def _default_abstract_clients(cache: ResponseCache | None = None) -> list[AbstractSourceClient]:
    return [OpenAlexClient(cache=cache), SemanticScholarClient(cache=cache), PubMedClient(cache=cache)]


def _select_abstract_clients(
    fallback_clients: Sequence[AbstractSourceClient],
    source: str,
) -> Sequence[AbstractSourceClient]:
    if source in ("auto", "crossref"):
        return [] if source == "crossref" else fallback_clients
    source_name = source.replace("-", "_")
    return [client for client in fallback_clients if client.source_name == source_name]


def _emit(payload: dict, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if "error" in payload:
        print(f"ERROR: {payload['error']}")
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    sys.exit(main())
