import unittest

from ref_verify.crossref import parse_crossref_work


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


if __name__ == "__main__":
    unittest.main()
