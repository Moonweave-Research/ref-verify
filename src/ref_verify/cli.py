from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from ref_verify.abstract_lookup import (
    AbstractSourceClient,
    lookup_abstract,
    lookup_selected_abstract,
)
from ref_verify.batch import (
    BatchInputError,
    BatchRowResult,
    batch_payload,
    parse_claim_file,
    render_batch_text,
)
from ref_verify.claim_check import check_claim_support
from ref_verify.crossref import CrossrefClient
from ref_verify.doi_check import normalize_doi, verify_doi_metadata
from ref_verify.models import CitationInput, ClaimSupportResult
from ref_verify.openalex import OpenAlexClient
from ref_verify.pubmed import PubMedClient
from ref_verify.semantic_scholar import SemanticScholarClient


def main(
    argv: Sequence[str] | None = None,
    *,
    client: CrossrefClient | None = None,
    abstract_clients: Sequence[AbstractSourceClient] | None = None,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    lookup_client = client or CrossrefClient()
    fallback_clients = list(abstract_clients) if abstract_clients is not None else _default_abstract_clients()

    try:
        if args.command == "verify-doi":
            return _verify_doi(args, lookup_client)
        if args.command == "check-claim":
            return _check_claim(args, lookup_client, fallback_clients)
        if args.command == "check-file":
            return _check_file(args, lookup_client, fallback_clients)
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
    subparsers = parser.add_subparsers(dest="command")

    verify = subparsers.add_parser("verify-doi", help="Check DOI metadata")
    verify.add_argument("doi")
    verify.add_argument("--title")
    verify.add_argument("--first-author")
    verify.add_argument("--year", type=int)
    verify.add_argument("--json", action="store_true")

    claim = subparsers.add_parser("check-claim", help="Check a claim against a DOI abstract")
    claim.add_argument("doi")
    claim.add_argument("--claim", required=True)
    claim.add_argument(
        "--source",
        choices=("auto", "crossref", "openalex", "semantic-scholar", "pubmed"),
        default="auto",
        help="Select an abstract source for debugging; default tries DOI-bound fallback sources.",
    )
    claim.add_argument("--json", action="store_true")

    check_file = subparsers.add_parser("check-file", help="Check claims from a JSONL or CSV file")
    check_file.add_argument("path")
    check_file.add_argument("--format", choices=("jsonl", "csv"))
    check_file.add_argument("--json", action="store_true")

    return parser


def _verify_doi(args: argparse.Namespace, client: CrossrefClient) -> int:
    lookup_doi = normalize_doi(args.doi)
    fetched = client.fetch_work(lookup_doi)
    provided = CitationInput(
        doi=args.doi,
        title=args.title,
        first_author=args.first_author,
        year=args.year,
    )
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
        rows = parse_claim_file(Path(args.path), args.format)
    except BatchInputError as exc:
        _emit({"error": str(exc)}, as_json=args.json)
        return 1

    results = []
    for row in rows:
        try:
            payload = _run_claim_check(row.doi, row.claim, row.source, client, fallback_clients)
        except Exception as exc:
            payload = _row_error_payload(row.claim, exc)
        results.append(BatchRowResult(row=row, payload=payload))
    payload = batch_payload(results)
    if args.json:
        _emit(payload, as_json=True)
    else:
        print(render_batch_text(results))
    summary = payload["summary"]
    return 0 if summary["total"] == summary["accept"] else 2


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
        fetched = client.fetch_work(lookup_doi)
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
    if result.status == "UNVERIFIABLE":
        return "NO_ABSTRACT"
    if result.status == "PARTIAL":
        if "does not explicitly support" in result.reason:
            return "CLAIM_NOT_EXPLICIT"
        return "CLAIM_AMBIGUOUS"
    return "CLAIM_NOT_EXPLICIT"


def _default_abstract_clients() -> list[AbstractSourceClient]:
    return [OpenAlexClient(), SemanticScholarClient(), PubMedClient()]


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
