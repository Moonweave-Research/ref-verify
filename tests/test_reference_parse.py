import tempfile
import unittest
from pathlib import Path

from ref_verify.reference_parse import (
    ReferenceInputError,
    detect_reference_format,
    parse_bibtex,
    parse_plain_text,
    parse_reference_file,
    parse_ris,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "references"


class BibtexParseTests(unittest.TestCase):
    def setUp(self):
        self.entries = parse_bibtex((FIXTURES / "refs.bib").read_text(encoding="utf-8"))

    def test_skips_comment_and_string_blocks(self):
        self.assertEqual([entry.key for entry in self.entries], ["pelrine2000", "mueller2019", "smith2021"])
        self.assertEqual([entry.index for entry in self.entries], [1, 2, 3])

    def test_entry_with_doi(self):
        entry = self.entries[0]

        self.assertEqual(
            entry.title,
            "High-Speed Electrically Actuated Elastomers with Strain Greater Than 100%",
        )
        self.assertEqual(entry.first_author, "Pelrine")
        self.assertEqual(entry.year, 2000)
        self.assertEqual(entry.doi, "10.1126/science.287.5454.836")
        self.assertEqual(entry.journal, "Science")
        self.assertTrue(entry.raw.startswith("@article{pelrine2000,"))

    def test_decodes_accents_and_strips_latex_markup(self):
        entry = self.entries[1]

        self.assertEqual(entry.title, "Self-healing ionic gels")
        self.assertEqual(entry.first_author, "Müller")
        self.assertEqual(entry.year, 2019)
        self.assertIsNone(entry.doi)

    def test_nested_braces_and_given_family_author(self):
        entry = self.entries[2]

        self.assertEqual(entry.title, "Nested Braces Inside Titles")
        self.assertEqual(entry.first_author, "Smith")
        self.assertEqual(entry.journal, "Proc. Testing")

    def test_braced_group_author_is_kept_whole(self):
        entries = parse_bibtex("@article{g, author = {{WHO Working Group} and Lee, Jane}, title = {T}}")

        self.assertEqual(entries[0].first_author, "WHO Working Group")

    def test_parenthesised_entry_and_concatenated_value(self):
        entries = parse_bibtex('@article(p, title = "Part one " # {part two}, year = "1999")')

        self.assertEqual(entries[0].title, "Part one part two")
        self.assertEqual(entries[0].year, 1999)

    def test_unbalanced_entry_is_an_input_error(self):
        with self.assertRaises(ReferenceInputError) as context:
            parse_bibtex((FIXTURES / "broken.bib").read_text(encoding="utf-8"))

        self.assertIn("line 6", str(context.exception))


class RisParseTests(unittest.TestCase):
    def test_parses_primary_and_alias_tags(self):
        entries = parse_ris((FIXTURES / "refs.ris").read_text(encoding="utf-8"))

        self.assertEqual(len(entries), 2)
        first, second = entries
        self.assertEqual(first.title, "Dielectric elastomer actuators")
        self.assertEqual(first.first_author, "Pelrine")
        self.assertEqual(first.year, 2000)
        self.assertEqual(first.doi, "10.1126/science.287.5454.836")
        self.assertEqual(first.journal, "Science")
        self.assertEqual(second.key, "mueller2019")
        self.assertEqual(second.title, "Self-healing ionic gels")
        self.assertEqual(second.first_author, "Müller")
        self.assertEqual(second.year, 2019)
        self.assertIsNone(second.doi)

    def test_entry_without_end_tag_is_kept(self):
        entries = parse_ris("TY  - JOUR\nTI  - Unterminated\nPY  - 2001\n")

        self.assertEqual(entries[0].title, "Unterminated")


class PlainTextParseTests(unittest.TestCase):
    def test_numbered_list_after_heading(self):
        entries = parse_plain_text((FIXTURES / "refs.txt").read_text(encoding="utf-8"))

        self.assertEqual(len(entries), 3)
        first, second, third = entries
        self.assertEqual(first.key, "1")
        self.assertTrue(first.raw.startswith("Pelrine R, Kornbluh R"))
        self.assertEqual(first.doi, "10.1126/science.287.5454.836")
        self.assertEqual(first.year, 2000)
        self.assertIsNone(first.title)
        self.assertIsNone(first.first_author)
        self.assertEqual(second.doi, "10.9999/dead.doi")
        self.assertEqual(second.year, 2021)
        self.assertEqual(third.key, "3")
        self.assertIsNone(third.doi)
        self.assertEqual(third.year, 2019)

    def test_blank_line_separated_paragraphs(self):
        text = (
            "Lee J, Park K. Long title that\nwraps onto a second line. Nature. 2018.\n\n"
            "Kim S. Another paper. Science. 2020.\n"
        )

        entries = parse_plain_text(text)

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].raw, "Lee J, Park K. Long title that wraps onto a second line. Nature. 2018.")

    def test_one_reference_per_line_with_markers(self):
        text = "1. Alpha A. First paper title. 2001.\n2) Beta B. Second paper title. 2002.\n- Gamma C. Third paper title. 2003.\n"

        entries = parse_plain_text(text)

        self.assertEqual([entry.key for entry in entries], ["1", "2", None])
        self.assertEqual(entries[2].raw, "Gamma C. Third paper title. 2003.")
        self.assertEqual([entry.year for entry in entries], [2001, 2002, 2003])

    def test_year_ignores_digits_inside_doi(self):
        entries = parse_plain_text("Pelrine R. Elastomers. doi:10.1126/science.1999.5454.836 (2000)\n")

        self.assertEqual(entries[0].year, 2000)


class ReferenceFileTests(unittest.TestCase):
    def test_detects_format_from_suffix(self):
        self.assertEqual(detect_reference_format(Path("a.bib"), None), "bib")
        self.assertEqual(detect_reference_format(Path("a.RIS"), None), "ris")
        self.assertEqual(detect_reference_format(Path("a.txt"), None), "txt")
        self.assertEqual(detect_reference_format(Path("a.md"), None), "txt")
        self.assertEqual(detect_reference_format(Path("a.docx"), "bib"), "bib")
        with self.assertRaises(ReferenceInputError):
            detect_reference_format(Path("a.docx"), None)

    def test_empty_file_is_an_input_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.bib"
            path.write_text("% nothing here\n", encoding="utf-8")
            with self.assertRaises(ReferenceInputError):
                parse_reference_file(path, None)

    def test_missing_file_is_an_input_error(self):
        with self.assertRaisesRegex(ReferenceInputError, "File not found: .*missing.bib. Check the name"):
            parse_reference_file(FIXTURES / "missing.bib", None)

    def test_word_file_and_folder_get_a_next_step(self):
        with self.assertRaisesRegex(ReferenceInputError, r"\.docx files cannot be read directly. Copy the reference list"):
            detect_reference_format(Path("thesis.docx"), None)
        with self.assertRaisesRegex(ReferenceInputError, "is a folder"):
            detect_reference_format(FIXTURES, None)

    def test_cp949_text_from_korean_windows_is_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "refs.txt"
            path.write_bytes("[1] 윤혜리, 이종휘, “리포익산을 함유한 PNIPAM 하이드로젤의 제조”, 폴리머, 2012.".encode("cp949"))

            entries = parse_reference_file(path, None)

        self.assertEqual(len(entries), 1)
        self.assertIn("리포익산", entries[0].raw)

    def test_binary_file_named_txt_is_an_input_error_not_a_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "refs.txt"
            path.write_bytes(b"PK\x03\x04\x14\x00\x06\x00\x80\xff\xfe\xfd binary")

            with self.assertRaisesRegex(ReferenceInputError, "not plain text in UTF-8"):
                parse_reference_file(path, None)


if __name__ == "__main__":
    unittest.main()
