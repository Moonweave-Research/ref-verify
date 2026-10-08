import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

from ref_verify.cli import main
from ref_verify.crossref import CrossrefClient
from ref_verify.models import PaperRecord
from ref_verify.reference_parse import ReferenceEntry
from ref_verify.reference_resolve import (
    UNMATCHED_REASON,
    check_reference,
    reference_payload,
    render_reference_text,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "references"
PELRINE_DOI = "10.1126/science.287.5454.836"
PELRINE = PaperRecord(
    doi=PELRINE_DOI,
    title="High-Speed Electrically Actuated Elastomers with Strain Greater Than 100%",
    authors=["Pelrine", "Kornbluh", "Pei", "Joseph"],
    year=2000,
    abstract=None,
    source="CrossRef",
)
GELS = PaperRecord(
    doi="10.1039/gels",
    title="Self-healing ionic gels",
    authors=["Müller", "García"],
    year=2019,
    abstract=None,
    source="CrossRef",
)
OTHER = PaperRecord(
    doi="10.1000/other",
    title="An unrelated paper about batteries",
    authors=["Other"],
    year=2019,
    abstract=None,
    source="CrossRef",
)


def _not_found(doi):
    return HTTPError(url=f"https://api.crossref.org/works/{doi}", code=404, msg="Not Found", hdrs=None, fp=None)


class FakeCrossref:
    def __init__(self, works=None, candidates=None, errors=None, search_error=None):
        self.works = works or {}
        self.candidates = candidates or []
        self.errors = errors or {}
        self.search_error = search_error
        self.queries = []

    def fetch_work(self, doi):
        if doi in self.errors:
            raise self.errors[doi]
        if doi not in self.works:
            raise _not_found(doi)
        return self.works[doi]

    def search_bibliographic(self, query, rows=3):
        self.queries.append((query, rows))
        if self.search_error:
            raise self.search_error
        return list(self.candidates)


def _entry(**overrides):
    values = {
        "index": 1,
        "key": "ref",
        "raw": "",
        "title": None,
        "first_author": None,
        "year": None,
        "doi": None,
        "journal": None,
    }
    values.update(overrides)
    return ReferenceEntry(**values)


class DoiReferenceTests(unittest.TestCase):
    def test_matching_metadata_passes(self):
        entry = _entry(doi=PELRINE_DOI, title=PELRINE.title, first_author="Pelrine", year=2000)

        result = check_reference(entry, FakeCrossref(works={PELRINE_DOI: PELRINE}))

        self.assertEqual(result.verdict, "PASS")
        self.assertEqual(result.status, "VERIFIED")
        self.assertIsNone(result.error_code)

    def test_title_mismatch_rejects(self):
        entry = _entry(doi=PELRINE_DOI, title="A different title", first_author="Pelrine", year=2000)

        result = check_reference(entry, FakeCrossref(works={PELRINE_DOI: PELRINE}))

        self.assertEqual(result.verdict, "REJECT")
        self.assertEqual(result.status, "MISMATCH")
        self.assertIn("title", result.mismatches)

    def test_year_only_mismatch_warns(self):
        entry = _entry(doi=PELRINE_DOI, title=PELRINE.title, first_author="Pelrine", year=2001)

        result = check_reference(entry, FakeCrossref(works={PELRINE_DOI: PELRINE}))

        self.assertEqual(result.verdict, "WARN")
        self.assertEqual(result.status, "MISMATCH")
        self.assertEqual(result.mismatches, ["year"])

    def test_dead_doi_rejects(self):
        result = check_reference(_entry(doi="10.9999/dead"), FakeCrossref())

        self.assertEqual(result.verdict, "REJECT")
        self.assertEqual(result.status, "NOT_FOUND")
        self.assertEqual(result.error_code, "DOI_NOT_FOUND")

    def test_retracted_doi_rejects(self):
        retracted = PaperRecord(
            doi="10.1000/retracted",
            title="Retracted paper",
            authors=["Lee"],
            year=2010,
            abstract=None,
            source="CrossRef",
            retraction_doi="10.1000/notice",
        )
        entry = _entry(doi="10.1000/retracted", title="Retracted paper", first_author="Lee", year=2010)

        result = check_reference(entry, FakeCrossref(works={"10.1000/retracted": retracted}))

        self.assertEqual(result.verdict, "REJECT")
        self.assertEqual(result.status, "RETRACTED")
        self.assertEqual(result.error_code, "PAPER_RETRACTED")
        self.assertIn("10.1000/notice", result.reason)

    def test_plain_text_doi_is_confirmed_from_reference_text(self):
        entry = _entry(
            doi=PELRINE_DOI,
            year=2000,
            raw=(
                "Pelrine R, Kornbluh R, Pei Q, Joseph J. High-speed electrically actuated "
                "elastomers with strain greater than 100%. Science. 2000."
            ),
        )

        result = check_reference(entry, FakeCrossref(works={PELRINE_DOI: PELRINE}))

        self.assertEqual(result.verdict, "PASS")
        self.assertEqual(result.status, "VERIFIED")

    def test_plain_text_doi_pointing_at_another_paper_is_not_passed(self):
        entry = _entry(doi=PELRINE_DOI, raw="Smith J. A study of imaginary results. 2021.")

        result = check_reference(entry, FakeCrossref(works={PELRINE_DOI: PELRINE}))

        self.assertEqual(result.verdict, "WARN")
        self.assertEqual(result.status, "UNVERIFIED")
        self.assertIsNone(result.error_code)

    def test_plain_text_doi_with_other_first_author_is_not_passed(self):
        entry = _entry(
            doi=PELRINE_DOI,
            raw=(
                "Smith John, Lee Kim, Pelrine R. High-speed electrically actuated elastomers "
                "with strain greater than 100%. Science. 2000."
            ),
        )

        result = check_reference(entry, FakeCrossref(works={PELRINE_DOI: PELRINE}))

        self.assertEqual(result.verdict, "WARN")
        self.assertEqual(result.status, "UNVERIFIED")

    def test_lookup_failure_is_counted_as_failed(self):
        entry = _entry(doi=PELRINE_DOI)
        client = FakeCrossref(errors={PELRINE_DOI: RuntimeError("upstream failed")})

        result = check_reference(entry, client)

        self.assertEqual(result.verdict, "WARN")
        self.assertEqual(result.error_code, "ROW_CHECK_ERROR")
        self.assertEqual(reference_payload([result])["summary"]["failed"], 1)


class SearchReferenceTests(unittest.TestCase):
    def test_title_match_resolves_and_passes(self):
        entry = _entry(title="Self-healing ionic gels", first_author="Müller", year=2019, journal="Soft Matter")
        client = FakeCrossref(candidates=[OTHER, GELS])

        result = check_reference(entry, client)

        self.assertEqual(result.verdict, "PASS")
        self.assertEqual(result.status, "RESOLVED")
        self.assertEqual(result.error_code, "REFERENCE_RESOLVED")
        self.assertEqual(result.resolved_doi, "10.1039/gels")
        self.assertEqual(client.queries, [("Self-healing ionic gels Müller 2019 Soft Matter", 3)])

    def test_year_off_by_one_warns(self):
        entry = _entry(title="Self-healing ionic gels", first_author="Müller", year=2018)

        result = check_reference(entry, FakeCrossref(candidates=[GELS]))

        self.assertEqual(result.verdict, "WARN")
        self.assertEqual(result.error_code, "REFERENCE_RESOLVED")
        self.assertIn("year", result.mismatches)

    def test_first_author_mismatch_warns(self):
        entry = _entry(title="Self-healing ionic gels", first_author="Smith", year=2019)

        result = check_reference(entry, FakeCrossref(candidates=[GELS]))

        self.assertEqual(result.verdict, "WARN")
        self.assertEqual(result.error_code, "REFERENCE_RESOLVED")
        self.assertIn("first_author", result.mismatches)

    def test_year_off_by_two_is_unmatched(self):
        entry = _entry(title="Self-healing ionic gels", year=2016)

        result = check_reference(entry, FakeCrossref(candidates=[GELS]))

        self.assertEqual(result.error_code, "REFERENCE_UNMATCHED")

    def test_no_matching_candidate_is_unverified_not_rejected(self):
        entry = _entry(title="A study of imaginary results", first_author="Smith", year=2021)

        result = check_reference(entry, FakeCrossref(candidates=[OTHER, GELS]))

        self.assertEqual(result.verdict, "WARN")
        self.assertEqual(result.status, "UNVERIFIED")
        self.assertEqual(result.error_code, "REFERENCE_UNMATCHED")
        self.assertEqual(result.reason, UNMATCHED_REASON)
        self.assertIsNone(result.resolved_doi)

    def test_plain_text_resolves_by_title_token_overlap(self):
        entry = _entry(raw="Müller J, García A. Self-healing ionic gels. Soft Matter (2019).", year=2019)
        client = FakeCrossref(candidates=[OTHER, GELS])

        result = check_reference(entry, client)

        self.assertEqual(result.error_code, "REFERENCE_RESOLVED")
        self.assertEqual(result.resolved_doi, "10.1039/gels")
        self.assertEqual(client.queries[0][0], entry.raw)

    def test_plain_text_with_low_overlap_is_unmatched(self):
        entry = _entry(raw="Smith J. Ionic liquids for imaginary batteries. 2019.", year=2019)

        result = check_reference(entry, FakeCrossref(candidates=[GELS]))

        self.assertEqual(result.error_code, "REFERENCE_UNMATCHED")

    def test_resolved_retracted_candidate_is_rejected(self):
        retracted = PaperRecord(
            doi="10.1039/gels",
            title="Self-healing ionic gels",
            authors=["Müller"],
            year=2019,
            abstract=None,
            source="CrossRef",
            retraction_doi="10.1039/notice",
        )
        entry = _entry(title="Self-healing ionic gels", year=2019)

        result = check_reference(entry, FakeCrossref(candidates=[retracted]))

        self.assertEqual(result.verdict, "REJECT")
        self.assertEqual(result.error_code, "PAPER_RETRACTED")
        self.assertEqual(result.resolved_doi, "10.1039/gels")

    def test_search_failure_is_counted_as_failed(self):
        entry = _entry(title="Self-healing ionic gels")

        result = check_reference(entry, FakeCrossref(search_error=TimeoutError("timed out")))

        self.assertEqual(result.error_code, "ROW_CHECK_ERROR")
        self.assertEqual(result.status, "UNVERIFIED")


class SearchBibliographicTests(unittest.TestCase):
    def test_builds_query_url_and_parses_items(self):
        body = json.dumps(
            {
                "message": {
                    "items": [
                        {"DOI": "10.1039/gels", "title": ["Self-healing ionic gels"], "issued": {"date-parts": [[2019]]}},
                        {"DOI": "10.1000/other", "title": ["Other"]},
                    ]
                }
            }
        )

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return body.encode("utf-8")

        with patch.dict(os.environ, {"REF_VERIFY_MAILTO": "me@example.org"}), patch(
            "ref_verify.http.urlopen", return_value=Response()
        ) as urlopen:
            records = CrossrefClient(timeout=1.0).search_bibliographic("Self-healing ionic gels 2019")

        request = urlopen.call_args.args[0]
        url = urlparse(request.full_url)
        query = parse_qs(url.query)
        self.assertEqual(url.path, "/works")
        self.assertEqual(query["query.bibliographic"], ["Self-healing ionic gels 2019"])
        self.assertEqual(query["rows"], ["3"])
        self.assertEqual(query["mailto"], ["me@example.org"])
        self.assertIn("ref-verify/", request.get_header("User-agent"))
        self.assertEqual([record.doi for record in records], ["10.1039/gels", "10.1000/other"])
        self.assertEqual(records[0].year, 2019)


class OutputTests(unittest.TestCase):
    def setUp(self):
        client = FakeCrossref(works={PELRINE_DOI: PELRINE}, candidates=[GELS])
        self.results = [
            check_reference(_entry(index=1, key="a", doi=PELRINE_DOI, title=PELRINE.title, first_author="Pelrine"), client),
            check_reference(_entry(index=2, key="b", title="Self-healing ionic gels", year=2019), client),
            check_reference(_entry(index=3, key="c", title="Nothing like it", year=2019), client),
            check_reference(_entry(index=4, key="d", doi="10.9999/dead"), client),
        ]

    def test_summary_counts(self):
        summary = reference_payload(self.results)["summary"]

        self.assertEqual(
            summary,
            {"total": 4, "pass": 2, "warn": 1, "reject": 1, "unverified": 1, "failed": 0},
        )

    def test_machine_output_avoids_accusatory_wording(self):
        dumped = json.dumps(reference_payload(self.results)).lower() + render_reference_text(self.results).lower()

        for word in ("fabricat", "fake", "hallucinat"):
            self.assertNotIn(word, dumped)

    def test_text_table_lists_every_reference(self):
        text = render_reference_text(self.results)

        self.assertIn("Summary: total=4 pass=2 warn=1 reject=1 unverified=1 failed=0", text)
        self.assertIn("VERDICT", text)
        self.assertIn("10.1039/gels (resolved)", text)
        for key in ("a", "b", "c", "d"):
            self.assertRegex(text, rf"\n(PASS|WARN|REJECT) +{key} ")


class CheckBibCliTests(unittest.TestCase):
    def _run(self, argv, client):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(argv, client=client, abstract_clients=[])
        return exit_code, output.getvalue()

    def test_bib_fixture_json(self):
        client = FakeCrossref(works={PELRINE_DOI: PELRINE}, candidates=[GELS])

        exit_code, output = self._run(["check-bib", str(FIXTURES / "refs.bib"), "--json"], client)

        payload = json.loads(output)
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["summary"]["total"], 3)
        self.assertEqual(
            [(result["key"], result["verdict"], result["error_code"]) for result in payload["results"]],
            [
                ("pelrine2000", "PASS", None),
                ("mueller2019", "PASS", "REFERENCE_RESOLVED"),
                ("smith2021", "WARN", "REFERENCE_UNMATCHED"),
            ],
        )
        self.assertEqual(payload["results"][1]["resolved_doi"], "10.1039/gels")
        self.assertEqual(payload["results"][0]["reference"]["first_author"], "Pelrine")

    def test_txt_fixture_reports_dead_doi(self):
        client = FakeCrossref(works={PELRINE_DOI: PELRINE}, candidates=[GELS])

        exit_code, output = self._run(["check-bib", str(FIXTURES / "refs.txt"), "--json"], client)

        payload = json.loads(output)
        self.assertEqual(exit_code, 2)
        self.assertEqual(
            [result["error_code"] for result in payload["results"]],
            [None, "DOI_NOT_FOUND", "REFERENCE_RESOLVED"],
        )
        self.assertEqual(payload["results"][0]["verdict"], "PASS")

    def test_ris_fixture_with_format_override_and_text_output(self):
        client = FakeCrossref(works={PELRINE_DOI: PELRINE}, candidates=[GELS])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.dat"
            path.write_text((FIXTURES / "refs.ris").read_text(encoding="utf-8"), encoding="utf-8")

            exit_code, output = self._run(["check-bib", str(path), "--format", "ris"], client)

        self.assertEqual(exit_code, 2)
        self.assertIn("Summary: total=2", output)

    def test_all_pass_exits_zero(self):
        client = FakeCrossref(candidates=[GELS])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "one.bib"
            path.write_text(
                "@article{g, title={Self-healing ionic gels}, author={M{\\\"u}ller, J.}, year={2019}}",
                encoding="utf-8",
            )

            exit_code, output = self._run(["check-bib", str(path), "--json"], client)

        self.assertEqual(exit_code, 0, output)

    def test_input_error_exits_one(self):
        exit_code, output = self._run(["check-bib", str(FIXTURES / "broken.bib"), "--json"], FakeCrossref())

        self.assertEqual(exit_code, 1)
        self.assertIn("Unbalanced braces", json.loads(output)["error"])

    def test_progress_counter_goes_to_terminal_stderr_only(self):
        class TerminalStderr(io.StringIO):
            def isatty(self):
                return True

        client = FakeCrossref(works={PELRINE_DOI: PELRINE}, candidates=[GELS])
        stdout, stderr = io.StringIO(), TerminalStderr()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            main(["check-bib", str(FIXTURES / "refs.bib")], client=client, abstract_clients=[])
        json_stderr = TerminalStderr()
        with redirect_stdout(io.StringIO()), redirect_stderr(json_stderr):
            main(["check-bib", str(FIXTURES / "refs.bib"), "--json"], client=client, abstract_clients=[])

        self.assertIn("Checking references: 3/3", stderr.getvalue())
        self.assertNotIn("Checking references", stdout.getvalue())
        self.assertEqual(json_stderr.getvalue(), "")

    def test_workers_keep_input_order(self):
        client = FakeCrossref(works={PELRINE_DOI: PELRINE}, candidates=[GELS])

        _, output = self._run(["check-bib", str(FIXTURES / "refs.bib"), "--workers", "3", "--json"], client)

        self.assertEqual([result["index"] for result in json.loads(output)["results"]], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
