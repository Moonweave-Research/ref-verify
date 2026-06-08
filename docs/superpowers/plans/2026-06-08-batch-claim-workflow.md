# Batch Claim Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `ref-verify check-file` so users can verify many DOI-bound numeric claims from JSONL or CSV while preserving the existing conservative single-claim verdict logic.

**Architecture:** Add `src/ref_verify/batch.py` for parsing, validation, result aggregation, and text/JSON-friendly batch models. Keep DOI lookup and claim verification in `src/ref_verify/cli.py` by extracting the current `check-claim` execution into a reusable helper, then call that helper once per row. Add deterministic fixture-backed eval tests so batch workflow improves real use without broadening claim acceptance.

**Tech Stack:** Python standard library only (`argparse`, `csv`, `json`, `dataclasses`, `pathlib`), existing `unittest` tests, existing `CrossrefClient`, abstract source clients, and `ClaimSupportResult`.

---

## File Map

- Create `src/ref_verify/batch.py`: input format detection, JSONL/CSV parsing, row validation, batch result aggregation, text rendering.
- Modify `src/ref_verify/cli.py`: add `check-file` parser, extract reusable claim execution, wire batch command, preserve single-claim behavior.
- Create `tests/test_batch.py`: direct unit tests for parser, validation, summary, and text rendering.
- Modify `tests/test_cli.py`: CLI-level tests using fake clients for `check-file` JSONL/CSV, exit codes, JSON output, and malformed input.
- Create `tests/fixtures/numeric_claim_eval.jsonl`: local abstract/claim eval fixtures across domains.
- Modify `tests/test_numeric_claim.py`: load fixture evals and verify expected statuses without live APIs.
- Modify `README.md`, `README.ko.md`, `CHANGELOG.md`: document batch usage after code lands.

## Task 1: Batch Parser And Models

**Files:**
- Create: `src/ref_verify/batch.py`
- Test: `tests/test_batch.py`

- [ ] **Step 1: Write failing parser tests**

Add `tests/test_batch.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from ref_verify.batch import (
    BatchInputError,
    BatchRowResult,
    BatchSummary,
    ClaimInputRow,
    detect_format,
    parse_claim_file,
    summarize_results,
)


class BatchParserTests(unittest.TestCase):
    def test_detect_format_from_extension(self):
        self.assertEqual(detect_format(Path("claims.jsonl"), None), "jsonl")
        self.assertEqual(detect_format(Path("claims.csv"), None), "csv")
        self.assertEqual(detect_format(Path("claims.txt"), "jsonl"), "jsonl")

    def test_unknown_format_is_rejected(self):
        with self.assertRaisesRegex(BatchInputError, "Unsupported input format"):
            detect_format(Path("claims.txt"), None)

    def test_parse_jsonl_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "id": "c1",
                                "doi": "10.1000/a",
                                "claim": "This paper reports 95% accuracy.",
                                "source": "crossref",
                                "note": "draft",
                            }
                        ),
                        json.dumps(
                            {
                                "doi": "10.1000/b",
                                "claim": "This study included 12 patients.",
                            }
                        ),
                    ]
                ),
                encoding="utf-8",
            )

            rows = parse_claim_file(path, None)

        self.assertEqual(
            rows,
            [
                ClaimInputRow(
                    row_number=1,
                    id="c1",
                    doi="10.1000/a",
                    claim="This paper reports 95% accuracy.",
                    source="crossref",
                    note="draft",
                ),
                ClaimInputRow(
                    row_number=2,
                    id=None,
                    doi="10.1000/b",
                    claim="This study included 12 patients.",
                    source="auto",
                    note=None,
                ),
            ],
        )

    def test_parse_csv_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.csv"
            path.write_text(
                "id,doi,claim,source\n"
                "c1,10.1000/a,This paper reports 95% accuracy.,crossref\n",
                encoding="utf-8",
            )

            rows = parse_claim_file(path, None)

        self.assertEqual(rows[0].id, "c1")
        self.assertEqual(rows[0].doi, "10.1000/a")
        self.assertEqual(rows[0].source, "crossref")

    def test_missing_required_field_is_rejected_with_row_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            path.write_text(json.dumps({"doi": "10.1000/a"}) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(BatchInputError, "line 1.*claim"):
                parse_claim_file(path, None)

    def test_invalid_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "doi": "10.1000/a",
                        "claim": "This paper reports 95% accuracy.",
                        "source": "wikipedia",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(BatchInputError, "line 1.*source"):
                parse_claim_file(path, None)

    def test_summarize_results_counts_verdicts_and_statuses(self):
        results = [
            BatchRowResult(row=ClaimInputRow(1, "a", "10.1000/a", "claim a", "auto", None), payload={"verdict": "ACCEPT", "status": "SUPPORTED"}),
            BatchRowResult(row=ClaimInputRow(2, "b", "10.1000/b", "claim b", "auto", None), payload={"verdict": "WARN", "status": "PARTIAL"}),
            BatchRowResult(row=ClaimInputRow(3, "c", "10.1000/c", "claim c", "auto", None), payload={"verdict": "WARN", "status": "UNVERIFIABLE"}),
        ]

        summary = summarize_results(results)

        self.assertEqual(
            summary,
            BatchSummary(total=3, accept=1, warn=2, reject=0, partial=1, unverifiable=1, failed=0),
        )
```

- [ ] **Step 2: Run tests to confirm failure**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_batch -v
```

Expected: import failure because `ref_verify.batch` does not exist.

- [ ] **Step 3: Implement parser and model helpers**

Create `src/ref_verify/batch.py`:

```python
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

BatchFormat = Literal["jsonl", "csv"]
_VALID_SOURCES = {"auto", "crossref", "semantic-scholar", "pubmed"}


class BatchInputError(ValueError):
    pass


@dataclass(frozen=True)
class ClaimInputRow:
    row_number: int
    id: str | None
    doi: str
    claim: str
    source: str = "auto"
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BatchRowResult:
    row: ClaimInputRow
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        result = {
            "row_number": self.row.row_number,
            "id": self.row.id,
            "doi": self.row.doi,
            "claim": self.row.claim,
        }
        if self.row.note is not None:
            result["note"] = self.row.note
        result.update(self.payload)
        return result


@dataclass(frozen=True)
class BatchSummary:
    total: int
    accept: int
    warn: int
    reject: int
    partial: int
    unverifiable: int
    failed: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def detect_format(path: Path, explicit_format: str | None) -> BatchFormat:
    if explicit_format in ("jsonl", "csv"):
        return explicit_format
    if explicit_format is not None:
        raise BatchInputError(f"Unsupported input format: {explicit_format}")
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return "jsonl"
    if suffix == ".csv":
        return "csv"
    raise BatchInputError("Unsupported input format; use .jsonl, .csv, or --format")


def parse_claim_file(path: Path, explicit_format: str | None) -> list[ClaimInputRow]:
    batch_format = detect_format(path, explicit_format)
    try:
        if batch_format == "jsonl":
            return _parse_jsonl(path)
        return _parse_csv(path)
    except OSError as exc:
        raise BatchInputError(f"Could not read input file: {exc}") from exc


def summarize_results(results: list[BatchRowResult]) -> BatchSummary:
    accept = warn = reject = partial = unverifiable = failed = 0
    for result in results:
        verdict = str(result.payload.get("verdict", ""))
        status = str(result.payload.get("status", ""))
        if verdict == "ACCEPT":
            accept += 1
        if verdict == "WARN":
            warn += 1
        if verdict == "REJECT":
            reject += 1
        if status == "PARTIAL":
            partial += 1
        if status == "UNVERIFIABLE":
            unverifiable += 1
        if verdict == "ERROR":
            failed += 1
    return BatchSummary(
        total=len(results),
        accept=accept,
        warn=warn,
        reject=reject,
        partial=partial,
        unverifiable=unverifiable,
        failed=failed,
    )


def batch_payload(results: list[BatchRowResult]) -> dict[str, Any]:
    return {
        "summary": summarize_results(results).to_dict(),
        "results": [result.to_dict() for result in results],
    }


def render_batch_text(results: list[BatchRowResult]) -> str:
    summary = summarize_results(results)
    lines = [
        (
            f"Summary: total={summary.total} accept={summary.accept} "
            f"warn={summary.warn} reject={summary.reject} "
            f"partial={summary.partial} unverifiable={summary.unverifiable}"
        )
    ]
    for result in results:
        payload = result.payload
        label = str(payload.get("verdict", "WARN"))
        row_id = result.row.id or f"row-{result.row.row_number}"
        lines.extend(
            [
                "",
                f"{label}  {row_id}  {result.row.doi}",
                f"Claim: {result.row.claim}",
                f"Reason: {payload.get('reason', '')}",
            ]
        )
        evidence = payload.get("evidence")
        if evidence:
            lines.append(f"Evidence: {evidence}")
        error_code = payload.get("error_code")
        if error_code:
            lines.append(f"Error code: {error_code}")
    return "\n".join(lines)


def _parse_jsonl(path: Path) -> list[ClaimInputRow]:
    rows: list[ClaimInputRow] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                raw = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise BatchInputError(f"Invalid JSON on line {line_number}: {exc.msg}") from exc
            if not isinstance(raw, dict):
                raise BatchInputError(f"Invalid row on line {line_number}: expected object")
            rows.append(_row_from_mapping(raw, line_number=line_number, row_label="line"))
    return rows


def _parse_csv(path: Path) -> list[ClaimInputRow]:
    rows: list[ClaimInputRow] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise BatchInputError("CSV input is missing a header row")
        for row_number, raw in enumerate(reader, start=2):
            rows.append(_row_from_mapping(raw, line_number=row_number, row_label="line"))
    return rows


def _row_from_mapping(raw: dict[str, Any], *, line_number: int, row_label: str) -> ClaimInputRow:
    doi = _required_string(raw, "doi", line_number, row_label)
    claim = _required_string(raw, "claim", line_number, row_label)
    source = _optional_string(raw, "source") or "auto"
    if source not in _VALID_SOURCES:
        raise BatchInputError(f"Invalid source on {row_label} {line_number}: {source}")
    return ClaimInputRow(
        row_number=line_number,
        id=_optional_string(raw, "id"),
        doi=doi,
        claim=claim,
        source=source,
        note=_optional_string(raw, "note"),
    )


def _required_string(raw: dict[str, Any], field: str, line_number: int, row_label: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise BatchInputError(f"Missing required field on {row_label} {line_number}: {field}")
    return value.strip()


def _optional_string(raw: dict[str, Any], field: str) -> str | None:
    value = raw.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value)
    stripped = value.strip()
    return stripped or None
```

- [ ] **Step 4: Run parser tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_batch -v
```

Expected: all `BatchParserTests` pass.

- [ ] **Step 5: Commit**

```bash
git add src/ref_verify/batch.py tests/test_batch.py
git commit -m "Add batch claim input parsing"
```

## Task 2: Shared Single-Claim Execution

**Files:**
- Modify: `src/ref_verify/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Add a regression test for existing single-claim behavior**

Add this test near existing `check-claim` tests in `tests/test_cli.py`:

```python
    def test_check_claim_still_outputs_same_json_shape_after_helper_extraction(self):
        record = PaperRecord(
            doi="10.1000/helper",
            title="Helper extraction",
            authors=["Lee"],
            year=2024,
            abstract="The model achieved 95% accuracy.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/helper",
                    "--claim",
                    "The model achieved 95% accuracy.",
                    "--json",
                ],
                client=FakeClient(record),
                abstract_clients=[],
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["verdict"], "ACCEPT")
        self.assertEqual(payload["status"], "SUPPORTED")
        self.assertEqual(payload["error_code"], "CLAIM_SUPPORTED")
        self.assertEqual(payload["abstract_source"], "crossref")
        self.assertIn("source_attempts", payload)
```

- [ ] **Step 2: Run the regression test before refactor**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli.CliTests.test_check_claim_still_outputs_same_json_shape_after_helper_extraction -v
```

Expected: PASS before refactor.

- [ ] **Step 3: Extract shared helper in `cli.py`**

Modify `src/ref_verify/cli.py` so `_check_claim` delegates to this helper:

```python
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
```

Then replace `_check_claim` body with:

```python
def _check_claim(
    args: argparse.Namespace,
    client: CrossrefClient,
    fallback_clients: Sequence[AbstractSourceClient],
) -> int:
    payload = _run_claim_check(args.doi, args.claim, args.source, client, fallback_clients)
    _emit(payload, as_json=args.json)
    return 0 if payload.get("verdict") == "ACCEPT" else 2
```

- [ ] **Step 4: Run targeted CLI tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli.CliTests.test_check_claim_still_outputs_same_json_shape_after_helper_extraction tests.test_cli.CliTests.test_check_claim_normalizes_prefixed_doi_before_fetching -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ref_verify/cli.py tests/test_cli.py
git commit -m "Extract reusable claim check execution"
```

## Task 3: JSONL `check-file` CLI

**Files:**
- Modify: `src/ref_verify/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing JSONL CLI tests**

Add these tests to `CliTests` in `tests/test_cli.py`:

```python
    def test_check_file_jsonl_outputs_json_summary(self):
        record = PaperRecord(
            doi="10.1000/batch",
            title="Batch paper",
            authors=["Lee"],
            year=2024,
            abstract="The model achieved 95% accuracy.",
            source="fixture",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "id": "c1",
                        "doi": "10.1000/batch",
                        "claim": "The model achieved 95% accuracy.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    ["check-file", str(path), "--json"],
                    client=FakeClient(record),
                    abstract_clients=[],
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["summary"]["total"], 1)
        self.assertEqual(payload["summary"]["accept"], 1)
        self.assertEqual(payload["results"][0]["id"], "c1")
        self.assertEqual(payload["results"][0]["verdict"], "ACCEPT")

    def test_check_file_jsonl_exits_two_when_any_claim_warns(self):
        record = PaperRecord(
            doi="10.1000/batch-warn",
            title="Batch warning",
            authors=["Lee"],
            year=2024,
            abstract="The model achieved 90% accuracy.",
            source="fixture",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "doi": "10.1000/batch-warn",
                        "claim": "The model achieved 95% accuracy.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    ["check-file", str(path), "--json"],
                    client=FakeClient(record),
                    abstract_clients=[],
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["summary"]["warn"], 1)
        self.assertEqual(payload["results"][0]["status"], "PARTIAL")
```

Also add imports at the top of `tests/test_cli.py`:

```python
import tempfile
from pathlib import Path
```

- [ ] **Step 2: Run tests to confirm failure**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli.CliTests.test_check_file_jsonl_outputs_json_summary tests.test_cli.CliTests.test_check_file_jsonl_exits_two_when_any_claim_warns -v
```

Expected: FAIL because `check-file` is not registered.

- [ ] **Step 3: Wire `check-file` command**

Modify imports in `src/ref_verify/cli.py`:

```python
from pathlib import Path

from ref_verify.batch import (
    BatchInputError,
    BatchRowResult,
    batch_payload,
    parse_claim_file,
    render_batch_text,
)
```

Add parser branch in `_build_parser()`:

```python
    check_file = subparsers.add_parser("check-file", help="Check claims from a JSONL or CSV file")
    check_file.add_argument("path")
    check_file.add_argument("--format", choices=("jsonl", "csv"))
    check_file.add_argument("--json", action="store_true")
```

Add dispatch in `main()`:

```python
        if args.command == "check-file":
            return _check_file(args, lookup_client, fallback_clients)
```

Add `_check_file`:

```python
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

    results = [
        BatchRowResult(
            row=row,
            payload=_run_claim_check(row.doi, row.claim, row.source, client, fallback_clients),
        )
        for row in rows
    ]
    payload = batch_payload(results)
    if args.json:
        _emit(payload, as_json=True)
    else:
        print(render_batch_text(results))
    summary = payload["summary"]
    return 0 if summary["total"] == summary["accept"] else 2
```

- [ ] **Step 4: Run JSONL CLI tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli.CliTests.test_check_file_jsonl_outputs_json_summary tests.test_cli.CliTests.test_check_file_jsonl_exits_two_when_any_claim_warns -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ref_verify/cli.py tests/test_cli.py
git commit -m "Add JSONL batch claim CLI"
```

## Task 4: CSV, Format Override, And Human Output

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `src/ref_verify/batch.py`
- Modify: `src/ref_verify/cli.py`

- [ ] **Step 1: Write CLI tests for CSV, format override, and invalid input**

Add these tests to `CliTests`:

```python
    def test_check_file_csv_outputs_human_summary(self):
        record = PaperRecord(
            doi="10.1000/csv",
            title="CSV paper",
            authors=["Lee"],
            year=2024,
            abstract="The experiment was conducted at 37 °C.",
            source="fixture",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.csv"
            path.write_text(
                "id,doi,claim\n"
                "temp,10.1000/csv,The experiment was conducted at 37 °C.\n",
                encoding="utf-8",
            )
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    ["check-file", str(path)],
                    client=FakeClient(record),
                    abstract_clients=[],
                )

        text = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Summary: total=1 accept=1", text)
        self.assertIn("ACCEPT  temp  10.1000/csv", text)
        self.assertIn("Claim: The experiment was conducted at 37 °C.", text)

    def test_check_file_accepts_format_override(self):
        record = PaperRecord(
            doi="10.1000/override",
            title="Override paper",
            authors=["Lee"],
            year=2024,
            abstract="The study included 12 patients.",
            source="fixture",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.txt"
            path.write_text(
                json.dumps(
                    {
                        "doi": "10.1000/override",
                        "claim": "The study included 12 patients.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    ["check-file", str(path), "--format", "jsonl", "--json"],
                    client=FakeClient(record),
                    abstract_clients=[],
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["summary"]["accept"], 1)

    def test_check_file_invalid_input_returns_json_error(self):
        record = PaperRecord(
            doi="10.1000/error",
            title="Error paper",
            authors=["Lee"],
            year=2024,
            abstract="The model achieved 95% accuracy.",
            source="fixture",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            path.write_text("{bad json}\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    ["check-file", str(path), "--json"],
                    client=FakeClient(record),
                    abstract_clients=[],
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertIn("Invalid JSON on line 1", payload["error"])
```

- [ ] **Step 2: Run tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli.CliTests.test_check_file_csv_outputs_human_summary tests.test_cli.CliTests.test_check_file_accepts_format_override tests.test_cli.CliTests.test_check_file_invalid_input_returns_json_error -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add src/ref_verify/batch.py src/ref_verify/cli.py tests/test_cli.py
git commit -m "Add CSV and human batch output"
```

## Task 5: Fixture-Backed Numeric Eval

**Files:**
- Create: `tests/fixtures/numeric_claim_eval.jsonl`
- Modify: `tests/test_numeric_claim.py`

- [ ] **Step 1: Add eval fixture**

Create `tests/fixtures/numeric_claim_eval.jsonl`:

```jsonl
{"id":"materials-accept","domain":"materials","abstract":"The actuator demonstrated actuation strain above 120% under cyclic loading.","claim":"The actuator demonstrated actuation strain above 100%.","expected_status":"SUPPORTED","why":"Same subject, percent unit, and comparator entailment are explicit."}
{"id":"biomed-accept","domain":"biomedicine","abstract":"The study enrolled 12 patients with confirmed disease.","claim":"The study enrolled 12 patients.","expected_status":"SUPPORTED","why":"Patient count is explicit and subject-bound."}
{"id":"ml-accept","domain":"machine-learning","abstract":"The classifier achieved 95% accuracy on the held-out test set.","claim":"The classifier achieved 95% accuracy.","expected_status":"SUPPORTED","why":"Accuracy percentage is explicit and subject-bound."}
{"id":"chemistry-accept","domain":"chemistry","abstract":"Samples were incubated at 37 °C for 2 h before analysis.","claim":"Samples were incubated at 37 °C.","expected_status":"SUPPORTED","why":"Temperature and subject are explicit in the same clause."}
{"id":"general-wrong-subject","domain":"general-science","abstract":"Group A included 12 patients, while group B included 20 patients.","claim":"Group B included 12 patients.","expected_status":"PARTIAL","why":"The number exists, but it belongs to the wrong subject."}
{"id":"materials-wrong-comparator","domain":"materials","abstract":"The device survived up to 3000 cycles before failure.","claim":"The device survived at least 5000 cycles.","expected_status":"PARTIAL","why":"The unit matches, but comparator and value do not support the claim."}
{"id":"ml-multiple-numbers","domain":"machine-learning","abstract":"Model A achieved 95% accuracy, whereas Model B achieved 88% accuracy.","claim":"Model B achieved 95% accuracy.","expected_status":"PARTIAL","why":"Same sentence contains the number, but subject binding would be wrong."}
```

- [ ] **Step 2: Add fixture test**

Append to `tests/test_numeric_claim.py`:

```python
import json
from pathlib import Path


class NumericClaimEvalFixtureTests(unittest.TestCase):
    def test_numeric_claim_eval_fixture(self):
        fixture = Path(__file__).parent / "fixtures" / "numeric_claim_eval.jsonl"
        with fixture.open("r", encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]

        self.assertGreaterEqual(len(rows), 7)
        self.assertEqual(
            {row["domain"] for row in rows},
            {"materials", "biomedicine", "machine-learning", "chemistry", "general-science"},
        )

        for row in rows:
            with self.subTest(row=row["id"]):
                result = check_numeric_claim_support(row["abstract"], row["claim"])
                self.assertEqual(result.status, row["expected_status"], row["why"])
```

If `tests/test_numeric_claim.py` already imports `json`, `Path`, or `unittest`, merge imports instead of duplicating them.

- [ ] **Step 3: Run numeric fixture tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_numeric_claim.NumericClaimEvalFixtureTests -v
```

Expected: PASS. If a false-accept defense row fails as `SUPPORTED`, stop and fix `numeric_claim.py` before continuing.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/numeric_claim_eval.jsonl tests/test_numeric_claim.py
git commit -m "Add numeric claim eval fixture"
```

## Task 6: Documentation, Full Verification, And Release Prep

**Files:**
- Modify: `README.md`
- Modify: `README.ko.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update English README**

Add a "Batch claim checks" section to `README.md` near the existing CLI usage:

````markdown
### Batch claim checks

Use `check-file` when you have many DOI/claim pairs from a draft, literature note, or AI-agent output.

JSONL:

```bash
ref-verify check-file claims.jsonl
ref-verify check-file claims.jsonl --json
```

CSV:

```bash
ref-verify check-file claims.csv
```

Each row must include `doi` and `claim`. Optional fields are `id`, `source`, and `note`.

Batch mode reuses the same conservative `check-claim` engine. `ACCEPT` means the abstract explicitly supports the numeric claim. `WARN`, `PARTIAL`, `REJECT`, or `UNVERIFIABLE` means the claim should not be treated as verified.
````

- [ ] **Step 2: Update Korean README**

Add the Korean equivalent to `README.ko.md`:

````markdown
### 여러 claim 한 번에 확인하기

초안, 리서치 메모, AI 에이전트 출력처럼 DOI/claim 쌍이 여러 개 있을 때는 `check-file`을 사용합니다.

JSONL:

```bash
ref-verify check-file claims.jsonl
ref-verify check-file claims.jsonl --json
```

CSV:

```bash
ref-verify check-file claims.csv
```

각 행에는 `doi`와 `claim`이 필요합니다. `id`, `source`, `note`는 선택 필드입니다.

배치 모드는 기존의 보수적인 `check-claim` 엔진을 그대로 사용합니다. `ACCEPT`는 abstract가 숫자 claim을 명시적으로 지지한다는 뜻입니다. `WARN`, `PARTIAL`, `REJECT`, `UNVERIFIABLE`은 검증된 claim으로 취급하면 안 됩니다.
````

- [ ] **Step 3: Update changelog**

Add to the top of `CHANGELOG.md`:

```markdown
## Unreleased

- Add `check-file` batch workflow for JSONL and CSV DOI/claim inputs.
- Add fixture-backed numeric claim eval coverage for repeated-use workflows.
```

- [ ] **Step 4: Run full local verification**

Run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m py_compile src/ref_verify/*.py tests/*.py scripts/*.py
python3 -m build --sdist --wheel
python3 -m twine check dist/*
python3 scripts/package_smoke.py --wheel dist/ref_verify-*.whl --expected-version "$(python3 -c 'import pathlib, tomllib; print(tomllib.loads(pathlib.Path("pyproject.toml").read_text())["project"]["version"])')"
git diff --check
```

Expected:

- Unit tests pass.
- `py_compile` exits `0`.
- build creates one source distribution and one wheel.
- `twine check` passes.
- package smoke passes and confirms `SKILL.md` is not packaged.
- `git diff --check` exits `0`.

- [ ] **Step 5: Commit docs**

```bash
git add README.md README.ko.md CHANGELOG.md
git commit -m "Document batch claim workflow"
```

## Final Review Checklist

- [ ] `check-claim` output shape and exit codes are unchanged.
- [ ] `check-file` calls the same claim execution helper as `check-claim`.
- [ ] JSONL and CSV parsing use structured parsers, not manual splitting.
- [ ] Unknown file formats fail closed unless `--format` is provided.
- [ ] Malformed rows return exit `1` and do not get silently skipped.
- [ ] Batch exit `0` only happens when every row is `ACCEPT`.
- [ ] Human output includes row-level reason/evidence, especially for non-accepted rows.
- [ ] JSON output includes summary counts and row results.
- [ ] Eval fixture includes at least five domains and false-accept defense cases.
- [ ] README English and Korean explain batch mode and conservative verdict interpretation.

## Plan Self-Review

- Spec coverage: JSONL, CSV, format override, row validation, exit codes, JSON output, human output, eval fixtures, documentation, and verification are covered by tasks.
- Placeholder scan: no placeholder markers or vague "add tests" steps remain.
- Type consistency: plan uses `ClaimInputRow`, `BatchRowResult`, `BatchSummary`, and `BatchInputError` consistently from Task 1 through CLI integration.
- Residual risk: the fixture rows may expose existing numeric-claim false accepts. If Task 5 fails, fix the numeric engine before documenting the workflow as complete.
