"""Run the labelled claim benchmark through `ref-verify check-file` and write a results file.

Not part of CI: it needs the network. See benchmarks/README.md for how to rerun it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from benchmark_references import _git, _rate, load_dataset  # noqa: E402

DEFAULT_DATASET = REPO_ROOT / "benchmarks" / "claims-v1.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "benchmarks" / "results"
# A row the tool could not check says nothing about its judgement (same set check-file counts as failed).
_INFRA_ERROR_CODES = {"ROW_CHECK_ERROR", "SOURCE_API_ERROR", "SOURCE_TIMEOUT", "SOURCE_RATE_LIMITED", "SOURCE_UNSUPPORTED"}
_RUN_CLI = "import sys; from ref_verify.cli import main; sys.exit(main())"


def _check_file(items: list[dict[str, Any]], workers: int, scratch: Path) -> list[dict[str, Any]]:
    path = scratch / "claims.jsonl"
    path.write_text(
        "".join(json.dumps({"id": i["id"], "doi": i["doi"], "claim": i["claim"]}) + "\n" for i in items),
        encoding="utf-8",
    )
    # A fresh cache directory, so every run fetches the abstracts itself.
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src"), "REF_VERIFY_CACHE_DIR": str(scratch / "cache")}
    env.pop("REF_VERIFY_NO_CACHE", None)
    completed = subprocess.run(
        [sys.executable, "-c", _RUN_CLI, "check-file", str(path), "--json", "--workers", str(workers)],
        capture_output=True,
        text=True,
        env=env,
    )
    if completed.returncode not in (0, 2):
        raise SystemExit(f"check-file failed ({completed.returncode}): {completed.stderr or completed.stdout}")
    return json.loads(completed.stdout)["results"]


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    checked = [r for r in results if r.get("error_code") not in _INFRA_ERROR_CODES]
    supported = [r for r in checked if r["label"] == "SUPPORTED"]
    unsupported = [r for r in checked if r["label"] == "NOT_SUPPORTED"]
    accepted = [r for r in checked if r["verdict"] == "ACCEPT"]

    false_accept_by_type: dict[str, dict[str, Any]] = {}
    for error_type in sorted({r["error_type"] for r in unsupported}):
        rows = [r for r in unsupported if r["error_type"] == error_type]
        false_accept_by_type[error_type] = _rate(sum(r["verdict"] == "ACCEPT" for r in rows), len(rows))

    verdicts: dict[str, dict[str, int]] = {}
    for label, rows in (("SUPPORTED", supported), ("NOT_SUPPORTED", unsupported)):
        counts: dict[str, int] = {}
        for row in rows:
            key = f"{row['verdict']}/{row['status']}"
            counts[key] = counts.get(key, 0) + 1
        verdicts[label] = dict(sorted(counts.items()))

    return {
        "infra_errors": len(results) - len(checked),
        "abstract_changed": sorted(r["id"] for r in results if r["abstract_changed"]),
        # The verdict users trust: how often a claim the abstract does not support is accepted.
        "false_accept_rate": _rate(sum(r["verdict"] == "ACCEPT" for r in unsupported), len(unsupported)),
        "false_accept_by_type": false_accept_by_type,
        "accept_precision": _rate(sum(r["label"] == "SUPPORTED" for r in accepted), len(accepted)),
        "accept_recall": _rate(sum(r["verdict"] == "ACCEPT" for r in supported), len(supported)),
        "unsupported_rejected": _rate(sum(r["verdict"] == "REJECT" for r in unsupported), len(unsupported)),
        "verdicts": verdicts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--workers", type=int, default=4, help="Same default as check-file.")
    args = parser.parse_args(argv)

    items = load_dataset(args.dataset)
    with tempfile.TemporaryDirectory(prefix="ref-verify-claims-") as tmp:
        rows = _check_file(items, args.workers, Path(tmp))

    results = []
    for item, row in zip(items, rows):
        if row.get("id") != item["id"]:
            raise SystemExit(f"row order mismatch: {row.get('id')} != {item['id']}")
        abstract = (row.get("paper") or {}).get("abstract") or ""
        results.append(
            {
                "id": item["id"],
                "doi": item["doi"],
                "label": item["label"],
                "error_type": item.get("error_type"),
                "verdict": row.get("verdict"),
                "status": row.get("status"),
                "error_code": row.get("error_code"),
                "abstract_source": row.get("abstract_source"),
                # The label was read off one abstract text; a different text voids the comparison.
                "abstract_changed": hashlib.sha256(abstract.encode("utf-8")).hexdigest() != item["abstract_sha256"],
                "reason": row.get("reason"),
                "evidence": row.get("evidence"),
            }
        )

    commit = _git("rev-parse", "--short", "HEAD")
    now = datetime.now(timezone.utc)
    payload = {
        "tool": "ref-verify check-file",
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
        "aggregates": aggregate(results),
        "results": results,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"{payload['date']}-{commit}-{args.dataset.stem}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(out)
    print(json.dumps(payload["aggregates"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
