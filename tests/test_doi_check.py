import unittest

from ref_verify.doi_check import normalize_doi, verify_doi_metadata
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

    def test_passes_matching_accented_author_surname(self):
        provided = CitationInput(
            doi="10.1000/example",
            title="Dielectric elastomer actuators",
            first_author="Garcia",
            year=2020,
        )
        fetched = PaperRecord(
            doi="10.1000/example",
            title="Dielectric elastomer actuators",
            authors=["García", "Lee"],
            year=2020,
            abstract=None,
            source="fixture",
        )

        result = verify_doi_metadata(provided, fetched)

        self.assertEqual(result.verdict, "PASS")
        self.assertEqual(result.mismatches, [])

    def test_rejects_different_group_authors_with_same_suffix(self):
        provided = CitationInput(
            doi="10.1000/group-author",
            title="Consensus statement",
            first_author="WHO Working Group",
            year=2024,
        )
        fetched = PaperRecord(
            doi="10.1000/group-author",
            title="Consensus statement",
            authors=["Malaria Genomic Epidemiology Network Study Group"],
            year=2024,
            abstract=None,
            source="fixture",
        )

        result = verify_doi_metadata(provided, fetched)

        self.assertEqual(result.verdict, "REJECT")
        self.assertIn("first_author", result.mismatches)

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

    def test_rejects_when_resolved_doi_differs_from_requested_doi(self):
        provided = CitationInput(
            doi="10.1000/requested",
            title="Dielectric elastomer actuators",
            first_author="Pelrine",
            year=2000,
        )
        fetched = PaperRecord(
            doi="10.1000/other",
            title="Dielectric elastomer actuators",
            authors=["Pelrine", "Kornbluh"],
            year=2000,
            abstract=None,
            source="fixture",
        )

        result = verify_doi_metadata(provided, fetched)

        self.assertEqual(result.verdict, "REJECT")
        self.assertIn("doi", result.mismatches)

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

    def test_rejects_high_similarity_title_when_meaningful_tokens_differ(self):
        cases = (
            (
                "Electroactive polymer actuators for in vivo applications",
                "Electroactive polymer actuators for in vitro applications",
            ),
            (
                "Hydrogel actuator lifetime after annealing",
                "Hydrogel actuator lifetime before annealing",
            ),
            (
                "Review of dielectric elastomer actuators",
                "Design of dielectric elastomer actuators",
            ),
        )

        for provided_title, fetched_title in cases:
            with self.subTest(provided_title=provided_title):
                provided = CitationInput(
                    doi="10.1000/near-miss",
                    title=provided_title,
                    first_author="Lee",
                    year=2020,
                )
                fetched = PaperRecord(
                    doi="10.1000/near-miss",
                    title=fetched_title,
                    authors=["Lee"],
                    year=2020,
                    abstract=None,
                    source="fixture",
                )

                result = verify_doi_metadata(provided, fetched)

                self.assertEqual(result.verdict, "REJECT")
                self.assertIn("title", result.mismatches)

    def test_rejects_titles_that_only_differ_by_greek_letter(self):
        provided = CitationInput(
            doi="10.1000/phase",
            title="β-phase PVDF actuators",
            first_author="Lee",
            year=2020,
        )
        fetched = PaperRecord(
            doi="10.1000/phase",
            title="α-phase PVDF actuators",
            authors=["Lee"],
            year=2020,
            abstract=None,
            source="fixture",
        )

        result = verify_doi_metadata(provided, fetched)

        self.assertEqual(result.verdict, "REJECT")
        self.assertIn("title", result.mismatches)

    def test_passes_transliterated_greek_letter_title(self):
        provided = CitationInput(
            doi="10.1000/phase",
            title="beta-phase PVDF actuators",
            first_author="Lee",
            year=2020,
        )
        fetched = PaperRecord(
            doi="10.1000/phase",
            title="β-phase PVDF actuators",
            authors=["Lee"],
            year=2020,
            abstract=None,
            source="fixture",
        )

        result = verify_doi_metadata(provided, fetched)

        self.assertEqual(result.verdict, "PASS")
        self.assertEqual(result.mismatches, [])

    def test_normalizes_pasted_doi_trailing_punctuation(self):
        cases = (
            ("10.1000/example.", "10.1000/example"),
            ("https://doi.org/10.1000/example,", "10.1000/example"),
            ("DOI: 10.1000/example;", "10.1000/example"),
            ("doi.org/10.1000/example)", "10.1000/example"),
        )

        for raw_doi, expected in cases:
            with self.subTest(raw_doi=raw_doi):
                self.assertEqual(normalize_doi(raw_doi), expected)

    def test_normalizes_percent_encoded_pasted_doi(self):
        cases = (
            ("https://doi.org/10.1000%2Fexample", "10.1000/example"),
            ("doi:10.1000%2F%28example%29", "10.1000/(example)"),
        )

        for raw_doi, expected in cases:
            with self.subTest(raw_doi=raw_doi):
                self.assertEqual(normalize_doi(raw_doi), expected)

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

    def test_warns_when_only_year_is_provided_even_if_it_matches(self):
        provided = CitationInput(
            doi="10.1000/year-only",
            year=2000,
        )
        fetched = PaperRecord(
            doi="10.1000/year-only",
            title="Completely Different Paper",
            authors=["Wrong"],
            year=2000,
            abstract=None,
            source="fixture",
        )

        result = verify_doi_metadata(provided, fetched)

        self.assertEqual(result.verdict, "WARN")
        self.assertIn("metadata", result.mismatches)

    def test_warns_when_provided_year_is_missing_from_fetched_record(self):
        provided = CitationInput(
            doi="10.1000/missing-year",
            year=2020,
        )
        fetched = PaperRecord(
            doi="10.1000/missing-year",
            title="Dielectric elastomer actuators",
            authors=["Pelrine", "Kornbluh"],
            year=None,
            abstract=None,
            source="fixture",
        )

        result = verify_doi_metadata(provided, fetched)

        self.assertEqual(result.verdict, "WARN")
        self.assertIn("metadata", result.mismatches)
        self.assertIn("year", result.mismatches)


if __name__ == "__main__":
    unittest.main()
