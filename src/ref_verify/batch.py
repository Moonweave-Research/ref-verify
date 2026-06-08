from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

BatchFormat = Literal["jsonl", "csv"]
_VALID_SOURCES = {"auto", "crossref", "openalex", "semantic-scholar", "pubmed"}
_FAILED_ERROR_CODES = {
    "ROW_CHECK_ERROR",
    "SOURCE_API_ERROR",
    "SOURCE_TIMEOUT",
    "SOURCE_RATE_LIMITED",
    "SOURCE_UNSUPPORTED",
}


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
            rows = _parse_jsonl(path)
        else:
            rows = _parse_csv(path)
    except OSError as exc:
        raise BatchInputError(f"Could not read input file: {exc}") from exc
    if not rows:
        raise BatchInputError("Input file does not contain any claim rows")
    return rows


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
        if verdict == "ERROR" or str(result.payload.get("error_code", "")) in _FAILED_ERROR_CODES:
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
            f"partial={summary.partial} unverifiable={summary.unverifiable} "
            f"failed={summary.failed}"
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
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, skipinitialspace=True)
        if reader.fieldnames is None:
            raise BatchInputError("CSV input is missing a header row")
        fieldnames = {_normalize_csv_fieldname(field) for field in reader.fieldnames if field}
        missing = {"doi", "claim"} - fieldnames
        if missing:
            missing_fields = ", ".join(sorted(missing))
            raise BatchInputError(f"CSV header must include doi and claim fields; missing: {missing_fields}")
        for row_number, raw in enumerate(reader, start=2):
            rows.append(
                _row_from_mapping(
                    _normalize_csv_row(raw),
                    line_number=row_number,
                    row_label="line",
                )
            )
    return rows


def _row_from_mapping(raw: dict[str, Any], *, line_number: int, row_label: str) -> ClaimInputRow:
    doi = _required_string(raw, "doi", line_number, row_label)
    claim = _required_string(raw, "claim", line_number, row_label)
    source = _optional_string(raw, "source") or "auto"
    if source not in _VALID_SOURCES:
        raise BatchInputError(f"Invalid field on {row_label} {line_number}: source={source}")
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


def _normalize_csv_fieldname(field: str) -> str:
    return field.lstrip("\ufeff").strip()


def _normalize_csv_row(raw: dict[str, Any]) -> dict[str, Any]:
    return {_normalize_csv_fieldname(key): value for key, value in raw.items() if key is not None}
