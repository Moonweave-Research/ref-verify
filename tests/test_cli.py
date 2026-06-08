import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from ref_verify.abstract_lookup import AbstractSourceError
from ref_verify.cli import _default_abstract_clients, main
from ref_verify.crossref import parse_crossref_work
from ref_verify.models import PaperRecord


class FakeClient:
    def __init__(self, record):
        self.record = record

    def fetch_work(self, doi):
        if doi != self.record.doi:
            raise AssertionError("unexpected doi")
        return self.record


class MismatchedDoiClient:
    def __init__(self, requested_doi, record):
        self.requested_doi = requested_doi
        self.record = record

    def fetch_work(self, doi):
        if doi != self.requested_doi:
            raise AssertionError("unexpected doi")
        return self.record


class FailingClient:
    def __init__(self, error):
        self.error = error

    def fetch_work(self, doi):
        raise self.error


class MappingClient:
    def __init__(self, records, errors=None):
        self.records = records
        self.errors = errors or {}

    def fetch_work(self, doi):
        if doi in self.errors:
            raise self.errors[doi]
        return self.records[doi]


class FakeAbstractSourceClient:
    def __init__(self, source_name, record=None, status="FOUND", reason=None, raises=None):
        self.source_name = source_name
        self.record = record
        self.status = status
        self.reason = reason
        self.raises = raises
        self.calls = []

    def fetch_record(self, doi):
        self.calls.append(doi)
        if self.raises:
            raise self.raises
        return self.record


class CliTests(unittest.TestCase):
    def test_verify_doi_outputs_machine_readable_json(self):
        record = PaperRecord(
            doi="10.1000/example",
            title="Dielectric elastomer actuators",
            authors=["Pelrine", "Kornbluh"],
            year=2000,
            abstract=None,
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "verify-doi",
                    "10.1000/example",
                    "--title",
                    "Dielectric elastomer actuators",
                    "--first-author",
                    "Pelrine",
                    "--year",
                    "2000",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["verdict"], "PASS")
        self.assertEqual(payload["fetched"]["title"], "Dielectric elastomer actuators")

    def test_verify_doi_normalizes_url_before_fetching(self):
        record = PaperRecord(
            doi="10.1000/example",
            title="Dielectric elastomer actuators",
            authors=["Pelrine", "Kornbluh"],
            year=2000,
            abstract=None,
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "verify-doi",
                    "https://doi.org/10.1000/example",
                    "--title",
                    "Dielectric elastomer actuators",
                    "--first-author",
                    "Pelrine",
                    "--year",
                    "2000",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["verdict"], "PASS")

    def test_verify_doi_normalizes_scheme_less_url_before_fetching(self):
        record = PaperRecord(
            doi="10.1000/example",
            title="Dielectric elastomer actuators",
            authors=["Pelrine", "Kornbluh"],
            year=2000,
            abstract=None,
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "verify-doi",
                    "doi.org/10.1000/example",
                    "--title",
                    "Dielectric elastomer actuators",
                    "--first-author",
                    "Pelrine",
                    "--year",
                    "2000",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["verdict"], "PASS")

    def test_verify_doi_exits_nonzero_when_no_metadata_is_provided(self):
        record = PaperRecord(
            doi="10.1000/example",
            title="Completely Different Paper",
            authors=["Wrong"],
            year=1999,
            abstract=None,
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "verify-doi",
                    "10.1000/example",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["verdict"], "WARN")
        self.assertIn("metadata", payload["mismatches"])

    def test_verify_doi_exits_nonzero_when_requested_year_is_unavailable(self):
        record = PaperRecord(
            doi="10.1000/missing-year",
            title="Dielectric elastomer actuators",
            authors=["Pelrine", "Kornbluh"],
            year=None,
            abstract=None,
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "verify-doi",
                    "10.1000/missing-year",
                    "--year",
                    "2020",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["verdict"], "WARN")
        self.assertIn("year", payload["mismatches"])

    def test_verify_doi_exits_nonzero_when_only_year_is_provided(self):
        record = PaperRecord(
            doi="10.1000/year-only",
            title="Completely Different Paper",
            authors=["Wrong"],
            year=2000,
            abstract=None,
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "verify-doi",
                    "10.1000/year-only",
                    "--year",
                    "2000",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["verdict"], "WARN")
        self.assertIn("metadata", payload["mismatches"])

    def test_verify_doi_exits_nonzero_when_crossref_only_has_created_year(self):
        record = parse_crossref_work(
            {
                "DOI": "10.1000/created-only",
                "title": ["Created timestamp is not publication"],
                "author": [{"family": "Lee", "given": "Jane"}],
                "created": {"date-parts": [[2020, 1, 1]]},
            }
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "verify-doi",
                    "10.1000/created-only",
                    "--year",
                    "2020",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["verdict"], "WARN")
        self.assertIn("year", payload["mismatches"])

    def test_check_claim_outputs_claim_status(self):
        record = PaperRecord(
            doi="10.1000/example",
            title="Dielectric elastomer actuators",
            authors=["Pelrine", "Kornbluh"],
            year=2000,
            abstract="Actuated strains up to 117% were demonstrated.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/example",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "SUPPORTED")
        self.assertEqual(payload["verdict"], "ACCEPT")
        self.assertEqual(payload["abstract_source"], "crossref")
        self.assertEqual(payload["error_code"], "CLAIM_SUPPORTED")

    def test_check_claim_does_not_query_fallback_when_crossref_has_abstract(self):
        record = PaperRecord(
            doi="10.1000/example",
            title="Dielectric elastomer actuators",
            authors=["Pelrine", "Kornbluh"],
            year=2000,
            abstract="Actuated strains up to 117% were demonstrated.",
            source="fixture",
        )
        fallback = FakeAbstractSourceClient(
            "semantic_scholar",
            record=PaperRecord(
                doi="10.1000/example",
                title="Fallback paper",
                authors=["Lee"],
                year=2021,
                abstract="Actuated strain remained below 20%.",
                source="semantic_scholar",
            ),
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/example",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
                abstract_clients=[fallback],
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(fallback.calls, [])
        self.assertEqual(payload["abstract_source"], "crossref")
        self.assertEqual(payload["source_attempts"][0]["status"], "FOUND")

    def test_check_claim_source_option_forces_requested_fallback_source(self):
        crossref_record = PaperRecord(
            doi="10.1000/example",
            title="Dielectric elastomer actuators",
            authors=["Pelrine", "Kornbluh"],
            year=2000,
            abstract="Actuated strain remained below 20%.",
            source="CrossRef",
        )
        semantic_record = PaperRecord(
            doi="10.1000/example",
            title="Dielectric elastomer actuators",
            authors=["Pelrine", "Kornbluh"],
            year=2000,
            abstract="Actuated strains up to 117% were demonstrated.",
            source="Semantic Scholar",
        )
        semantic = FakeAbstractSourceClient("semantic_scholar", record=semantic_record)
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/example",
                    "--claim",
                    "actuation strain above 100%",
                    "--source",
                    "semantic-scholar",
                    "--json",
                ],
                client=FakeClient(crossref_record),
                abstract_clients=[semantic],
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["abstract_source"], "semantic_scholar")
        self.assertEqual(payload["source_attempts"][0]["source"], "semantic_scholar")
        self.assertEqual(payload["source_attempts"][0]["status"], "FOUND")

    def test_check_claim_openalex_source_option(self):
        crossref_record = PaperRecord(
            doi="10.1000/openalex",
            title="CrossRef no abstract",
            authors=["Lee"],
            year=2024,
            abstract=None,
            source="fixture",
        )
        openalex_record = PaperRecord(
            doi="10.1000/openalex",
            title="OpenAlex paper",
            authors=["Lee"],
            year=2024,
            abstract="The actuator survived 5000 cycles.",
            source="fixture",
        )
        openalex = FakeAbstractSourceClient("openalex", record=openalex_record)
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/openalex",
                    "--claim",
                    "The actuator survived 5000 cycles.",
                    "--source",
                    "openalex",
                    "--json",
                ],
                client=FakeClient(crossref_record),
                abstract_clients=[openalex],
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["abstract_source"], "openalex")
        self.assertEqual(payload["source_attempts"][0]["source"], "openalex")
        self.assertEqual(payload["error_code"], "CLAIM_SUPPORTED")

    def test_check_claim_uses_semantic_scholar_fallback_when_crossref_has_no_abstract(self):
        crossref_record = PaperRecord(
            doi="10.1000/noabstract",
            title="Smart material paper",
            authors=["Kim"],
            year=2021,
            abstract=None,
            source="CrossRef",
        )
        semantic_record = PaperRecord(
            doi="10.1000/noabstract",
            title="Smart material paper",
            authors=["Kim"],
            year=2021,
            abstract="Actuated strains up to 117% were demonstrated.",
            source="Semantic Scholar",
        )
        semantic = FakeAbstractSourceClient("semantic_scholar", record=semantic_record)
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/noabstract",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(crossref_record),
                abstract_clients=[semantic],
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["paper"]["source"], "Semantic Scholar")
        self.assertEqual(payload["abstract_source"], "semantic_scholar")
        self.assertEqual(payload["source_attempts"][0]["status"], "NO_ABSTRACT")
        self.assertEqual(payload["source_attempts"][1]["status"], "FOUND")

    def test_default_fallback_order_tries_openalex_before_semantic_scholar(self):
        clients = _default_abstract_clients()

        self.assertEqual(
            [client.source_name for client in clients],
            ["openalex", "semantic_scholar", "pubmed"],
        )

    def test_check_claim_ignores_mismatched_fallback_and_uses_next_source(self):
        crossref_record = PaperRecord(
            doi="10.1000/noabstract",
            title="Smart material paper",
            authors=["Kim"],
            year=2021,
            abstract=None,
            source="CrossRef",
        )
        mismatched_record = PaperRecord(
            doi="10.1000/other",
            title="Other paper",
            authors=["Lee"],
            year=2022,
            abstract="Actuated strains up to 117% were demonstrated.",
            source="Semantic Scholar",
        )
        pubmed_record = PaperRecord(
            doi="10.1000/noabstract",
            title="Smart material paper",
            authors=["Kim"],
            year=2021,
            abstract="The actuator survived 5000 cycles.",
            source="PubMed",
        )
        semantic = FakeAbstractSourceClient("semantic_scholar", record=mismatched_record)
        pubmed = FakeAbstractSourceClient("pubmed", record=pubmed_record)
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/noabstract",
                    "--claim",
                    "actuator survived at least 4000 cycles",
                    "--json",
                ],
                client=FakeClient(crossref_record),
                abstract_clients=[semantic, pubmed],
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["abstract_source"], "pubmed")
        self.assertEqual(payload["source_attempts"][1]["status"], "DOI_MISMATCH")
        self.assertEqual(payload["source_attempts"][2]["status"], "FOUND")

    def test_check_claim_continues_after_fallback_api_error(self):
        crossref_record = PaperRecord(
            doi="10.1000/noabstract",
            title="Smart material paper",
            authors=["Kim"],
            year=2021,
            abstract=None,
            source="CrossRef",
        )
        pubmed_record = PaperRecord(
            doi="10.1000/noabstract",
            title="Smart material paper",
            authors=["Kim"],
            year=2021,
            abstract="Samples were maintained at 37 °C.",
            source="PubMed",
        )
        semantic = FakeAbstractSourceClient(
            "semantic_scholar",
            raises=RuntimeError("upstream unavailable"),
        )
        pubmed = FakeAbstractSourceClient("pubmed", record=pubmed_record)
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/noabstract",
                    "--claim",
                    "samples were maintained at 37 °C",
                    "--json",
                ],
                client=FakeClient(crossref_record),
                abstract_clients=[semantic, pubmed],
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["abstract_source"], "pubmed")
        self.assertEqual(payload["source_attempts"][1]["status"], "API_ERROR")
        self.assertEqual(payload["source_attempts"][2]["status"], "FOUND")

    def test_check_claim_reports_source_api_error_when_fallbacks_all_fail_by_api(self):
        crossref_record = PaperRecord(
            doi="10.1000/noabstract",
            title="Smart material paper",
            authors=["Kim"],
            year=2021,
            abstract=None,
            source="CrossRef",
        )
        semantic = FakeAbstractSourceClient(
            "semantic_scholar",
            raises=RuntimeError("semantic scholar unavailable"),
        )
        pubmed = FakeAbstractSourceClient(
            "pubmed",
            raises=RuntimeError("pubmed unavailable"),
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/noabstract",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(crossref_record),
                abstract_clients=[semantic, pubmed],
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "UNVERIFIABLE")
        self.assertEqual(payload["error_code"], "SOURCE_API_ERROR")
        self.assertEqual([attempt["status"] for attempt in payload["source_attempts"]], [
            "NO_ABSTRACT",
            "API_ERROR",
            "API_ERROR",
        ])

    def test_check_claim_explicit_source_bypasses_crossref_failure(self):
        semantic_record = PaperRecord(
            doi="10.1000/example",
            title="Dielectric elastomer actuators",
            authors=["Pelrine", "Kornbluh"],
            year=2000,
            abstract="Actuated strains up to 117% were demonstrated.",
            source="Semantic Scholar",
        )
        semantic = FakeAbstractSourceClient("semantic_scholar", record=semantic_record)
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/example",
                    "--claim",
                    "actuation strain above 100%",
                    "--source",
                    "semantic-scholar",
                    "--json",
                ],
                client=FailingClient(RuntimeError("crossref unavailable")),
                abstract_clients=[semantic],
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["abstract_source"], "semantic_scholar")
        self.assertEqual(payload["source_attempts"][0]["source"], "semantic_scholar")
        self.assertEqual(payload["source_attempts"][0]["status"], "FOUND")

    def test_check_claim_reports_no_abstract_after_all_sources_fail(self):
        crossref_record = PaperRecord(
            doi="10.1000/noabstract",
            title="Smart material paper",
            authors=["Kim"],
            year=2021,
            abstract=None,
            source="CrossRef",
        )
        semantic = FakeAbstractSourceClient("semantic_scholar", record=None)
        pubmed = FakeAbstractSourceClient("pubmed", record=None)
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/noabstract",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(crossref_record),
                abstract_clients=[semantic, pubmed],
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "UNVERIFIABLE")
        self.assertEqual(payload["verdict"], "WARN")
        self.assertEqual(payload["error_code"], "NO_ABSTRACT")
        self.assertIsNone(payload["abstract_source"])
        self.assertEqual([attempt["status"] for attempt in payload["source_attempts"]], [
            "NO_ABSTRACT",
            "NO_ABSTRACT",
            "NO_ABSTRACT",
        ])

    def test_check_claim_reports_source_rate_limited(self):
        crossref_record = PaperRecord(
            doi="10.1000/rate-limited",
            title="No abstract",
            authors=["Lee"],
            year=2024,
            abstract=None,
            source="fixture",
        )
        semantic = FakeAbstractSourceClient(
            "semantic_scholar",
            raises=AbstractSourceError("RATE_LIMITED", "Semantic Scholar rate limit exceeded."),
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/rate-limited",
                    "--claim",
                    "The actuator survived 5000 cycles.",
                    "--json",
                ],
                client=FakeClient(crossref_record),
                abstract_clients=[semantic],
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["error_code"], "SOURCE_RATE_LIMITED")
        self.assertEqual(payload["source_attempts"][1]["status"], "RATE_LIMITED")

    def test_check_claim_does_not_promote_fallback_doi_mismatch_to_final_error(self):
        crossref_record = PaperRecord(
            doi="10.1000/noabstract",
            title="Smart material paper",
            authors=["Kim"],
            year=2021,
            abstract=None,
            source="CrossRef",
        )
        mismatched_record = PaperRecord(
            doi="10.1000/other",
            title="Other paper",
            authors=["Lee"],
            year=2022,
            abstract="Actuated strains up to 117% were demonstrated.",
            source="Semantic Scholar",
        )
        semantic = FakeAbstractSourceClient("semantic_scholar", record=mismatched_record)
        pubmed = FakeAbstractSourceClient("pubmed", record=None)
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/noabstract",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(crossref_record),
                abstract_clients=[semantic, pubmed],
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["error_code"], "NO_ABSTRACT")
        self.assertEqual(payload["source_attempts"][1]["status"], "DOI_MISMATCH")

    def test_check_claim_reports_source_timeout_when_fallbacks_time_out(self):
        crossref_record = PaperRecord(
            doi="10.1000/noabstract",
            title="Smart material paper",
            authors=["Kim"],
            year=2021,
            abstract=None,
            source="CrossRef",
        )
        semantic = FakeAbstractSourceClient(
            "semantic_scholar",
            raises=TimeoutError("semantic scholar timed out"),
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/noabstract",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(crossref_record),
                abstract_clients=[semantic],
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["error_code"], "SOURCE_TIMEOUT")
        self.assertEqual(payload["source_attempts"][1]["status"], "TIMEOUT")

    def test_check_claim_preserves_structured_source_error_status(self):
        crossref_record = PaperRecord(
            doi="10.1000/noabstract",
            title="Smart material paper",
            authors=["Kim"],
            year=2021,
            abstract=None,
            source="CrossRef",
        )
        semantic = FakeAbstractSourceClient(
            "semantic_scholar",
            raises=AbstractSourceError("NOT_FOUND", "Semantic Scholar had no paper for the DOI."),
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/noabstract",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(crossref_record),
                abstract_clients=[semantic],
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["error_code"], "NO_ABSTRACT")
        self.assertEqual(payload["source_attempts"][1]["status"], "NOT_FOUND")

    def test_check_claim_distinguishes_not_explicit_from_ambiguous_claim_warning(self):
        not_explicit = PaperRecord(
            doi="10.1000/not-explicit",
            title="Unrelated paper",
            authors=["Kim"],
            year=2021,
            abstract="The study discusses polymer synthesis.",
            source="CrossRef",
        )
        ambiguous = PaperRecord(
            doi="10.1000/ambiguous",
            title="Prestrain paper",
            authors=["Kim"],
            year=2021,
            abstract="The film was subjected to 500% pre-strain before testing.",
            source="CrossRef",
        )

        not_explicit_output = io.StringIO()
        with redirect_stdout(not_explicit_output):
            not_explicit_exit = main(
                [
                    "check-claim",
                    "10.1000/not-explicit",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(not_explicit),
            )

        ambiguous_output = io.StringIO()
        with redirect_stdout(ambiguous_output):
            ambiguous_exit = main(
                [
                    "check-claim",
                    "10.1000/ambiguous",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(ambiguous),
            )

        not_explicit_payload = json.loads(not_explicit_output.getvalue())
        ambiguous_payload = json.loads(ambiguous_output.getvalue())
        self.assertEqual(not_explicit_exit, 2)
        self.assertEqual(ambiguous_exit, 2)
        self.assertEqual(not_explicit_payload["error_code"], "CLAIM_NOT_EXPLICIT")
        self.assertEqual(ambiguous_payload["error_code"], "CLAIM_AMBIGUOUS")

    def test_check_claim_normalizes_prefixed_doi_before_fetching(self):
        record = PaperRecord(
            doi="10.1000/example",
            title="Dielectric elastomer actuators",
            authors=["Pelrine", "Kornbluh"],
            year=2000,
            abstract="Actuated strains up to 117% were demonstrated.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "doi:10.1000/example",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "SUPPORTED")
        self.assertEqual(payload["verdict"], "ACCEPT")

    def test_check_claim_normalizes_scheme_less_dx_url_before_fetching(self):
        record = PaperRecord(
            doi="10.1000/example",
            title="Dielectric elastomer actuators",
            authors=["Pelrine", "Kornbluh"],
            year=2000,
            abstract="Actuated strains up to 117% were demonstrated.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "dx.doi.org/10.1000/example",
                    "--claim",
                    "actuation strain > 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "SUPPORTED")
        self.assertEqual(payload["verdict"], "ACCEPT")

    def test_check_claim_accepts_natural_language_percent_claim(self):
        record = PaperRecord(
            doi="10.1000/example",
            title="Dielectric elastomer actuators",
            authors=["Pelrine", "Kornbluh"],
            year=2000,
            abstract="Actuated strains up to 117% were demonstrated.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/example",
                    "--claim",
                    "actuation strain over 100 per cent",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "SUPPORTED")
        self.assertEqual(payload["verdict"], "ACCEPT")

    def test_check_claim_accepts_first_person_result_frame(self):
        record = PaperRecord(
            doi="10.1000/direct-result",
            title="Direct result actuator",
            authors=["Lee"],
            year=2020,
            abstract="We found actuated strains above 120%.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/direct-result",
                    "--claim",
                    "actuated strains above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "SUPPORTED")
        self.assertEqual(payload["verdict"], "ACCEPT")

    def test_check_claim_accepts_result_modal_frame(self):
        record = PaperRecord(
            doi="10.1000/modal-result",
            title="Modal result actuator",
            authors=["Lee"],
            year=2020,
            abstract="Silicone elastomers can achieve actuation strains of 117%.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/modal-result",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "SUPPORTED")
        self.assertEqual(payload["verdict"], "ACCEPT")

    def test_check_claim_exits_nonzero_when_fetched_doi_differs(self):
        record = PaperRecord(
            doi="10.1000/other",
            title="Different paper",
            authors=["Lee"],
            year=2020,
            abstract="Actuated strains up to 117% were demonstrated.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/requested",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=MismatchedDoiClient("10.1000/requested", record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "UNVERIFIABLE")
        self.assertEqual(payload["verdict"], "WARN")
        self.assertEqual(payload["paper"]["doi"], "10.1000/other")

    def test_check_claim_exits_nonzero_when_claim_is_partial(self):
        record = PaperRecord(
            doi="10.1000/example",
            title="Dielectric elastomer actuators",
            authors=["Pelrine", "Kornbluh"],
            year=2000,
            abstract="Actuated strain remained below 50% throughout testing.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/example",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_cross_sentence_contradiction(self):
        record = PaperRecord(
            doi="10.1000/cross-sentence-conflict",
            title="Cross-sentence strain conflict",
            authors=["Lee"],
            year=2020,
            abstract=(
                "Actuation strain remained below 50%. "
                "Actuated strains up to 60% were demonstrated later."
            ),
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/cross-sentence-conflict",
                    "--claim",
                    "actuation strain below 50%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_negated_percentage_evidence(self):
        record = PaperRecord(
            doi="10.1000/negated",
            title="Negated strain actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuation strain did not exceed 117% in any sample.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/negated",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_no_sample_negation(self):
        record = PaperRecord(
            doi="10.1000/no-sample",
            title="No sample actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuation strain exceeded 117% in no sample.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/no-sample",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_none_negation(self):
        record = PaperRecord(
            doi="10.1000/none-showed",
            title="None showed actuator",
            authors=["Lee"],
            year=2020,
            abstract="None showed actuation strain above 100%.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/none-showed",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_scoped_percentage(self):
        record = PaperRecord(
            doi="10.1000/scoped-percentage",
            title="Scoped percentage actuator",
            authors=["Lee"],
            year=2020,
            abstract="Before treatment, actuation strain exceeded 117%.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/scoped-percentage",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_modal_negation(self):
        record = PaperRecord(
            doi="10.1000/modal-negation",
            title="Modal negation actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuation strain cannot exceed 117% in this material.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/modal-negation",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_leading_no_negation(self):
        record = PaperRecord(
            doi="10.1000/leading-no",
            title="Leading no actuator",
            authors=["Lee"],
            year=2020,
            abstract="No actuation strain above 100% was observed.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/leading-no",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_prepositional_scope(self):
        record = PaperRecord(
            doi="10.1000/prepositional-scope",
            title="Prepositional scope actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuation strain exceeded 117% in saline solution.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/prepositional-scope",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_suffix_bounded_percentage(self):
        record = PaperRecord(
            doi="10.1000/suffix-bound",
            title="Suffix bound actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuation strain was 117% or less.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/suffix-bound",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_thousands_separator_claim(self):
        record = PaperRecord(
            doi="10.1000/thousands-claim",
            title="Thousand strain actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuated strains up to 117% were demonstrated.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/thousands-claim",
                    "--claim",
                    "actuation strain above 1,000%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_accepts_thousands_separator_evidence(self):
        record = PaperRecord(
            doi="10.1000/thousands-evidence",
            title="Thousand strain actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuated strain reached 1,200%.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/thousands-evidence",
                    "--claim",
                    "actuation strain above 1000%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "SUPPORTED")
        self.assertEqual(payload["verdict"], "ACCEPT")
        self.assertIn("1,200%", payload["evidence"])

    def test_check_claim_accepts_matching_generic_percentage_subject(self):
        record = PaperRecord(
            doi="10.1000/generic-percentage",
            title="Generic percentage result",
            authors=["Lee"],
            year=2020,
            abstract="Device efficiency reached 95%.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/generic-percentage",
                    "--claim",
                    "device efficiency above 90%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "SUPPORTED")
        self.assertEqual(payload["verdict"], "ACCEPT")

    def test_check_claim_exits_nonzero_for_present_reporting_frame(self):
        record = PaperRecord(
            doi="10.1000/present-reporting",
            title="Present reporting actuator",
            authors=["Lee"],
            year=2020,
            abstract="These results suggest actuation strain exceeded 117%.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/present-reporting",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_attributed_percentage_frame(self):
        record = PaperRecord(
            doi="10.1000/attributed-frame",
            title="Attributed frame actuator",
            authors=["Lee"],
            year=2020,
            abstract="The authors found actuation strain exceeded 117%.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/attributed-frame",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_projected_percentage_frame(self):
        record = PaperRecord(
            doi="10.1000/projected-frame",
            title="Projected frame actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuation strain was projected to exceed 117%.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/projected-frame",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_verify_doi_exits_nonzero_for_high_similarity_wrong_title(self):
        record = PaperRecord(
            doi="10.1000/near-miss-title",
            title="Electroactive polymer actuators for in vitro applications",
            authors=["Lee"],
            year=2020,
            abstract=None,
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "verify-doi",
                    "10.1000/near-miss-title",
                    "--title",
                    "Electroactive polymer actuators for in vivo applications",
                    "--first-author",
                    "Lee",
                    "--year",
                    "2020",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["verdict"], "REJECT")
        self.assertIn("title", payload["mismatches"])

    def test_check_claim_exits_nonzero_for_hedged_frame(self):
        record = PaperRecord(
            doi="10.1000/hedged-frame",
            title="Hedged frame actuator",
            authors=["Lee"],
            year=2020,
            abstract="These results indicate actuation strain exceeded 117%.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/hedged-frame",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_introductory_scoped_percentage(self):
        record = PaperRecord(
            doi="10.1000/introductory-scope",
            title="Introductory scope actuator",
            authors=["Lee"],
            year=2020,
            abstract=(
                "Experimentally, under standard conditions, "
                "actuation strain exceeded 117%."
            ),
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/introductory-scope",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_condition_scoped_percentage(self):
        record = PaperRecord(
            doi="10.1000/condition-scope",
            title="Condition scope actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuation strain exceeded 117% at 5 V.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/condition-scope",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_punctuation_scoped_percentage(self):
        record = PaperRecord(
            doi="10.1000/punctuation-scope",
            title="Punctuation scope actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuation strain exceeded 117%, at 5 V.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/punctuation-scope",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_approximate_percentage(self):
        record = PaperRecord(
            doi="10.1000/approximate-percentage",
            title="Approximate percentage actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuation strain was approximately 117%.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/approximate-percentage",
                    "--claim",
                    "actuation strain 117%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_symbolic_approximate_percentage(self):
        record = PaperRecord(
            doi="10.1000/symbolic-approximate",
            title="Symbolic approximate actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuation strain exceeded ≈117%.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/symbolic-approximate",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_punctuation_bounded_percentage(self):
        record = PaperRecord(
            doi="10.1000/punctuation-bound",
            title="Punctuation bound actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuation strain was 117%, or more.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/punctuation-bound",
                    "--claim",
                    "actuation strain 117%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_named_bounded_percentage(self):
        record = PaperRecord(
            doi="10.1000/named-bound",
            title="Named bound actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuation strain was 117% maximum.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/named-bound",
                    "--claim",
                    "actuation strain 117%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_symbolic_bounded_percentage(self):
        record = PaperRecord(
            doi="10.1000/symbolic-bound",
            title="Symbolic bound actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuation strain was <117%.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/symbolic-bound",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_no_greater_upper_bound(self):
        record = PaperRecord(
            doi="10.1000/no-greater-bound",
            title="No greater bound actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuation strain was no greater than 117%.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/no-greater-bound",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_less_than_or_equal_upper_bound(self):
        record = PaperRecord(
            doi="10.1000/less-than-equal-bound",
            title="Less than equal bound actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuation strain was less than or equal to 117%.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/less-than-equal-bound",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_named_bounded_text_claim(self):
        record = PaperRecord(
            doi="10.1000/named-bound-text",
            title="Named bound text actuator",
            authors=["Lee"],
            year=2020,
            abstract="The device lifetime was 5000 cycles minimum.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/named-bound-text",
                    "--claim",
                    "the device lifetime was 5000 cycles",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_aggregate_text_claim(self):
        record = PaperRecord(
            doi="10.1000/aggregate-text",
            title="Aggregate text actuator",
            authors=["Lee"],
            year=2020,
            abstract="The device lifetime was 5000 cycles on average.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/aggregate-text",
                    "--claim",
                    "the device lifetime was 5000 cycles",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_non_strain_percentage(self):
        record = PaperRecord(
            doi="10.1000/mixed-quantity",
            title="Mixed quantity actuator",
            authors=["Lee"],
            year=2020,
            abstract=(
                "Actuation strain reached 42%, voltage efficiency improved by "
                "200% under the same protocol."
            ),
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/mixed-quantity",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_for_strain_energy_percentage(self):
        record = PaperRecord(
            doi="10.1000/strain-energy",
            title="Strain energy actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuation caused strain energy to increase by 117%.",
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/strain-energy",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual(payload["verdict"], "WARN")

    def test_check_claim_exits_nonzero_when_claim_is_unverifiable(self):
        record = PaperRecord(
            doi="10.1000/noabstract",
            title="Smart material paper",
            authors=["Kim"],
            year=2021,
            abstract=None,
            source="fixture",
        )
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "check-claim",
                    "10.1000/noabstract",
                    "--claim",
                    "actuation strain above 100%",
                    "--json",
                ],
                client=FakeClient(record),
                abstract_clients=[],
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "UNVERIFIABLE")
        self.assertEqual(payload["verdict"], "WARN")

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

    def test_check_file_preserves_results_when_one_row_raises(self):
        good = PaperRecord(
            doi="10.1000/good",
            title="Good paper",
            authors=["Lee"],
            year=2024,
            abstract="The model achieved 95% accuracy.",
            source="fixture",
        )
        client = MappingClient(
            {"10.1000/good": good},
            errors={"10.1000/bad": RuntimeError("upstream failed")},
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "id": "good",
                                "doi": "10.1000/good",
                                "claim": "The model achieved 95% accuracy.",
                            }
                        ),
                        json.dumps(
                            {
                                "id": "bad",
                                "doi": "10.1000/bad",
                                "claim": "The model achieved 95% accuracy.",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    ["check-file", str(path), "--json"],
                    client=client,
                    abstract_clients=[],
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["summary"]["total"], 2)
        self.assertEqual(payload["summary"]["accept"], 1)
        self.assertEqual(payload["summary"]["failed"], 1)
        self.assertEqual(payload["results"][0]["verdict"], "ACCEPT")
        self.assertEqual(payload["results"][1]["error_code"], "ROW_CHECK_ERROR")
        self.assertIn("upstream failed", payload["results"][1]["reason"])

    def test_check_file_json_contract_for_agent_routing(self):
        good = PaperRecord(
            doi="10.1000/good",
            title="Good paper",
            authors=["Lee"],
            year=2024,
            abstract="The model achieved 95% accuracy.",
            source="fixture",
        )
        client = MappingClient(
            {"10.1000/good": good},
            errors={"10.1000/bad": RuntimeError("upstream failed")},
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "id": "accepted-claim",
                                "doi": "10.1000/good",
                                "claim": "The model achieved 95% accuracy.",
                                "note": "draft paragraph 4",
                            }
                        ),
                        json.dumps(
                            {
                                "id": "failed-claim",
                                "doi": "10.1000/bad",
                                "claim": "The model achieved 95% accuracy.",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    ["check-file", str(path), "--json"],
                    client=client,
                    abstract_clients=[],
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(
            set(payload["summary"]),
            {"total", "accept", "warn", "reject", "partial", "unverifiable", "failed"},
        )
        self.assertEqual(payload["summary"]["total"], 2)
        self.assertEqual(len(payload["results"]), 2)

        required_result_keys = {
            "row_number",
            "id",
            "doi",
            "claim",
            "status",
            "verdict",
            "reason",
            "evidence",
            "abstract_source",
            "source_attempts",
            "error_code",
        }
        for result in payload["results"]:
            with self.subTest(result=result["id"]):
                self.assertTrue(required_result_keys <= set(result))

        self.assertEqual(payload["results"][0]["note"], "draft paragraph 4")
        self.assertEqual(payload["results"][0]["error_code"], "CLAIM_SUPPORTED")
        self.assertEqual(payload["results"][1]["error_code"], "ROW_CHECK_ERROR")


if __name__ == "__main__":
    unittest.main()
