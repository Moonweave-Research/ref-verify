import io
import json
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

from ref_verify import __version__
from ref_verify.batch import BatchRowResult, ClaimInputRow
from ref_verify.cli import main
from ref_verify.models import PaperRecord
from ref_verify.reference_parse import ReferenceEntry
from ref_verify.reference_resolve import ReferenceResult, reference_payload
from ref_verify.report import (
    FOOTER_NOTE,
    ReportError,
    render_report,
    report_format,
    rows_from_batch_results,
    rows_from_reference_results,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "references"
NOW = datetime(2026, 10, 8, 9, 30, tzinfo=timezone.utc)
RECORD = PaperRecord(
    doi="10.1000/good",
    title="Good paper",
    authors=["Lee"],
    year=2024,
    abstract=None,
    source="CrossRef",
)


def _entry(index, key, **overrides):
    values = {
        "index": index,
        "key": key,
        "raw": f"raw text {index}",
        "title": None,
        "first_author": None,
        "year": None,
        "doi": None,
        "journal": None,
    }
    values.update(overrides)
    return ReferenceEntry(**values)


def _reference_results():
    return [
        ReferenceResult(
            entry=_entry(1, "good", doi="10.1000/good"),
            status="VERIFIED",
            verdict="PASS",
            reason="Provided citation metadata matches the fetched CrossRef record.",
            fetched=RECORD,
        ),
        ReferenceResult(
            entry=_entry(2, "found"),
            status="RESOLVED",
            verdict="WARN",
            reason="Matched CrossRef record 10.1000/found by bibliographic search, but the year differs.",
            error_code="REFERENCE_RESOLVED",
            mismatches=["year"],
            resolved_doi="10.1000/found",
        ),
        ReferenceResult(
            entry=_entry(3, "<script>alert(1)</script>", raw="Evil | <script>alert(2)</script> title"),
            status="UNVERIFIED",
            verdict="WARN",
            reason="No matching CrossRef record was found; verify this reference manually.",
            error_code="REFERENCE_UNMATCHED",
        ),
        ReferenceResult(
            entry=_entry(4, "dead", doi="10.9999/dead"),
            status="NOT_FOUND",
            verdict="REJECT",
            reason="CrossRef has no record for this DOI (HTTP 404).",
            error_code="DOI_NOT_FOUND",
        ),
    ]


def _render(fmt, results=None):
    results = results or _reference_results()
    return render_report(
        fmt,
        command="check-bib",
        source_name="refs.bib",
        summary=reference_payload(results)["summary"],
        rows=rows_from_reference_results(results),
        generated_at=NOW,
    )


class HtmlReportTests(unittest.TestCase):
    def setUp(self):
        self.html = _render("html")

    def test_is_self_contained(self):
        self.assertTrue(self.html.startswith("<!doctype html>"))
        self.assertIn("<style>", self.html)
        self.assertNotIn("<script", self.html.lower())
        self.assertNotIn("<link", self.html.lower())
        self.assertNotIn("http://", self.html)
        for url in re.findall(r"https?://[^\s\"'<>]+", self.html):
            with self.subTest(url=url):
                self.assertTrue(url.startswith("https://doi.org/"), url)

    def test_summary_counts_add_up_to_the_total(self):
        # Counted by the label shown: the JSON summary's warn=2 includes the UNVERIFIED row.
        for name, value in (("total", 4), ("PASS", 1), ("WARN", 1), ("REJECT", 1), ("UNVERIFIED", 1)):
            with self.subTest(name=name):
                self.assertRegex(self.html, rf'<span class="n">{value}</span>\s*<span class="label">{name}</span>')
        self.assertNotIn("not checked", self.html)

    def test_one_table_row_per_result(self):
        self.assertEqual(self.html.count("<tr class="), 4)

    def test_legend_explains_each_verdict_above_the_tables(self):
        legend = self.html.index('<ul class="legend">')

        self.assertLess(legend, self.html.index("<table>"))
        self.assertIn("This does not mean it is wrong; look it up once yourself.", self.html)

    def test_problems_come_before_passed_references(self):
        needs_look = self.html.index("Needs a look (3)")
        passed = self.html.index("Passed (1)")

        self.assertLess(needs_look, passed)
        self.assertLess(self.html.index('<span class="badge reject">REJECT</span></td>'), passed)
        self.assertGreater(self.html.index('<span class="badge pass">PASS</span></td>'), passed)

    def test_all_passing_report_says_nothing_to_fix_and_failed_rows_are_counted(self):
        passing = _render("html", _reference_results()[:1])
        failed = ReferenceResult(
            entry=_entry(5, "later"),
            status="UNVERIFIED",
            verdict="WARN",
            reason="Not checked: CrossRef asked ref-verify to slow down (HTTP 429).",
            error_code="ROW_CHECK_ERROR",
        )

        self.assertIn("Nothing to fix: every reference passed.", passing)
        self.assertRegex(_render("html", [failed]), r'<span class="n">1</span>\s*<span class="label">not checked, rerun</span>')

    def test_verdict_badges_and_doi_links(self):
        self.assertIn('<span class="badge pass">PASS</span>', self.html)
        self.assertIn('<span class="badge warn">WARN</span>', self.html)
        self.assertIn('<span class="badge unverified">UNVERIFIED</span>', self.html)
        self.assertIn('<span class="badge reject">REJECT</span>', self.html)
        self.assertIn('<a href="https://doi.org/10.1000/good">10.1000/good</a>', self.html)
        self.assertIn('<a href="https://doi.org/10.1000/found">10.1000/found</a> (resolved)', self.html)

    def test_escapes_user_derived_text(self):
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", self.html)
        self.assertIn("&lt;script&gt;alert(2)&lt;/script&gt;", self.html)

    def test_footer_and_generation_stamp(self):
        self.assertIn(FOOTER_NOTE, self.html)
        self.assertIn("UNVERIFIED means the tool could not confirm it automatically, not that it is wrong.", FOOTER_NOTE)
        self.assertIn("2026-10-08 09:30 UTC", self.html)
        self.assertIn(f"ref-verify {__version__}", self.html)

    def test_evidence_shows_fetched_record(self):
        self.assertIn("Good paper", self.html)


class MarkdownReportTests(unittest.TestCase):
    def setUp(self):
        self.markdown = _render("md")

    def test_table_rows_and_summary(self):
        table_rows = [line for line in self.markdown.splitlines() if line.startswith("| ")]

        # A header row for each of the two tables plus one row per result.
        self.assertEqual(len(table_rows), 6)
        self.assertIn("total 4", self.markdown)
        self.assertIn("UNVERIFIED 1", self.markdown)
        self.assertLess(self.markdown.index("## Needs a look (3)"), self.markdown.index("## Passed (1)"))
        self.assertIn("- **UNVERIFIED**: Could not be confirmed automatically", self.markdown)
        self.assertIn("[10.1000/good](https://doi.org/10.1000/good)", self.markdown)

    def test_escapes_pipes_and_html(self):
        self.assertNotIn("<script>", self.markdown)
        self.assertIn("Evil \\| &lt;script&gt;", self.markdown)

    def test_footer(self):
        self.assertIn(FOOTER_NOTE, self.markdown)
        self.assertIn(f"ref-verify {__version__}", self.markdown)
        self.assertNotIn("http://", self.markdown)


class BatchRowsTests(unittest.TestCase):
    def test_check_file_rows_carry_claim_and_evidence(self):
        row = ClaimInputRow(row_number=2, id=None, doi="10.1000/good", claim="The model achieved 95% accuracy.")
        payload = {
            "status": "UNVERIFIABLE",
            "verdict": "WARN",
            "reason": "No abstract.",
            "evidence": "",
            "error_code": "NO_ABSTRACT",
        }
        accepted = {
            "status": "SUPPORTED",
            "verdict": "ACCEPT",
            "reason": "Matched.",
            "evidence": "Accuracy reached 95%.",
            "error_code": "CLAIM_SUPPORTED",
        }

        rows = rows_from_batch_results([BatchRowResult(row=row, payload=payload), BatchRowResult(row=row, payload=accepted)])

        self.assertEqual(rows[0].label, "UNVERIFIED")
        self.assertEqual(rows[0].key, "row-2")
        self.assertEqual(rows[0].detail, "The model achieved 95% accuracy.")
        self.assertEqual(rows[1].label, "ACCEPT")
        self.assertEqual(rows[1].tone, "pass")
        self.assertEqual(rows[1].evidence, "Accuracy reached 95%.")


class ReportFormatTests(unittest.TestCase):
    def test_format_follows_extension(self):
        self.assertEqual(report_format(Path("out.html")), "html")
        self.assertEqual(report_format(Path("out.HTM")), "html")
        self.assertEqual(report_format(Path("out.md")), "md")
        with self.assertRaises(ReportError):
            report_format(Path("out.pdf"))


class FakeCrossref:
    def __init__(self):
        self.calls = 0

    def fetch_work(self, doi):
        self.calls += 1
        return PaperRecord(
            doi="10.1126/science.287.5454.836",
            title="High-Speed Electrically Actuated Elastomers with Strain Greater Than 100%",
            authors=["Pelrine"],
            year=2000,
            abstract="Actuated strains up to 117% were demonstrated.",
            source="CrossRef",
        )

    def search_bibliographic(self, query, rows=3, **filters):
        self.calls += 1
        return []


class CliReportTests(unittest.TestCase):
    def test_check_bib_writes_html_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.html"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    ["check-bib", str(FIXTURES / "refs.bib"), "--report", str(report), "--json"],
                    client=FakeCrossref(),
                    abstract_clients=[],
                )
            html = report.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 2)
        self.assertEqual(json.loads(output.getvalue())["summary"]["total"], 3)
        self.assertIn("check-bib", html)
        self.assertIn("refs.bib", html)
        self.assertEqual(html.count("<tr class="), 3)

    def test_check_file_writes_markdown_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            claims = Path(tmp) / "claims.jsonl"
            claims.write_text(
                json.dumps({"id": "c1", "doi": "10.1126/science.287.5454.836", "claim": "strain up to 117%"}) + "\n",
                encoding="utf-8",
            )
            report = Path(tmp) / "report.md"
            with redirect_stdout(io.StringIO()):
                main(
                    ["check-file", str(claims), "--report", str(report)],
                    client=FakeCrossref(),
                    abstract_clients=[],
                )
            markdown = report.read_text(encoding="utf-8")

        self.assertIn("check-file", markdown)
        self.assertIn("| c1", markdown)

    def test_unsupported_report_extension_fails_before_any_lookup(self):
        client = FakeCrossref()
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(output):
            exit_code = main(
                ["check-bib", str(FIXTURES / "refs.bib"), "--report", str(Path(tmp) / "report.pdf"), "--json"],
                client=client,
                abstract_clients=[],
            )

        self.assertEqual(exit_code, 1)
        self.assertIn(".html", json.loads(output.getvalue())["error"])
        self.assertEqual(client.calls, 0)

    def test_missing_report_folder_fails_before_any_lookup(self):
        client = FakeCrossref()
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    ["check-bib", str(FIXTURES / "refs.bib"), "--report", str(Path(tmp) / "missing" / "r.html"), "--json"],
                    client=client,
                    abstract_clients=[],
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("folder for --report does not exist", json.loads(output.getvalue())["error"])
        # A long run is not wasted on a report that could never be written.
        self.assertEqual(client.calls, 0)


if __name__ == "__main__":
    unittest.main()
