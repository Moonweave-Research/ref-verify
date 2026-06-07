import io
import json
import unittest
from contextlib import redirect_stdout

from ref_verify.cli import main
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
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "UNVERIFIABLE")
        self.assertEqual(payload["verdict"], "WARN")


if __name__ == "__main__":
    unittest.main()
