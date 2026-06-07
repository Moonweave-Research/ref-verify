import unittest

from ref_verify.crossref import parse_crossref_work
from ref_verify.doi_check import verify_doi_metadata
from ref_verify.models import CitationInput


class CrossrefTests(unittest.TestCase):
    def test_parses_work_message_into_paper_record(self):
        message = {
            "DOI": "10.1000/example",
            "title": ["Dielectric elastomer actuators"],
            "author": [
                {"family": "Pelrine", "given": "Ronald"},
                {"family": "Kornbluh", "given": "Roy"},
            ],
            "published-print": {"date-parts": [[2000, 1, 1]]},
            "container-title": ["Science"],
            "abstract": "<jats:p>Actuated strains up to 117% were demonstrated.</jats:p>",
            "URL": "https://doi.org/10.1000/example",
        }

        record = parse_crossref_work(message)

        self.assertEqual(record.doi, "10.1000/example")
        self.assertEqual(record.title, "Dielectric elastomer actuators")
        self.assertEqual(record.authors, ["Pelrine", "Kornbluh"])
        self.assertEqual(record.year, 2000)
        self.assertEqual(record.journal, "Science")
        self.assertEqual(record.abstract, "Actuated strains up to 117% were demonstrated.")

    def test_does_not_use_created_timestamp_as_publication_year(self):
        message = {
            "DOI": "10.1000/created-only",
            "title": ["Created timestamp is not publication"],
            "author": [{"family": "Lee", "given": "Jane"}],
            "created": {"date-parts": [[2020, 1, 1]]},
        }

        record = parse_crossref_work(message)

        self.assertIsNone(record.year)

    def test_preserves_group_author_name(self):
        message = {
            "DOI": "10.1000/group-author",
            "title": ["Consensus statement"],
            "author": [{"name": "WHO Working Group"}],
            "issued": {"date-parts": [[2024]]},
        }

        record = parse_crossref_work(message)

        self.assertEqual(record.authors, ["WHO Working Group"])

    def test_group_author_record_verifies_metadata(self):
        message = {
            "DOI": "10.1000/group-author",
            "title": ["Consensus statement"],
            "author": [{"name": "WHO Working Group"}],
            "issued": {"date-parts": [[2024]]},
        }

        record = parse_crossref_work(message)
        result = verify_doi_metadata(
            CitationInput(
                doi="10.1000/group-author",
                title="Consensus statement",
                first_author="WHO Working Group",
                year=2024,
            ),
            record,
        )

        self.assertEqual(result.verdict, "PASS")


if __name__ == "__main__":
    unittest.main()
