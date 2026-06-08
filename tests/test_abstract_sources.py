import unittest

from ref_verify.pubmed import parse_pubmed_article
from ref_verify.semantic_scholar import parse_semantic_scholar_paper


class AbstractSourceTests(unittest.TestCase):
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
