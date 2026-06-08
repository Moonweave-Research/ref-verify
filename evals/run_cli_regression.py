#!/usr/bin/env python3
"""Deterministic CLI regression gate for ref-verify.

Runs the labeled corpus in ``cli_regression.jsonl`` through ``check-file`` and
classifies every row into one of:

- SAFETY pass/fail — invariants that must hold on every commit:
    * ``must_accept`` rows must end ACCEPT (the supported happy path stays green)
    * ``must_not_accept`` rows must NOT end ACCEPT (no fabricated/relational/
      unreachable/over-accepting claim is ever waved through)
  A SAFETY failure exits non-zero and should block release.

- PROGRESS — gated rows whose ``expected_verdict`` is not yet reached because a
  named issue (``gated_on``) has not landed. These are reported, not failed; they
  flip to PASS as their fixes land.

Stdlib only. Usage:
    PYTHONPATH=src python3 evals/run_cli_regression.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

CORPUS = Path(__file__).with_name("cli_regression.jsonl")


def _load_corpus() -> list[dict]:
    rows = []
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _run_cli(rows: list[dict]) -> dict[str, dict]:
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps({"id": row["id"], "doi": row["doi"], "claim": row["claim"]}) + "\n")
        claims_path = handle.name
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "ref_verify.cli", "check-file", claims_path, "--json"],
            capture_output=True,
            text=True,
        )
    finally:
        Path(claims_path).unlink(missing_ok=True)
    if not proc.stdout.strip():
        raise SystemExit(f"check-file produced no JSON. stderr:\n{proc.stderr}")
    payload = json.loads(proc.stdout)
    return {r["id"]: r for r in payload["results"]}


def main() -> int:
    rows = _load_corpus()
    results = _run_cli(rows)

    safety_failures: list[str] = []
    progress_pending: list[str] = []
    print(f"{'id':26}{'verdict':20}{'expected':14}{'class':13}note")
    print("-" * 92)
    for row in rows:
        res = results.get(row["id"], {})
        verdict = res.get("verdict", "MISSING")
        status = res.get("status", "")
        accepted = verdict == "ACCEPT"
        klass, note = "PASS", ""

        if row.get("must_accept") and not accepted:
            klass, note = "SAFETY-FAIL", "must ACCEPT but did not"
            safety_failures.append(row["id"])
        elif row.get("must_not_accept") and accepted:
            klass, note = "SAFETY-FAIL", "must NOT ACCEPT but did"
            safety_failures.append(row["id"])
        elif row.get("must_not_accept"):
            # Control row: the only invariant is "never ACCEPT". The exact non-ACCEPT
            # verdict (UNVERIFIABLE vs PARTIAL) can vary with source availability, so it
            # is not pinned.
            klass = "PASS"
        elif verdict != row["expected_verdict"] and status != row["expected_verdict"]:
            gated = ",".join(row.get("gated_on") or []) or "?"
            klass, note = "PENDING", f"want {row['expected_verdict']} after {gated}"
            progress_pending.append(row["id"])

        shown = verdict if verdict != "WARN" else f"{verdict}/{status}"
        print(f"{row['id']:26}{shown:20}{row['expected_verdict']:14}{klass:13}{note}")

    print("-" * 92)
    print(
        f"SAFETY: {len(rows) - len(safety_failures)}/{len(rows)} ok"
        f"  |  PROGRESS pending: {len(progress_pending)}"
    )
    if safety_failures:
        print("SAFETY FAILURES (release blockers):", ", ".join(safety_failures))
        return 1
    if progress_pending:
        print("Pending (informational, not a failure):", ", ".join(progress_pending))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
