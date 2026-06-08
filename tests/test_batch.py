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

    def test_csv_without_required_headers_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.csv"
            path.write_text(
                "10.1000/a,This paper reports 95% accuracy.\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(BatchInputError, "CSV header.*doi.*claim"):
                parse_claim_file(path, None)

    def test_empty_input_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            path.write_text("", encoding="utf-8")

            with self.assertRaisesRegex(BatchInputError, "does not contain any claim rows"):
                parse_claim_file(path, None)

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
            BatchRowResult(
                row=ClaimInputRow(1, "a", "10.1000/a", "claim a", "auto", None),
                payload={"verdict": "ACCEPT", "status": "SUPPORTED"},
            ),
            BatchRowResult(
                row=ClaimInputRow(2, "b", "10.1000/b", "claim b", "auto", None),
                payload={"verdict": "WARN", "status": "PARTIAL"},
            ),
            BatchRowResult(
                row=ClaimInputRow(3, "c", "10.1000/c", "claim c", "auto", None),
                payload={"verdict": "WARN", "status": "UNVERIFIABLE"},
            ),
        ]

        summary = summarize_results(results)

        self.assertEqual(
            summary,
            BatchSummary(total=3, accept=1, warn=2, reject=0, partial=1, unverifiable=1, failed=0),
        )
