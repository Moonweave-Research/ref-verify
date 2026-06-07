import io
import json
import unittest
from contextlib import redirect_stdout

from ref_verify.cli import main
from ref_verify.models import PaperRecord


class FakeClient:
    def __init__(self, record):
        self.record = record

    def fetch_work(self, doi):
        if doi != self.record.doi:
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
