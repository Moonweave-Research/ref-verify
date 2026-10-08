import ast
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = REPO_ROOT / "src" / "ref_verify"
REASONS_JS = REPO_ROOT / "web" / "reasons.js"

# Top-level names in reference_resolve.py that write terminal output, not reasons.
NOT_REASONS = {"TEXT_LEGEND", "render_reference_text"}
# Reason builders that check-bib uses from other modules.
OTHER_REASON_FUNCTIONS = {"doi_check.py": {"verify_doi_metadata"}, "crossref.py": {"not_in_crossref_reason"}}
# The list joiner in "journal, year, and first author", which reasons.js splits in code.
JOINERS = {", and "}


def _phrases(node: ast.AST) -> set[str]:
    # String constants, including the literal parts of f-strings, that read as English.
    return {
        sub.value
        for sub in ast.walk(node)
        if isinstance(sub, ast.Constant)
        and isinstance(sub.value, str)
        and " " in sub.value.strip()
        and re.search(r"[A-Za-z]{3,}", sub.value)
    }


def engine_reason_phrases() -> set[str]:
    phrases = set()
    for node in ast.parse((PACKAGE / "reference_resolve.py").read_text(encoding="utf-8")).body:
        names = {getattr(node, "name", None)}
        if isinstance(node, ast.Assign):
            names |= {target.id for target in node.targets if isinstance(target, ast.Name)}
        if not names & NOT_REASONS:
            phrases |= _phrases(node)
    for filename, functions in OTHER_REASON_FUNCTIONS.items():
        for node in ast.parse((PACKAGE / filename).read_text(encoding="utf-8")).body:
            if isinstance(node, ast.FunctionDef) and node.name in functions:
                phrases |= _phrases(node)
    return phrases - JOINERS


def korean_templates() -> list[tuple[str, str]]:
    source = REASONS_JS.read_text(encoding="utf-8")
    pairs = re.findall(r'en:\s*("(?:[^"\\]|\\.)*"),\s*ko:\s*("(?:[^"\\]|\\.)*")', source)
    templates = [(json.loads(en), json.loads(ko)) for en, ko in pairs]
    for block in ("FIELDS", "VALUES"):
        body = re.search(rf"const {block} = \{{(.*?)\}};", source, re.S).group(1)
        templates += [
            (quoted or bare, ko) for quoted, bare, ko in re.findall(r'(?:"([^"]+)"|(\w+)):\s*"([^"]+)"', body)
        ]
    return templates


class WebReasonTranslationTests(unittest.TestCase):
    def test_every_engine_reason_phrase_has_a_korean_template(self):
        english = [en for en, _ in korean_templates()]
        phrases = engine_reason_phrases()
        self.assertGreater(len(phrases), 20)
        for phrase in sorted(phrases):
            with self.subTest(phrase=phrase):
                self.assertTrue(
                    any(phrase in template for template in english),
                    f"Add a Korean template for this check-bib reason to web/reasons.js: {phrase!r}",
                )

    def test_korean_templates_keep_every_value_placeholder(self):
        for en, ko in korean_templates():
            with self.subTest(en=en):
                expected = sorted(name for name in re.findall(r"\{(\w+)(?::\w+)?\}", en))
                self.assertEqual(sorted(re.findall(r"\{(\w+)\}", ko)), expected)
                self.assertRegex(ko, r"[가-힣]")


if __name__ == "__main__":
    unittest.main()
