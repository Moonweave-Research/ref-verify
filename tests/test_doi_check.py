import unittest

from ref_verify.doi_check import verify_doi_metadata
from ref_verify.models import CitationInput, PaperRecord


class DoiCheckTests(unittest.TestCase):
    def test_passes_matching_title_author_year(self):
        provided = CitationInput(
            doi="10.1000/example",
            title="Dielectric elastomer actuators",
            first_author="Pelrine",
            year=2000,
        )
        fetched = PaperRecord(
            doi="10.1000/example",
            title="Dielectric elastomer actuators",
            authors=["Pelrine", "Kornbluh"],
            year=2000,
            abstract=None,
            source="fixture",
        )

        result = verify_doi_metadata(provided, fetched)

        self.assertEqual(result.verdict, "PASS")
        self.assertEqual(result.mismatches, [])

    def test_rejects_wrong_resolved_paper(self):
        provided = CitationInput(
            doi="10.1000/chapter",
            title="Dielectric elastomers as electromechanical transducers",
            first_author="Carpi",
            year=2011,
        )
        fetched = PaperRecord(
            doi="10.1000/chapter",
            title="Chapter 1 - Introduction to dielectric elastomers",
            authors=["Pelrine", "Kornbluh"],
            year=2008,
            abstract=None,
            source="fixture",
        )

        result = verify_doi_metadata(provided, fetched)

        self.assertEqual(result.verdict, "REJECT")
        self.assertIn("title", result.mismatches)
        self.assertIn("first_author", result.mismatches)
        self.assertIn("year", result.mismatches)

    def test_rejects_high_similarity_title_when_numeric_tokens_differ(self):
        provided = CitationInput(
            doi="10.1000/near-miss",
            title="High-Speed Electrically Actuated Elastomers with Strain Greater Than 100%",
            first_author="Pelrine",
            year=2000,
        )
        fetched = PaperRecord(
            doi="10.1000/near-miss",
            title="High-Speed Electrically Actuated Elastomers with Strain Greater Than 10%",
            authors=["Pelrine"],
            year=2000,
            abstract=None,
            source="fixture",
        )

        result = verify_doi_metadata(provided, fetched)

        self.assertEqual(result.verdict, "REJECT")
        self.assertIn("title", result.mismatches)

    def test_warns_when_only_year_differs(self):
        provided = CitationInput(
            doi="10.1000/example",
            title="Dielectric elastomer actuators",
            first_author="Pelrine",
            year=2001,
        )
        fetched = PaperRecord(
            doi="10.1000/example",
            title="Dielectric elastomer actuators",
            authors=["Pelrine", "Kornbluh"],
            year=2000,
            abstract=None,
            source="fixture",
        )

        result = verify_doi_metadata(provided, fetched)

        self.assertEqual(result.verdict, "WARN")
        self.assertEqual(result.mismatches, ["year"])


if __name__ == "__main__":
    unittest.main()
