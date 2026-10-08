"""Run the labelled reference benchmark against live CrossRef and write a results file.

Not part of CI: it needs the network. See benchmarks/README.md for how to rerun it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ref_verify import __version__  # noqa: E402
from ref_verify.cache import ResponseCache  # noqa: E402
from ref_verify.crossref import CrossrefClient  # noqa: E402
from ref_verify.reference_parse import parse_reference_file  # noqa: E402
from ref_verify.reference_resolve import check_reference  # noqa: E402

DEFAULT_DATASET = REPO_ROOT / "benchmarks" / "references-v1.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "benchmarks" / "results"
_SUFFIXES = {"bib": ".bib", "ris": ".ris", "txt": ".txt"}
# A row the tool could not check (rate limit, timeout) says nothing about its judgement.
_INFRA_ERROR_CODES = {"ROW_CHECK_ERROR"}


def load_dataset(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def outcome(verdict: str) -> str:
    return {"PASS": "pass", "WARN": "warn", "REJECT": "reject"}.get(verdict, "warn")


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float] | None:
    if total == 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return (max(0.0, centre - half), min(1.0, centre + half))


def _rate(successes: int, total: int) -> dict[str, Any]:
    interval = wilson_interval(successes, total)
    return {
        "k": successes,
        "n": total,
        "rate": successes / total if total else None,
        "ci95": list(interval) if interval else None,
    }


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    # Rows that failed for infrastructure reasons are counted, then left out of every rate.
    checked = [r for r in results if r.get("error_code") not in _INFRA_ERROR_CODES]
    by_category: dict[str, list[dict[str, Any]]] = {}
    for result in checked:
        by_category.setdefault(result["category"], []).append(result)

    composition = {
        category: {
            "n": len(rows),
            "pass": sum(r["outcome"] == "pass" for r in rows),
            "warn": sum(r["outcome"] == "warn" for r in rows),
            "reject": sum(r["outcome"] == "reject" for r in rows),
        }
        for category, rows in sorted(by_category.items())
    }

    real = by_category.get("REAL", [])
    fabricated = by_category.get("FABRICATED", [])
    retracted = [r for r in by_category.get("RETRACTED", []) if r.get("crossref_marks_retraction", True)]
    unmarked = [r for r in by_category.get("RETRACTED", []) if not r.get("crossref_marks_retraction", True)]
    unindexed = by_category.get("NOT_IN_CROSSREF", [])

    fabricated_by_type: dict[str, dict[str, Any]] = {}
    for subtype in sorted({r.get("subtype") or "" for r in fabricated}):
        rows = [r for r in fabricated if (r.get("subtype") or "") == subtype]
        fabricated_by_type[subtype] = _rate(sum(r["outcome"] != "pass" for r in rows), len(rows))

    return {
        "infra_errors": len(results) - len(checked),
        "composition": composition,
        "fabricated_flagged": _rate(sum(r["outcome"] != "pass" for r in fabricated), len(fabricated)),
        "fabricated_flagged_by_type": fabricated_by_type,
        "retracted_rejected": _rate(
            sum(r.get("error_code") == "PAPER_RETRACTED" for r in retracted), len(retracted)
        ),
        "retracted_not_marked_by_crossref": len(unmarked),
        "real_clean_pass": _rate(sum(r["outcome"] == "pass" for r in real), len(real)),
        "real_needs_check": _rate(sum(r["outcome"] == "warn" for r in real), len(real)),
        "real_wrongly_rejected": _rate(sum(r["outcome"] == "reject" for r in real), len(real)),
        "unindexed_rejected": _rate(sum(r["outcome"] == "reject" for r in unindexed), len(unindexed)),
        # A PASS is only right if it is the right paper.
        "pass_on_wrong_record": sorted(
            r["id"]
            for r in checked
            if r["outcome"] == "pass"
            and r.get("truth_doi")
            and (r.get("resolved_doi") or r.get("fetched_doi") or "").lower() != r["truth_doi"].lower()
        ),
    }


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _run_once(
    items: list[dict[str, Any]], client: CrossrefClient, workers: int, scratch: Path
) -> tuple[dict[str, dict[str, Any]], float]:
    # One file per input format, as a user would hand check-bib a .bib, .ris, or .txt list.
    rows: dict[str, dict[str, Any]] = {}
    started = time.perf_counter()
    for fmt in ("bib", "ris", "txt"):
        group = [item for item in items if item["input_format"] == fmt]
        if not group:
            continue
        path = scratch / f"references{_SUFFIXES[fmt]}"
        path.write_text("\n\n".join(item["reference"] for item in group) + "\n", encoding="utf-8")
        entries = parse_reference_file(path, fmt)
        if len(entries) != len(group):
            raise SystemExit(f"{fmt}: parsed {len(entries)} entries from {len(group)} items")

        def timed(entry: Any) -> tuple[Any, float]:
            began = time.perf_counter()
            result = check_reference(entry, client)
            return result, time.perf_counter() - began

        with ThreadPoolExecutor(max_workers=workers) as executor:
            for item, (result, seconds) in zip(group, executor.map(timed, entries)):
                rows[item["id"]] = {
                    "verdict": result.verdict,
                    "status": result.status,
                    "error_code": result.error_code,
                    "mismatches": list(result.mismatches),
                    "resolved_doi": result.resolved_doi,
                    "fetched_doi": result.fetched.doi if result.fetched else None,
                    "reason": result.reason,
                    "seconds": round(seconds, 4),
                }
    return rows, time.perf_counter() - started


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--workers", type=int, default=4, help="Same default as check-bib.")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        help="HTTP cache for the run; default is a fresh temporary directory so the first pass is cold.",
    )
    args = parser.parse_args(argv)

    items = load_dataset(args.dataset)
    with tempfile.TemporaryDirectory(prefix="ref-verify-bench-") as tmp:
        scratch = Path(tmp)
        cache_dir = args.cache_dir or scratch / "cache"
        client = CrossrefClient(cache=ResponseCache(cache_dir, ttl_seconds=7 * 86400))
        first, first_seconds = _run_once(items, client, args.workers, scratch)
        cached, cached_seconds = _run_once(items, client, args.workers, scratch)
        # A rate-limited row is re-checked once, alone, after a pause; the first-attempt
        # error stays in the results so the rate limit is still visible.
        failed = [item for item in items if first[item["id"]]["error_code"] in _INFRA_ERROR_CODES]
        retried: dict[str, dict[str, Any]] = {}
        if failed:
            time.sleep(15)
            retried, _ = _run_once(failed, client, 1, scratch)

    results = []
    for item in items:
        row = retried.get(item["id"], first[item["id"]])
        if item["id"] in retried:
            row = {**row, "first_attempt_error": first[item["id"]]["reason"]}
        results.append(
            {
                "id": item["id"],
                "category": item["category"],
                "subtype": item.get("subtype"),
                "input_format": item["input_format"],
                "expected": item["expected"],
                "crossref_marks_retraction": item.get("crossref_marks_retraction"),
                "truth_doi": item.get("truth_doi"),
                **row,
                "outcome": outcome(row["verdict"]),
                "seconds_cached": cached[item["id"]]["seconds"],
                "cached_verdict_differs": cached[item["id"]]["verdict"] != row["verdict"],
            }
        )

    commit = _git("rev-parse", "--short", "HEAD")
    now = datetime.now(timezone.utc)
    payload = {
        "tool": "ref-verify check-bib",
        "tool_version": __version__,
        "commit": commit,
        "dirty": bool(_git("status", "--porcelain", "--untracked-files=no")),
        "date": now.date().isoformat(),
        "generated_at": now.isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "dataset": args.dataset.relative_to(REPO_ROOT).as_posix()
        if args.dataset.is_relative_to(REPO_ROOT)
        else str(args.dataset),
        "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        "workers": args.workers,
        "first_attempt_infra_errors": [item["id"] for item in failed],
        "timing": {
            "first_run_seconds": round(first_seconds, 2),
            "cached_run_seconds": round(cached_seconds, 2),
            "median_seconds_per_reference_first": round(statistics.median(r["seconds"] for r in results), 3),
            "median_seconds_per_reference_cached": round(
                statistics.median(r["seconds_cached"] for r in results), 4
            ),
        },
        "aggregates": aggregate(results),
        "results": results,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    set_name = args.dataset.stem.removeprefix("references-")
    out = args.out_dir / f"{payload['date']}-{commit}-{set_name}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(out)
    print(json.dumps(payload["aggregates"], indent=2))
    print(json.dumps(payload["timing"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
