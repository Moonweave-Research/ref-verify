from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from ref_verify.doi_check import normalize_doi

ReferenceFormat = Literal["bib", "ris", "txt"]

_SUFFIX_FORMATS: dict[str, ReferenceFormat] = {
    ".bib": "bib",
    ".bibtex": "bib",
    ".ris": "ris",
    ".txt": "txt",
    ".md": "txt",
    ".markdown": "txt",
}
# Old Wiley DOIs are SICIs with an angle-bracketed part ("...40:11<2004::aid-anie2004>3.0.co;2-5");
# a bracketed run without spaces stays in the DOI, while a DOI wrapped as <...> ends at ">".
_DOI_PATTERN = re.compile(r"10\.\d{4,9}/(?:[^\s\"<>{}]|<[^\s\"<>{}]*>)+", re.IGNORECASE)
DOI_PATTERN = _DOI_PATTERN
_YEAR_PATTERN = re.compile(r"\b(?:1[89]|20)\d{2}\b")
_PARENTHESISED_YEAR_PATTERN = re.compile(r"\(((?:1[89]|20)\d{2})[a-z]?\)")
# A publication year is followed by punctuation or the end ("2020;395", "2020.", "2020)"),
# unlike a year inside a title ("infected with 2019 novel coronavirus").
_CITATION_YEAR_PATTERN = re.compile(r"\b((?:1[89]|20)\d{2})[a-z]?(?=\s*(?:[;.,:)\]]|$))")


class ReferenceInputError(ValueError):
    pass


@dataclass(frozen=True)
class ReferenceEntry:
    index: int
    key: str | None
    raw: str
    title: str | None
    first_author: str | None
    year: int | None
    doi: str | None
    journal: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_DOCUMENT_SUFFIXES = {".doc", ".docx", ".hwp", ".hwpx", ".odt", ".pages", ".pdf", ".rtf"}


def detect_reference_format(path: Path, explicit_format: str | None) -> ReferenceFormat:
    if explicit_format in ("bib", "ris", "txt"):
        return explicit_format
    if explicit_format is not None:
        raise ReferenceInputError(f"Unsupported reference format: {explicit_format}")
    if path.is_dir():
        raise ReferenceInputError(f"{path} is a folder; give the path of a .bib, .ris, .txt, or .md file")
    if path.suffix.lower() in _DOCUMENT_SUFFIXES:
        raise ReferenceInputError(
            f"{path.suffix} files cannot be read directly. Copy the reference list into a plain-text "
            ".txt file, or export .bib or .ris from Zotero, EndNote, or Mendeley, and check that file"
        )
    detected = _SUFFIX_FORMATS.get(path.suffix.lower())
    if detected is None:
        raise ReferenceInputError("Unsupported reference format; use .bib, .ris, .txt, .md, or --format")
    return detected


def parse_reference_file(path: Path, explicit_format: str | None) -> list[ReferenceEntry]:
    reference_format = detect_reference_format(path, explicit_format)
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        raise ReferenceInputError(
            f"File not found: {path}. Check the name, or drag the file into the terminal to paste its full path"
        ) from None
    except OSError as exc:
        raise ReferenceInputError(f"Could not read input file: {exc}") from exc
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Notepad on Korean Windows used to save plain text as CP949 ("ANSI").
        try:
            text = data.decode("cp949")
        except UnicodeDecodeError:
            raise ReferenceInputError(
                f"{path.name} is not plain text in UTF-8. If it is a Word or PDF file, copy the "
                "reference list into a .txt file; otherwise save it again with UTF-8 encoding"
            ) from None
    if reference_format == "bib":
        entries = parse_bibtex(text)
    elif reference_format == "ris":
        entries = parse_ris(text)
    else:
        entries = parse_plain_text(text)
    if not entries:
        raise ReferenceInputError(
            "Input file does not contain any references; put one reference per line, per "
            "paragraph, or per [1]/1. item, or use a .bib or .ris export"
        )
    return entries


# --- BibTeX ---------------------------------------------------------------

_BIB_ENTRY_START = re.compile(r"@\s*([A-Za-z]+)\s*([{(])")
_BIB_FIELD_NAME = re.compile(r"\s*([A-Za-z][\w:.+-]*)\s*=\s*")
_BIB_SKIPPED_TYPES = {"comment", "string", "preamble"}
_LATEX_ACCENTS = {
    '"': "\u0308",
    "'": "\u0301",
    "`": "\u0300",
    "^": "\u0302",
    "~": "\u0303",
    "=": "\u0304",
    ".": "\u0307",
    "u": "\u0306",
    "v": "\u030c",
    "H": "\u030b",
    "c": "\u0327",
    "k": "\u0328",
}
_LATEX_LETTERS = {
    "ss": "ß",
    "aa": "å",
    "AA": "Å",
    "ae": "æ",
    "AE": "Æ",
    "oe": "œ",
    "OE": "Œ",
    "o": "ø",
    "O": "Ø",
    "l": "ł",
    "L": "Ł",
    "i": "i",
    "j": "j",
}


_LATEX_GREEK = {
    name: char
    for names, chars in (
        (
            "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi pi rho sigma tau "
            "upsilon phi chi psi omega",
            "αβγδεζηθικλμνξπρστυφχψω",
        ),
        ("varepsilon vartheta varpi varrho varsigma varphi", "εθπρςφ"),
        ("Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega", "ΓΔΘΛΞΠΣΥΦΨΩ"),
    )
    for name, char in zip(names.split(), chars)
}


def parse_bibtex(text: str) -> list[ReferenceEntry]:
    entries: list[ReferenceEntry] = []
    position = 0
    while match := _BIB_ENTRY_START.search(text, position):
        body_start = match.end()
        body_end = _bib_closing_index(text, body_start, match.group(2))
        if body_end is None:
            line = text.count("\n", 0, match.start()) + 1
            raise ReferenceInputError(f"Unbalanced braces in the BibTeX entry starting on line {line}")
        position = body_end + 1
        if match.group(1).lower() in _BIB_SKIPPED_TYPES:
            continue
        key, fields = _bib_fields(text[body_start:body_end])
        doi_source = fields.get("doi") or fields.get("url") or ""
        entries.append(
            ReferenceEntry(
                index=len(entries) + 1,
                key=key or None,
                raw=text[match.start() : body_end + 1],
                title=_first_clean(fields, ("title",)),
                # Edited books carry `editor` instead of `author`; citations name the editors.
                first_author=_bib_first_author(fields.get("author") or fields.get("editor")),
                year=_first_year(fields.get("year") or fields.get("date") or ""),
                doi=_find_doi(doi_source.replace("\\_", "_")),
                journal=_first_clean(fields, ("journal", "journaltitle", "booktitle")),
            )
        )
    return entries


def _bib_closing_index(text: str, start: int, opener: str) -> int | None:
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            if depth == 0 and opener == "{":
                return index
            depth -= 1
            if depth < 0:
                return None
        elif char == ")" and opener == "(" and depth == 0:
            return index
    return None


def _bib_fields(body: str) -> tuple[str, dict[str, str]]:
    key, _, rest = body.partition(",")
    fields: dict[str, str] = {}
    position = 0
    while name_match := _BIB_FIELD_NAME.match(rest, position):
        position = name_match.end()
        parts: list[str] = []
        while (value := _bib_value(rest, position)) is not None:
            part, position = value
            parts.append(part)
            concatenation = re.compile(r"\s*#\s*").match(rest, position)
            if not concatenation:
                break
            position = concatenation.end()
        fields[name_match.group(1).lower()] = "".join(parts)
        separator = re.compile(r"\s*,").match(rest, position)
        if not separator:
            break
        position = separator.end()
    return key.strip(), fields


def _bib_value(text: str, position: int) -> tuple[str, int] | None:
    while position < len(text) and text[position].isspace():
        position += 1
    if position >= len(text):
        return None
    if text[position] == "{":
        end = _bib_closing_index(text, position + 1, "{")
        if end is None:
            return None
        return text[position + 1 : end], end + 1
    if text[position] == '"':
        depth = 0
        for index in range(position + 1, len(text)):
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            elif char == '"' and depth == 0:
                return text[position + 1 : index], index + 1
        return None
    bare = re.compile(r"[^\s,#}]+").match(text, position)
    if not bare:
        return None
    return bare.group(0), bare.end()


def _bib_first_author(value: str | None) -> str | None:
    if not value:
        return None
    first = _split_top_level_and(value)[0].strip()
    if first.startswith("{") and _bib_closing_index(first, 1, "{") == len(first) - 1:
        # A fully braced name is a corporate author; do not split it into given/family.
        return _clean_latex(first) or None
    return _family_name(_clean_latex(first))


def _split_top_level_and(value: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = 0
    index = 0
    while index < len(value):
        char = value[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif depth == 0:
            separator = re.compile(r"\s+and\s+", re.IGNORECASE).match(value, index)
            if separator:
                parts.append(value[start:index])
                start = index = separator.end()
                continue
        index += 1
    parts.append(value[start:])
    return parts


def _clean_latex(value: str) -> str:
    text = re.sub(
        r"\\(ss|aa|AA|ae|AE|oe|OE|o|O|l|L|i|j)(?![A-Za-z])\s*",
        lambda match: _LATEX_LETTERS[match.group(1)],
        value,
    )
    text = re.sub(
        r"\\([\"'`^~=.])\s*\{?\s*([A-Za-z])\s*\}?",
        lambda match: unicodedata.normalize("NFC", match.group(2) + _LATEX_ACCENTS[match.group(1)]),
        text,
    )
    text = re.sub(
        r"\\([uvHck])(?:\s+|\s*\{\s*)([A-Za-z])\s*\}?",
        lambda match: unicodedata.normalize("NFC", match.group(2) + _LATEX_ACCENTS[match.group(1)]),
        text,
    )
    text = re.sub(
        r"\\(?:text)?(" + "|".join(_LATEX_GREEK) + r")(?![A-Za-z])\s*",
        lambda match: _LATEX_GREEK[match.group(1)],
        text,
    )
    # Math delimiters carry no text ("amyloid-$\beta$" is "amyloid-β"); "\$" stays a dollar sign.
    text = re.sub(r"(?<!\\)\$", "", text)
    text = re.sub(r"\\([%&$#_{}])", r"\1", text)
    text = re.sub(r"\\[,;:! ]", " ", text)
    text = re.sub(r"\\[A-Za-z]+\*?\s*", "", text)
    text = text.replace("{", "").replace("}", "").replace("~", " ")
    return re.sub(r"\s+", " ", text).strip()


def _first_clean(fields: dict[str, str], names: tuple[str, ...]) -> str | None:
    for name in names:
        if fields.get(name):
            return _clean_latex(fields[name]) or None
    return None


# --- RIS ------------------------------------------------------------------

_RIS_LINE = re.compile(r"^([A-Z][A-Z0-9])\s{1,2}-\s?(.*)$")


def parse_ris(text: str) -> list[ReferenceEntry]:
    entries: list[ReferenceEntry] = []
    tags: dict[str, list[str]] = {}
    lines: list[str] = []

    def flush() -> None:
        if tags:
            entries.append(_ris_entry(len(entries) + 1, tags, "\n".join(lines)))
        tags.clear()
        lines.clear()

    for line in text.splitlines():
        match = _RIS_LINE.match(line.rstrip())
        if not match:
            continue
        tag, value = match.group(1), match.group(2).strip()
        if tag == "TY":
            flush()
        lines.append(line.rstrip())
        if tag == "ER":
            flush()
            continue
        if value:
            tags.setdefault(tag, []).append(value)
    flush()
    return entries


def _ris_entry(index: int, tags: dict[str, list[str]], raw: str) -> ReferenceEntry:
    def first(*names: str) -> str | None:
        for name in names:
            if tags.get(name):
                return tags[name][0]
        return None

    author = first("AU", "A1")
    return ReferenceEntry(
        index=index,
        key=first("ID"),
        raw=raw,
        title=first("TI", "T1"),
        first_author=_family_name(author) if author else None,
        year=_first_year(first("PY", "Y1", "DA") or ""),
        doi=_find_doi(first("DO", "UR") or ""),
        journal=first("JO", "JF", "T2", "JA"),
    )


# --- Plain text / Markdown --------------------------------------------------

_LIST_MARKER = re.compile(r"^\s*(?:\[(\d+)\]|(\d+)[.)]|[-*•])\s+")


def parse_plain_text(text: str) -> list[ReferenceEntry]:
    lines = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
    blocks: list[list[str]] = [[]]
    for line in lines:
        if line.strip():
            blocks[-1].append(line.strip())
        elif blocks[-1]:
            blocks.append([])
    blocks = [block for block in blocks if block]

    items: list[list[str]] = []
    for block in blocks:
        if any(_LIST_MARKER.match(line) for line in block[1:]):
            # Several numbered references in one block: each marker starts a new item and
            # unmarked lines continue the previous one.
            for line in block:
                if _LIST_MARKER.match(line) or not items:
                    items.append([line])
                else:
                    items[-1].append(line)
        elif len(blocks) == 1:
            items.extend([line] for line in block)
        else:
            items.append(block)

    entries: list[ReferenceEntry] = []
    for item in items:
        joined = " ".join(item)
        marker = _LIST_MARKER.match(joined)
        key = (marker.group(1) or marker.group(2)) if marker else None
        reference = joined[marker.end() :] if marker else joined
        doi_match = _DOI_PATTERN.search(reference)
        # A heading such as "References" is not a reference; real ones carry a DOI or
        # at least a few words of bibliographic text.
        if not doi_match and len(reference.split()) < 3:
            continue
        without_doi = reference.replace(doi_match.group(0), " ") if doi_match else reference
        entries.append(
            ReferenceEntry(
                index=len(entries) + 1,
                key=key,
                raw=reference,
                title=None,
                first_author=None,
                year=_plain_text_year(without_doi),
                doi=normalize_doi(doi_match.group(0)) if doi_match else None,
                journal=None,
            )
        )
    return entries


def _plain_text_year(text: str) -> int | None:
    parenthesised = _PARENTHESISED_YEAR_PATTERN.search(text)
    if parenthesised:
        return int(parenthesised.group(1))
    cited = _CITATION_YEAR_PATTERN.search(text)
    if cited:
        return int(cited.group(1))
    return _first_year(text)


# --- Shared -----------------------------------------------------------------


def _family_name(name: str) -> str | None:
    name = name.strip()
    if not name:
        return None
    if "," in name:
        return name.split(",", 1)[0].strip() or None
    return name.split()[-1]


def _first_year(value: str) -> int | None:
    match = _YEAR_PATTERN.search(value)
    return int(match.group(0)) if match else None


def _find_doi(value: str) -> str | None:
    match = _DOI_PATTERN.search(value)
    return normalize_doi(match.group(0)) if match else None
