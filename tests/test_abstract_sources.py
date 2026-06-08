import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from ref_verify.abstract_lookup import AbstractSourceError
from ref_verify.openalex import parse_openalex_work, reconstruct_openalex_abstract
from ref_verify.pubmed import parse_pubmed_article
from ref_verify.semantic_scholar import SemanticScholarClient, parse_semantic_scholar_paper


class _JsonResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        import json

        return json.dumps(self.payload).encode("utf-8")


class AbstractSourceTests(unittest.TestCase):
    def test_reconstructs_openalex_inverted_index(self):
        abstract = reconstruct_openalex_abstract(
            {
                "The": [0],
                "actuator": [1],
                "survived": [2],
                "5000": [3],
                "cycles.": [4],
            }
        )

        self.assertEqual(abstract, "The actuator survived 5000 cycles.")

    def test_parses_openalex_doi_bound_abstract(self):
        record = parse_openalex_work(
            {
                "doi": "https://doi.org/10.1000/openalex",
                "title": "OpenAlex actuator",
                "authorships": [
                    {"author": {"display_name": "Jane Kim"}},
                    {"author": {"display_name": "Lee Lab"}},
                ],
                "publication_year": 2024,
                "primary_location": {"source": {"display_name": "Journal of Tests"}},
                "id": "https://openalex.org/W123",
                "abstract_inverted_index": {
                    "The": [0],
                    "actuator": [1],
                    "survived": [2],
                    "5000": [3],
                    "cycles.": [4],
                },
            }
        )

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.doi, "10.1000/openalex")
        self.assertEqual(record.source, "OpenAlex")
        self.assertEqual(record.abstract, "The actuator survived 5000 cycles.")
        self.assertEqual(record.authors, ["Jane Kim", "Lee Lab"])
        self.assertEqual(record.journal, "Journal of Tests")
        self.assertEqual(record.url, "https://openalex.org/W123")

    def test_openalex_requires_abstract_and_doi(self):
        self.assertIsNone(
            parse_openalex_work(
                {
                    "doi": "https://doi.org/10.1000/openalex",
                    "abstract_inverted_index": None,
                }
            )
        )
        self.assertIsNone(
            parse_openalex_work(
                {
                    "abstract_inverted_index": {"Text": [0]},
                }
            )
        )

    def test_parses_semantic_scholar_doi_bound_abstract(self):
        record = parse_semantic_scholar_paper(
            {
                "title": "Durable actuator",
                "authors": [{"name": "Kim"}, {"name": "Lee"}],
                "year": 2024,
                "abstract": "The actuator survived 5000 cycles.",
                "externalIds": {"DOI": "10.1000/example"},
                "url": "https://www.semanticscholar.org/paper/example",
                "venue": "Science",
            }
        )

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.doi, "10.1000/example")
        self.assertEqual(record.source, "Semantic Scholar")
        self.assertEqual(record.abstract, "The actuator survived 5000 cycles.")
        self.assertEqual(record.authors, ["Kim", "Lee"])

    def test_semantic_scholar_requires_abstract_and_doi(self):
        self.assertIsNone(
            parse_semantic_scholar_paper(
                {
                    "title": "No abstract",
                    "externalIds": {"DOI": "10.1000/example"},
                }
            )
        )

    def test_semantic_scholar_retries_429_once_then_parses_record(self):
        first = HTTPError(
            url="https://example.test",
            code=429,
            msg="Too Many Requests",
            hdrs=None,
            fp=None,
        )
        response = _JsonResponse(
            {
                "title": "Durable actuator",
                "authors": [{"name": "Kim"}],
                "year": 2024,
                "abstract": "The actuator survived 5000 cycles.",
                "externalIds": {"DOI": "10.1000/example"},
            }
        )

        with patch(
            "ref_verify.semantic_scholar.urlopen",
            side_effect=[first, response],
        ) as urlopen:
            client = SemanticScholarClient(timeout=1.0, max_retries=1, retry_delay=0)

            record = client.fetch_record("10.1000/example")

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.abstract, "The actuator survived 5000 cycles.")
        self.assertEqual(urlopen.call_count, 2)

    def test_semantic_scholar_reports_429_as_rate_limited(self):
        error = HTTPError(
            url="https://example.test",
            code=429,
            msg="Too Many Requests",
            hdrs=None,
            fp=None,
        )

        with patch("ref_verify.semantic_scholar.urlopen", side_effect=error):
            client = SemanticScholarClient(timeout=1.0, max_retries=0, retry_delay=0)

            with self.assertRaises(AbstractSourceError) as context:
                client.fetch_record("10.1000/example")

        self.assertEqual(context.exception.status, "RATE_LIMITED")
        self.assertIsNone(
            parse_semantic_scholar_paper(
                {
                    "title": "No DOI",
                    "abstract": "The actuator survived 5000 cycles.",
                    "externalIds": {},
                }
            )
        )

    def test_parses_pubmed_structured_abstract_and_doi(self):
        xml_payload = """<?xml version="1.0" ?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345</PMID>
      <Article>
        <Journal>
          <Title>Journal of Tests</Title>
          <JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue>
        </Journal>
        <ArticleTitle>Clinical temperature study</ArticleTitle>
        <AuthorList>
          <Author><LastName>Garcia</LastName></Author>
          <Author><CollectiveName>Trial Group</CollectiveName></Author>
        </AuthorList>
        <Abstract>
          <AbstractText Label="METHODS">Samples were maintained at 37 °C.</AbstractText>
          <AbstractText Label="RESULTS">Cell viability reached 95%.</AbstractText>
        </Abstract>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="doi">10.1000/pubmed</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""

        record = parse_pubmed_article(xml_payload)

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.doi, "10.1000/pubmed")
        self.assertEqual(record.source, "PubMed")
        self.assertIn("METHODS: Samples were maintained at 37 °C.", record.abstract)
        self.assertIn("RESULTS: Cell viability reached 95%.", record.abstract)
        self.assertEqual(record.authors, ["Garcia", "Trial Group"])
        self.assertEqual(record.url, "https://pubmed.ncbi.nlm.nih.gov/12345/")

    def test_pubmed_requires_abstract_and_doi(self):
        no_doi = """<PubmedArticleSet><PubmedArticle><MedlineCitation><Article>
<ArticleTitle>No DOI</ArticleTitle>
<Abstract><AbstractText>Samples were maintained at 37 °C.</AbstractText></Abstract>
</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""
        no_abstract = """<PubmedArticleSet><PubmedArticle><MedlineCitation><Article>
<ArticleTitle>No abstract</ArticleTitle>
</Article></MedlineCitation><PubmedData><ArticleIdList>
<ArticleId IdType="doi">10.1000/noabstract</ArticleId>
</ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>"""

        self.assertIsNone(parse_pubmed_article(no_doi))
        self.assertIsNone(parse_pubmed_article(no_abstract))


if __name__ == "__main__":
    unittest.main()
