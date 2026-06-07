from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from ref_verify.claim_check import check_claim_support
from ref_verify.crossref import CrossrefClient
from ref_verify.doi_check import verify_doi_metadata
from ref_verify.models import CitationInput


def main(
    argv: Sequence[str] | None = None,
    *,
    client: CrossrefClient | None = None,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    lookup_client = client or CrossrefClient()

    try:
        if args.command == "verify-doi":
            return _verify_doi(args, lookup_client)
        if args.command == "check-claim":
            return _check_claim(args, lookup_client)
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
    claim.add_argument("--json", action="store_true")

    return parser


def _verify_doi(args: argparse.Namespace, client: CrossrefClient) -> int:
    fetched = client.fetch_work(args.doi)
    provided = CitationInput(
        doi=args.doi,
        title=args.title,
        first_author=args.first_author,
        year=args.year,
    )
    result = verify_doi_metadata(provided, fetched)
    _emit(result.to_dict(), as_json=args.json)
    return 2 if result.verdict == "REJECT" else 0


def _check_claim(args: argparse.Namespace, client: CrossrefClient) -> int:
    fetched = client.fetch_work(args.doi)
    result = check_claim_support(fetched, args.claim)
    _emit(result.to_dict(), as_json=args.json)
    return 0 if result.verdict == "ACCEPT" else 2


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
