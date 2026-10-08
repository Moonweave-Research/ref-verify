import io
import json
import os
import tempfile
import unittest
from email.message import Message
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

from ref_verify.cli import main
from ref_verify.cache import ResponseCache
from ref_verify.crossref import CrossrefClient, parse_crossref_work
from ref_verify.models import PaperRecord
from ref_verify.reference_parse import ReferenceEntry, parse_bibtex
from ref_verify.reference_resolve import (
    _looks_titleless,
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
    def __init__(
        self, works=None, candidates=None, errors=None, search_error=None, agencies=None, filtered_candidates=None
    ):
        self.works = works or {}
        self.candidates = candidates or []
        # Returned by a search with author/year filters, like CrossRef's structured search.
        self.filtered_candidates = filtered_candidates or []
        self.filtered_queries = []
        self.errors = errors or {}
        self.search_error = search_error
        self.agencies = agencies or {}
        self.queries = []

    def registration_agency(self, doi):
        return self.agencies.get(doi)

    def fetch_work(self, doi):
        if doi in self.errors:
            raise self.errors[doi]
        if doi not in self.works:
            raise _not_found(doi)
        return self.works[doi]

    def search_bibliographic(self, query, rows=3, **filters):
        if filters:
            self.filtered_queries.append((query, filters))
            return list(self.filtered_candidates)
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

    def test_plain_text_doi_pointing_at_another_paper_is_a_mismatch(self):
        entry = _entry(doi=PELRINE_DOI, raw="Smith J. A study of imaginary results. 2021.")

        result = check_reference(entry, FakeCrossref(works={PELRINE_DOI: PELRINE}))

        # Shown as a mismatch with the paper the DOI really names, not as "could not confirm".
        self.assertEqual(result.verdict, "WARN")
        self.assertEqual(result.status, "MISMATCH")
        self.assertIsNone(result.error_code)
        self.assertIn(f'"{PELRINE.title}" (Pelrine, 2000)', result.reason)

    def test_plain_text_doi_swap_with_the_same_first_author_is_a_mismatch(self):
        entry = _entry(
            doi=PELRINE_DOI,
            raw="Pelrine, R. (2001). Silicone actuators for underwater swimming robots. Soft Matter, 3, 1-9.",
        )

        result = check_reference(entry, FakeCrossref(works={PELRINE_DOI: PELRINE}))

        self.assertEqual(result.status, "MISMATCH")
        self.assertEqual(result.verdict, "WARN")

    def test_markup_in_crossref_title_does_not_reject_the_reference(self):
        record = parse_crossref_work(
            {
                "DOI": "10.1002/adma.201102306",
                "title": ["Two\u2010Dimensional Nanocrystals Produced by Exfoliation of Ti <sub>3</sub> AlC <sub>2</sub>"],
                "author": [{"family": "Naguib"}],
                "published-print": {"date-parts": [[2011]]},
            }
        )
        bib = _entry(doi=record.doi, title="Two-Dimensional Nanocrystals Produced by Exfoliation of Ti3AlC2",
                     first_author="Naguib", year=2011)
        text = _entry(doi=record.doi, raw="Naguib, M. et al. Two-Dimensional Nanocrystals Produced by Exfoliation of Ti3AlC2. Adv. Mater. 2011.")
        client = FakeCrossref(works={record.doi: record})

        self.assertEqual(record.title, "Two\u2010Dimensional Nanocrystals Produced by Exfoliation of Ti 3 AlC 2")
        self.assertEqual(check_reference(bib, client).verdict, "PASS")
        self.assertEqual(check_reference(text, client).verdict, "PASS")

    def test_escaped_title_tags_are_removed(self):
        record = parse_crossref_work(
            {"DOI": "10.1117/12.349672", "title": ["&lt;title&gt;High-field electrostriction&lt;/title&gt;"]}
        )

        self.assertEqual(record.title, "High-field electrostriction")

    def test_korean_title_and_hangul_author_match_crossref_original_title(self):
        record = parse_crossref_work(
            {
                "DOI": "10.7317/pk.2012.36.4.455",
                "title": ["Preparation of PNIPAM Hydrogel Containing Lipoic Acid"],
                "original-title": ["리포익산을 함유한 PNIPAM 하이드로젤의 제조"],
                "author": [{"family": "Yoon", "given": "Hye-Ri"}, {"family": "Lee", "given": "Jong-Hwi"}],
                "published-print": {"date-parts": [[2012]]},
            }
        )
        client = FakeCrossref(works={record.doi: record})
        bib = _entry(doi=record.doi, title="리포익산을 함유한 PNIPAM 하이드로젤의 제조", first_author="윤혜리", year=2012)
        text = _entry(
            doi=record.doi,
            year=2012,
            raw="윤혜리, 이종휘, “리포익산을 함유한 PNIPAM 하이드로젤의 제조”, 폴리머, 36권, 4호, pp. 455–460, 2012.",
        )

        self.assertEqual(check_reference(bib, client).verdict, "PASS")
        self.assertEqual(check_reference(text, client).verdict, "PASS")

    def test_hangul_author_with_another_surname_is_not_passed(self):
        record = PaperRecord(
            doi="10.7317/pk.x", title="Hydrogel study", authors=["Yoon"], year=2012, abstract=None,
            source="CrossRef", alt_titles=["하이드로젤 연구"],
        )
        client = FakeCrossref(works={record.doi: record})

        bib = check_reference(_entry(doi=record.doi, title="하이드로젤 연구", first_author="김철수", year=2012), client)
        text = check_reference(_entry(doi=record.doi, year=2012, raw="김철수, “하이드로젤 연구”, 폴리머, 2012."), client)

        self.assertEqual(bib.verdict, "REJECT")
        self.assertIn("reference: 김철수; CrossRef: Yoon", bib.reason)
        self.assertEqual(text.verdict, "WARN")
        self.assertEqual(text.status, "UNVERIFIED")
        self.assertIn("first author (Yoon) was not found", text.reason)

    def test_online_first_year_and_dropped_subtitle_still_pass(self):
        record = parse_crossref_work(
            {
                "DOI": "10.1007/book",
                "title": ["Electroactive Polymers for Robotic Applications"],
                "editor": [{"family": "Kim", "given": "Kwang J."}],
                "published-print": {"date-parts": [[2010, 1]]},
                "published-online": {"date-parts": [[2009, 12]]},
            }
        )
        entry = _entry(
            doi=record.doi,
            title="Electroactive Polymers for Robotic Applications: Artificial Muscles and Sensors",
            first_author="Kim",
            year=2009,
        )

        result = check_reference(entry, FakeCrossref(works={record.doi: record}))

        self.assertEqual(record.alt_years, [2009])
        self.assertEqual(result.verdict, "PASS")

    def test_year_mismatch_reason_names_both_years(self):
        entry = _entry(doi=PELRINE_DOI, title=PELRINE.title, first_author="Pelrine", year=2001)

        result = check_reference(entry, FakeCrossref(works={PELRINE_DOI: PELRINE}))

        self.assertEqual(result.reason, "DOI matches, but the year differs (reference: 2001; CrossRef: 2000).")

    def test_title_mismatch_reason_shows_the_crossref_title(self):
        entry = _entry(doi=PELRINE_DOI, title="A different title", first_author="Pelrine", year=2000)

        result = check_reference(entry, FakeCrossref(works={PELRINE_DOI: PELRINE}))

        self.assertIn(f'the title differs (CrossRef: "{PELRINE.title}")', result.reason)

    def test_doi_registered_outside_crossref_is_unverified_not_rejected(self):
        doi = "10.48550/arxiv.1706.03762"
        client = FakeCrossref(agencies={doi: "DataCite"})

        result = check_reference(_entry(doi=doi, title="Attention Is All You Need"), client)

        self.assertEqual(result.verdict, "WARN")
        self.assertEqual(result.status, "UNVERIFIED")
        self.assertEqual(result.error_code, "DOI_NOT_IN_CROSSREF")
        self.assertIn("registered with DataCite", result.reason)

    def test_doi_unknown_to_every_registry_is_still_rejected(self):
        result = check_reference(_entry(doi="10.9999/dead"), FakeCrossref(agencies={"10.9999/dead": None}))

        self.assertEqual(result.verdict, "REJECT")
        self.assertEqual(result.error_code, "DOI_NOT_FOUND")

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

    def test_rate_limit_and_offline_failures_say_what_to_do(self):
        limited = HTTPError(url="https://api.crossref.org/works", code=429, msg="Too Many Requests", hdrs=None, fp=None)
        offline = URLError("nodename nor servname provided")

        with patch("ref_verify.reference_resolve._sleep") as sleep:
            rate_limited = check_reference(_entry(doi=PELRINE_DOI), FakeCrossref(errors={PELRINE_DOI: limited}))
        unreachable = check_reference(_entry(doi=PELRINE_DOI), FakeCrossref(errors={PELRINE_DOI: offline}))

        self.assertEqual(rate_limited.error_code, "ROW_CHECK_ERROR")
        self.assertIn("Run the same command again in a minute", rate_limited.reason)
        # Re-checked once after a pause before giving up.
        sleep.assert_called_once_with(15.0)
        self.assertIn("could not reach CrossRef (nodename nor servname provided)", unreachable.reason)

    def test_rate_limited_reference_is_rechecked_once_after_retry_after(self):
        headers = Message()
        headers["Retry-After"] = "30"
        limited = HTTPError(url="https://api.crossref.org/works", code=429, msg="Too Many Requests", hdrs=headers, fp=None)

        class OnceLimited(FakeCrossref):
            def fetch_work(self, doi):
                if not self.queries:
                    self.queries.append(doi)
                    raise limited
                return super().fetch_work(doi)

        entry = _entry(doi=PELRINE_DOI, title=PELRINE.title, first_author="Pelrine", year=2000)
        with patch("ref_verify.reference_resolve._sleep") as sleep:
            result = check_reference(entry, OnceLimited(works={PELRINE_DOI: PELRINE}))

        self.assertEqual(result.verdict, "PASS")
        sleep.assert_called_once_with(30.0)

    def test_sici_style_doi_with_angle_brackets_is_looked_up_whole(self):
        doi = "10.1002/1521-3773(20010601)40:11<2004::aid-anie2004>3.0.co;2-5"
        record = PaperRecord(doi=doi, title="Click Chemistry: Diverse Chemical Function from a Few Good Reactions",
                             authors=["Kolb"], year=2001, abstract=None, source="CrossRef")
        entry = parse_bibtex(
            "@article{k, author={Kolb, Hartmuth C.}, title={Click Chemistry: Diverse Chemical Function from a "
            "Few Good Reactions}, year={2001}, doi={" + doi + "}}"
        )[0]

        result = check_reference(entry, FakeCrossref(works={doi: record}))

        self.assertEqual(entry.doi, doi)
        self.assertEqual(result.verdict, "PASS")

    def test_citation_without_subtitle_or_edition_note_passes(self):
        cp2k = PaperRecord(
            doi="10.1063/5.0007045",
            title="CP2K: An electronic structure and molecular dynamics software package - Quickstep: "
            "Efficient and accurate electronic structure calculations",
            authors=["Kühne"], year=2020, abstract=None, source="CrossRef",
        )
        book = PaperRecord(
            doi="10.1117/3.547465",
            title="Electroactive Polymer (EAP) Actuators as Artificial Muscles: Reality, Potential, and Challenges, Second Edition",
            authors=["Bar-Cohen"], year=2004, abstract=None, source="CrossRef",
        )
        client = FakeCrossref(works={cp2k.doi: cp2k, book.doi: book})

        first = check_reference(_entry(doi=cp2k.doi, title="CP2K: An electronic structure and molecular dynamics software package",
                                       first_author="Kühne", year=2020), client)
        second = check_reference(_entry(doi=book.doi, title="Electroactive Polymer (EAP) Actuators as Artificial Muscles: "
                                        "Reality, Potential, and Challenges", first_author="Bar-Cohen", year=2004), client)
        different = check_reference(_entry(doi=cp2k.doi, title="CP2K: A general electronic structure program",
                                           first_author="Kühne", year=2020), client)

        self.assertEqual((first.verdict, second.verdict), ("PASS", "PASS"))
        self.assertEqual(different.verdict, "REJECT")

    def test_lookup_failure_is_counted_as_failed(self):
        entry = _entry(doi=PELRINE_DOI)
        client = FakeCrossref(errors={PELRINE_DOI: RuntimeError("upstream failed")})

        result = check_reference(entry, client)

        self.assertEqual(result.verdict, "WARN")
        self.assertEqual(result.error_code, "ROW_CHECK_ERROR")
        self.assertEqual(reference_payload([result])["summary"]["failed"], 1)


BCS = PaperRecord(
    doi="10.1103/physrev.108.1175",
    title="Theory of Superconductivity",
    authors=["Bardeen", "Cooper", "Schrieffer"],
    year=1957,
    abstract=None,
    source="CrossRef",
    journal="Physical Review",
    journal_abbreviations=["Phys. Rev."],
    volume="108",
    first_page="1175",
)


class TitlelessCitationTests(unittest.TestCase):
    def test_titleless_citation_with_doi_passes_on_journal_volume_page_year_and_author(self):
        entry = _entry(
            doi=BCS.doi,
            year=1957,
            raw="J. Bardeen, L. N. Cooper, and J. R. Schrieffer, Phys. Rev. 108, 1175 (1957). doi:10.1103/physrev.108.1175",
        )

        result = check_reference(entry, FakeCrossref(works={BCS.doi: BCS}))

        self.assertEqual(result.verdict, "PASS")
        self.assertEqual(
            result.reason,
            "The reference has no article title; it matches CrossRef's record for this DOI on journal, volume, "
            "first page, year, and first author.",
        )

    def test_titleless_citation_names_each_field_that_differs(self):
        entry = _entry(
            doi=BCS.doi,
            year=1958,
            raw="J. Bardeen, L. N. Cooper, and J. R. Schrieffer, Phys. Rev. 109, 1175 (1958). doi:10.1103/physrev.108.1175",
        )

        result = check_reference(entry, FakeCrossref(works={BCS.doi: BCS}))

        self.assertEqual((result.verdict, result.status), ("WARN", "MISMATCH"))
        self.assertIn("volume (CrossRef: 108); year (reference: 1958; CrossRef: 1957)", result.reason)
        self.assertNotIn("may point to a different paper", result.reason)

    def test_abbreviated_journal_matches_the_full_name(self):
        prl = PaperRecord(
            doi="10.1103/physrevlett.98.123456", title="Some letter", authors=["Author"], year=2007,
            abstract=None, source="CrossRef", journal="Physical Review Letters", volume="98", first_page="123456",
        )
        entry = _entry(doi=prl.doi, year=2007, raw="A. Author et al., Phys. Rev. Lett. 98, 123456 (2007).")

        self.assertEqual(check_reference(entry, FakeCrossref(works={prl.doi: prl})).verdict, "PASS")

    def test_titleless_citation_without_doi_resolves_only_on_full_agreement(self):
        epr = PaperRecord(
            doi="10.1103/physrev.47.777",
            title="Can Quantum-Mechanical Description of Physical Reality Be Considered Complete?",
            authors=["Einstein", "Podolsky", "Rosen"], year=1935, abstract=None, source="CrossRef",
            journal="Physical Review", volume="47", first_page="777",
        )
        good = _entry(year=1935, raw="A. Einstein, B. Podolsky, and N. Rosen, Phys. Rev. 47, 777 (1935).")
        wrong_page = _entry(year=1935, raw="A. Einstein, B. Podolsky, and N. Rosen, Phys. Rev. 47, 778 (1935).")

        resolved = check_reference(good, FakeCrossref(candidates=[epr]))
        unmatched = check_reference(wrong_page, FakeCrossref(candidates=[epr]))

        self.assertEqual((resolved.verdict, resolved.resolved_doi), ("PASS", epr.doi))
        self.assertIn("no article title", resolved.reason)
        self.assertEqual((unmatched.status, unmatched.error_code), ("UNVERIFIED", "REFERENCE_UNMATCHED"))

    def test_titleless_citation_missing_from_first_search_is_found_by_author_and_year(self):
        riess = PaperRecord(
            doi="10.1086/300499",
            title="Observational Evidence from Supernovae for an Accelerating Universe and a Cosmological Constant",
            authors=["Riess", "Filippenko"], year=1998, abstract=None, source="CrossRef",
            journal="The Astronomical Journal", journal_abbreviations=["AJ"], volume="116", first_page="1009",
        )
        entry = _entry(year=1998, raw="A. G. Riess et al., Astron. J. 116, 1009 (1998).")
        client = FakeCrossref(candidates=[OTHER], filtered_candidates=[OTHER, riess])

        result = check_reference(entry, client)

        self.assertEqual((result.verdict, result.resolved_doi), ("PASS", riess.doi))
        # No bare year in the query text: it matches far too many records.
        self.assertEqual(
            client.filtered_queries,
            [("Astron. J. 116, 1009", {"author": "Riess", "year_range": (1997, 1998)})],
        )

    def test_second_search_accepts_only_full_agreement_and_reports_retraction(self):
        riess = PaperRecord(
            doi="10.1086/300499", title="Observational Evidence", authors=["Riess"], year=1998, abstract=None,
            source="CrossRef", journal="The Astronomical Journal", volume="116", first_page="1009",
        )
        retracted = PaperRecord(
            doi="10.1000/retracted", title="Retracted letter", authors=["Lee"], year=2010, abstract=None,
            source="CrossRef", journal="Physical Review Letters", volume="104", first_page="1",
            retraction_doi="10.1000/notice",
        )
        titled = _entry(year=1998, raw="A. G. Riess et al., Supernovae prefer open universes. Astron. J. 116, 1009 (1998).")
        wrong_volume = _entry(year=1998, raw="A. G. Riess et al., Astron. J. 117, 1009 (1998).")
        withdrawn = _entry(year=2010, raw="J. Lee et al., Phys. Rev. Lett. 104, 1 (2010).")

        titled_result = check_reference(titled, FakeCrossref(filtered_candidates=[riess]))
        wrong_result = check_reference(wrong_volume, FakeCrossref(filtered_candidates=[riess]))
        withdrawn_result = check_reference(withdrawn, FakeCrossref(filtered_candidates=[retracted]))

        self.assertEqual(titled_result.error_code, "REFERENCE_UNMATCHED")
        self.assertEqual(wrong_result.error_code, "REFERENCE_UNMATCHED")
        self.assertEqual(withdrawn_result.error_code, "PAPER_RETRACTED")

    def test_second_search_runs_only_for_references_that_look_title_less(self):
        titled = FakeCrossref()
        entry = _entry(
            year=2022,
            raw="Smith J, Patel R, Nguyen T. Long-term cardiovascular outcomes of intermittent fasting in adults "
            "with type 2 diabetes: a randomized controlled trial. Lancet Diabetes Endocrinol. 2022;10(4):255-264.",
        )

        result = check_reference(entry, titled)

        self.assertEqual(result.error_code, "REFERENCE_UNMATCHED")
        # A titled reference can never be accepted from the second search, so it is not sent.
        self.assertEqual(titled.filtered_queries, [])
        for raw in (
            "A. G. Riess et al., Astron. J. 116, 1009 (1998).",
            "J. Bardeen, L. N. Cooper, and J. R. Schrieffer, Phys. Rev. 108, 1175 (1957).",
            "Tang, C. W.; VanSlyke, S. A. Applied Physics Letters 1987, 51, 913–915.",
            "B. P. Nguyen and K. Kim, Journal of the Korean Physical Society 64, 1665 (2014).",
        ):
            with self.subTest(raw=raw):
                self.assertTrue(_looks_titleless(raw))
        self.assertFalse(_looks_titleless("A. G. Riess et al., Astron. J. (1998)."))

    def test_no_second_search_for_structured_entries_or_without_a_year(self):
        bib = FakeCrossref()
        no_year = FakeCrossref()

        check_reference(_entry(title="Some title", first_author="Riess", year=1998), bib)
        check_reference(_entry(raw="A. G. Riess et al., Astron. J. 116, 1009."), no_year)

        self.assertEqual((bib.filtered_queries, no_year.filtered_queries), ([], []))

    def test_a_different_title_is_not_excused_as_titleless(self):
        # Right journal, volume, page, year, and author, but an invented title.
        entry = _entry(
            doi=BCS.doi,
            year=1957,
            raw="J. Bardeen, L. N. Cooper, and J. R. Schrieffer, Microscopic origin of magnetic flux pinning. "
            "Phys. Rev. 108, 1175 (1957). doi:10.1103/physrev.108.1175",
        )

        result = check_reference(entry, FakeCrossref(works={BCS.doi: BCS}))

        self.assertNotEqual(result.verdict, "PASS")


class FirstAuthorPositionTests(unittest.TestCase):
    RIESS = PaperRecord(
        doi="10.1086/300499",
        title="Observational Evidence from Supernovae for an Accelerating Universe and a Cosmological Constant",
        authors=["Riess", "Filippenko", "Perlmutter"], year=1998, abstract=None, source="CrossRef",
    )

    def _check(self, record, raw):
        return check_reference(_entry(doi=record.doi, year=record.year, raw=raw), FakeCrossref(works={record.doi: record}))

    def test_second_author_in_first_position_is_not_passed(self):
        result = self._check(
            self.RIESS,
            "Perlmutter S, Riess AG. Observational Evidence from Supernovae for an Accelerating Universe and a "
            "Cosmological Constant. The Astronomical Journal. 1998;116(3):1009-1038. doi:10.1086/300499",
        )

        self.assertNotEqual(result.verdict, "PASS")

    def test_initials_first_and_particle_names_still_pass(self):
        title = self.RIESS.title
        for raw in (
            f"A. G. Riess et al., {title}, Astron. J. 116, 1009 (1998).",
            f"Riess, A. G., Filippenko, A. V. (1998). {title}. AJ, 116, 1009.",
            f"Adam G. Riess and Alexei V. Filippenko. {title}. 1998.",
        ):
            with self.subTest(raw=raw):
                self.assertEqual(self._check(self.RIESS, raw).verdict, "PASS")
        waals = PaperRecord(doi="10.1/w", title="Over de continuiteit", authors=["van der Waals"], year=1873,
                            abstract=None, source="CrossRef")
        lecunff = PaperRecord(doi="10.1/l", title="Ionic liquid actuators", authors=["Le Cunff"], year=2012,
                              abstract=None, source="CrossRef")
        self.assertEqual(self._check(waals, "J. D. van der Waals, Over de continuiteit, 1873.").verdict, "PASS")
        self.assertEqual(self._check(lecunff, "Le Cunff, A., Ionic liquid actuators, 2012.").verdict, "PASS")

    def test_group_author_opening_the_reference_passes(self):
        jama = PaperRecord(
            doi="10.1001/jama.288.3.321",
            title="Risks and Benefits of Estrogen Plus Progestin in Healthy Postmenopausal Women",
            authors=["Writing Group for the Women's Health Initiative Investigators"],
            year=2002, abstract=None, source="CrossRef",
        )
        raw = (
            "Writing Group for the Women's Health Initiative Investigators. Risks and Benefits of Estrogen Plus "
            "Progestin in Healthy Postmenopausal Women. JAMA. 2002;288(3):321-333."
        )

        self.assertEqual(self._check(jama, raw).verdict, "PASS")


class SearchReferenceTests(unittest.TestCase):
    def test_review_reports_and_notices_are_not_taken_as_the_paper(self):
        title = "A pneumonia outbreak associated with a new coronavirus of probable bat origin"
        review = parse_crossref_work(
            {"DOI": "10.14293/review", "type": "peer-review", "title": [f'Review of "{title}"'],
             "relation": {"is-review-of": [{"id": "10.1038/s41586-020-2012-7"}]}}
        )
        opinion = parse_crossref_work(
            {"DOI": "10.3410/f.1", "type": "dataset", "title": [f"Faculty Opinions recommendation of {title}"],
             "author": [{"family": "Zhou"}], "issued": {"date-parts": [[2020]]}}
        )
        addendum = parse_crossref_work(
            {"DOI": "10.1038/addendum", "type": "journal-article", "title": [f"Addendum: {title}"],
             "author": [{"family": "Zhou"}], "issued": {"date-parts": [[2020]]}}
        )
        paper = parse_crossref_work(
            {"DOI": "10.1038/s41586-020-2012-7", "type": "journal-article", "title": [title],
             "author": [{"family": "Zhou"}], "issued": {"date-parts": [[2020]]}}
        )
        entry = _entry(year=2020, raw=f"Zhou, P., Yang, X.-L., et al. (2020). {title}. Nature, 579(7798), 270–273.")

        result = check_reference(entry, FakeCrossref(candidates=[review, opinion, addendum, paper]))

        self.assertTrue(review.is_about_other_work and opinion.is_about_other_work and addendum.is_about_other_work)
        self.assertFalse(paper.is_about_other_work)
        self.assertEqual(result.verdict, "PASS")
        self.assertEqual(result.resolved_doi, paper.doi)

    def test_tex_greek_in_bibtex_title_finds_the_retracted_paper(self):
        retracted = PaperRecord(
            doi="10.1038/nature04533",
            title="A specific amyloid-β protein assembly in the brain impairs memory",
            authors=["Lesné"], year=2006, abstract=None, source="CrossRef", retraction_doi="10.1038/s41586-024-07691-8",
        )
        entry = parse_bibtex(
            "@article{l, author={Lesn{\\'e}, Sylvain}, title={A specific amyloid-$\\beta$ protein assembly "
            "in the brain impairs memory}, journal={Nature}, year={2006}}"
        )[0]
        client = FakeCrossref(candidates=[retracted])

        result = check_reference(entry, client)

        self.assertEqual(entry.title, "A specific amyloid-β protein assembly in the brain impairs memory")
        self.assertEqual(result.error_code, "PAPER_RETRACTED")

    def test_hangul_reference_resolves_through_original_title(self):
        candidate = PaperRecord(
            doi="10.7317/pk.2021.45.6.897",
            title="Evaporative Crystallization System Based on Temperature-Responsive Hydrogel",
            authors=["Kim", "Lee"],
            year=2021,
            abstract=None,
            source="CrossRef",
            alt_titles=["온도감응성 하이드로젤 기반 증발 결정화 시스템"],
        )
        entry = _entry(
            year=2021,
            raw="김호연, 이종휘, “온도감응성 하이드로젤 기반 증발 결정화 시스템”, 폴리머, 45권, 6호, pp. 897–903, 2021.",
        )

        result = check_reference(entry, FakeCrossref(candidates=[candidate]))

        self.assertEqual(result.verdict, "PASS")
        self.assertEqual(result.resolved_doi, candidate.doi)

    def test_resolved_year_difference_names_both_years(self):
        entry = _entry(title="Self-healing ionic gels", first_author="Müller", year=2020)

        result = check_reference(entry, FakeCrossref(candidates=[GELS]))

        self.assertIn("the year differs (reference: 2020; CrossRef: 2019)", result.reason)

    def test_title_match_resolves_and_passes(self):
        entry = _entry(title="Self-healing ionic gels", first_author="Müller", year=2019, journal="Soft Matter")
        client = FakeCrossref(candidates=[OTHER, GELS])

        result = check_reference(entry, client)

        self.assertEqual(result.verdict, "PASS")
        self.assertEqual(result.status, "RESOLVED")
        self.assertEqual(result.error_code, "REFERENCE_RESOLVED")
        self.assertEqual(result.resolved_doi, "10.1039/gels")
        self.assertEqual(client.queries, [("Self-healing ionic gels Müller 2019 Soft Matter", 5)])

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
        self.assertNotIn("filter", query)
        self.assertIn("ref-verify/", request.get_header("User-agent"))
        self.assertEqual([record.doi for record in records], ["10.1039/gels", "10.1000/other"])
        self.assertEqual(records[0].year, 2019)


class SearchPacingTests(unittest.TestCase):
    def test_uncached_searches_are_spaced_and_cached_ones_are_not(self):
        body = json.dumps({"message": {"items": []}})

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return body.encode("utf-8")

        clock = [100.0]
        sleeps = []

        def sleep(seconds):
            sleeps.append(round(seconds, 2))
            clock[0] += seconds

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=False):
            os.environ.pop("REF_VERIFY_MAILTO", None)
            client = CrossrefClient(timeout=1.0, cache=ResponseCache(Path(tmp), ttl_seconds=100))
            with patch("ref_verify.crossref._last_search_started", [float("-inf")]), patch(
                "ref_verify.crossref.time.monotonic", side_effect=lambda: clock[0]
            ), patch("ref_verify.crossref.time.sleep", side_effect=sleep), patch(
                "ref_verify.http.urlopen", side_effect=lambda *args, **kwargs: Response()
            ):
                client.search_bibliographic("first")
                clock[0] += 0.25
                client.search_bibliographic("second")
                client.search_bibliographic("first")

        self.assertEqual(sleeps, [0.75])


class StructuredSearchTests(unittest.TestCase):
    def test_author_and_year_range_become_crossref_parameters(self):
        body = json.dumps({"message": {"items": []}})

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return body.encode("utf-8")

        with patch("ref_verify.http.urlopen", return_value=Response()) as urlopen, patch(
            "ref_verify.crossref._pace_search"
        ):
            CrossrefClient(timeout=1.0).search_bibliographic(
                "Astron. J. 116, 1009", rows=5, author="Riess", year_range=(1997, 1998)
            )

        query = parse_qs(urlparse(urlopen.call_args.args[0].full_url).query)
        self.assertEqual(query["query.author"], ["Riess"])
        self.assertEqual(query["filter"], ["from-pub-date:1997,until-pub-date:1998"])
        self.assertEqual(query["query.bibliographic"], ["Astron. J. 116, 1009"])


class RegistrationAgencyTests(unittest.TestCase):
    def test_reads_agency_from_doi_org(self):
        body = json.dumps([{"DOI": "10.48550/arXiv.1706.03762", "RA": "DataCite"}])

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return body.encode("utf-8")

        with patch("ref_verify.http.urlopen", return_value=Response()) as urlopen:
            agency = CrossrefClient(timeout=1.0).registration_agency("10.48550/arXiv.1706.03762")

        self.assertEqual(agency, "DataCite")
        self.assertEqual(urlopen.call_args.args[0].full_url, "https://doi.org/ra/10.48550/arxiv.1706.03762")


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
        text = render_reference_text(self.results, width=100)

        self.assertTrue(text.startswith("4 references: 2 PASS, 0 WARN, 1 REJECT, 1 UNVERIFIED\n"))
        self.assertIn("VERDICT", text)
        self.assertIn("10.1039/gels (resolved)", text)
        for label, key in (("PASS", "a"), ("PASS", "b"), ("UNVERIFIED", "c"), ("REJECT", "d")):
            self.assertRegex(text, rf"\n{label} +{key} ")
        self.assertIn("does not mean the reference is wrong", " ".join(text.split()))

    def test_text_output_fits_a_100_column_terminal(self):
        long_key = _entry(index=5, key="kornbluhHighfieldElectrostrictionElastomericPolymerDielectrics1999",
                          doi="10.9999/dead")
        pasted = _entry(index=6, key=None, raw="Keplinger, C., & Suo, Z. (2016). Self-healing ionic conductors. Nat. Mater.")
        results = self.results + [check_reference(long_key, FakeCrossref()), check_reference(pasted, FakeCrossref())]

        text = render_reference_text(results, width=100)

        self.assertLessEqual(max(len(line) for line in text.splitlines()), 100)
        # A pasted list has no keys, so the row shows the start of the reference itself.
        self.assertIn("6. Keplinger, C., & Suo, Z. (2016).", text)
        # PASS rows carry no reason line; others are followed by an indented reason.
        self.assertNotIn("Provided citation metadata matches", text)
        self.assertIn("\n            No matching CrossRef record was found", text)

    def test_failed_rows_tell_the_reader_to_rerun(self):
        failed = check_reference(_entry(doi=PELRINE_DOI), FakeCrossref(errors={PELRINE_DOI: RuntimeError("boom")}))

        text = render_reference_text([failed], width=100)

        self.assertTrue(text.startswith("1 reference: 0 PASS"))
        self.assertIn("(1 could not be checked; run the same command again)", text)


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
        self.assertIn("2 references:", output)

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
