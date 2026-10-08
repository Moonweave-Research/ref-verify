from __future__ import annotations

import re
import unicodedata
from urllib.parse import unquote

from ref_verify.models import CitationInput, MetadataCheckResult, PaperRecord

_GREEK_LETTER_NAMES = {
    "\u03b1": "alpha",
    "\u03b2": "beta",
    "\u03b3": "gamma",
    "\u03b4": "delta",
    "\u03b5": "epsilon",
    "\u03b6": "zeta",
    "\u03b7": "eta",
    "\u03b8": "theta",
    "\u03b9": "iota",
    "\u03ba": "kappa",
    "\u03bb": "lambda",
    "\u03bc": "mu",
    "\u03bd": "nu",
    "\u03be": "xi",
    "\u03bf": "omicron",
    "\u03c0": "pi",
    "\u03c1": "rho",
    "\u03c2": "sigma",
    "\u03c3": "sigma",
    "\u03c4": "tau",
    "\u03c5": "upsilon",
    "\u03c6": "phi",
    "\u03c7": "chi",
    "\u03c8": "psi",
    "\u03c9": "omega",
}

_GROUP_AUTHOR_TERMS = {
    "association",
    "collaboration",
    "committee",
    "consortium",
    "group",
    "network",
    "organisation",
    "organization",
    "society",
    "team",
    "working",
}


_HANGUL_NAME = re.compile(r"\s*([\uac00-\ud7a3]{2,5})")
_HANGUL_SURNAMES: dict[str, set[str]] = {
    surname: set(romanizations.split())
    for surname, romanizations in {
        "남궁": "namgung namkung", "황보": "hwangbo", "제갈": "jegal", "선우": "sunwoo seonwoo",
        "독고": "dokgo", "사공": "sagong", "서문": "seomun",
        "김": "kim gim", "이": "lee yi rhee i ri rhie li", "박": "park bak pak",
        "최": "choi choe chey", "정": "jung jeong chung joung jeung", "강": "kang gang",
        "조": "cho jo joe", "윤": "yoon yun youn", "장": "jang chang", "임": "lim im rim yim",
        "한": "han", "오": "oh o", "서": "seo suh so", "신": "shin sin", "권": "kwon gwon kweon",
        "황": "hwang", "안": "ahn an", "송": "song", "류": "ryu yoo yu you ryoo rhyu lyu",
        "유": "yoo yu you ryu", "전": "jeon jun chun jeun chon", "홍": "hong", "고": "ko go koh",
        "문": "moon mun", "양": "yang ryang", "손": "son sohn", "배": "bae bai pae",
        "백": "baek paek paik back baik", "허": "heo hur huh her", "남": "nam", "심": "shim sim",
        "노": "noh no roh ro", "하": "ha", "곽": "kwak gwak", "성": "sung seong", "차": "cha",
        "주": "joo ju chu choo", "우": "woo wu u", "구": "koo ku gu goo", "민": "min",
        "나": "na ra", "진": "jin chin", "지": "ji chi", "엄": "eom um uhm eum", "채": "chae chai",
        "원": "won weon", "천": "cheon chun chon", "방": "bang pang", "공": "kong gong",
        "현": "hyun hyeon", "함": "ham", "변": "byun byeon pyun", "염": "yeom yum youm",
        "여": "yeo yoo yuh", "추": "choo chu", "도": "do doh to", "소": "so soh",
        "석": "seok suk sok", "선": "sun seon", "설": "seol sul", "마": "ma", "길": "gil kil",
        "연": "yeon yun youn", "위": "wi wee", "표": "pyo", "명": "myung myeong", "기": "ki gi",
        "반": "ban pan", "왕": "wang", "금": "keum kum geum", "옥": "ok ock", "육": "yuk yook",
        "인": "in", "맹": "maeng", "제": "je jae", "모": "mo", "탁": "tak", "국": "kook kuk guk",
        "어": "eo uh", "은": "eun", "편": "pyeon pyun", "용": "yong", "예": "ye yea",
        "경": "kyung gyeong kyeong", "봉": "bong", "사": "sa", "부": "boo bu pu", "가": "ka ga",
        "복": "bok", "태": "tae", "목": "mok", "형": "hyung hyeong", "피": "pi pee", "두": "doo du",
        "감": "kam gam", "음": "eum", "빈": "bin", "동": "dong", "온": "on", "호": "ho",
        "범": "beom bum", "좌": "jwa", "팽": "paeng", "승": "seung", "간": "kan gan", "상": "sang",
        "갈": "kal gal", "라": "ra la", "견": "kyun gyeon", "당": "dang", "계": "kye gye",
    }.items()
}


def verify_doi_metadata(
    provided: CitationInput,
    fetched: PaperRecord,
) -> MetadataCheckResult:
    mismatches: list[str] = []

    if provided.doi and not doi_matches(provided.doi, fetched.doi):
        mismatches.append("doi")

    if not _has_comparison_metadata(provided):
        mismatches.append("metadata")

    if provided.title and not any(_titles_match(provided.title, title) for title in record_titles(fetched)):
        mismatches.append("title")

    if provided.first_author and not _author_matches(
        provided.first_author,
        fetched.authors[0] if fetched.authors else None,
    ):
        mismatches.append("first_author")

    if provided.year is not None and provided.year not in record_years(fetched):
        mismatches.append("year")

    if fetched.retraction_doi:
        mismatches.append("retracted")

    if not mismatches:
        verdict = "PASS"
        reason = "Provided citation metadata matches the fetched CrossRef record."
    elif "retracted" in mismatches:
        verdict = "REJECT"
        reason = (
            "CrossRef records this paper as retracted "
            f"(notice DOI {fetched.retraction_doi}); do not use it as a source."
        )
    elif any(field in mismatches for field in ("doi", "title", "first_author")):
        verdict = "REJECT"
        reason = "DOI resolves to a materially different paper than provided."
    elif "metadata" in mismatches:
        verdict = "WARN"
        reason = "Insufficient citation metadata was provided to verify the fetched CrossRef record."
    else:
        verdict = "WARN"
        reason = "DOI resolves, but minor metadata differs from the provided citation."

    return MetadataCheckResult(
        verdict=verdict,
        mismatches=mismatches,
        reason=reason,
        provided=provided,
        fetched=fetched,
    )


def _has_comparison_metadata(provided: CitationInput) -> bool:
    return bool(provided.title and provided.first_author)


def doi_matches(provided: str, fetched: str) -> bool:
    return normalize_doi(provided) == normalize_doi(fetched)


def normalize_doi(value: str) -> str:
    normalized = value.strip().casefold()
    normalized = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", normalized)
    normalized = re.sub(r"^doi:\s*", "", normalized)
    normalized = unquote(normalized)
    return _strip_trailing_doi_punctuation(normalized)


def _strip_trailing_doi_punctuation(value: str) -> str:
    stripped = value.strip()
    while stripped:
        without_sentence_punctuation = stripped.rstrip(".,;:")
        if without_sentence_punctuation != stripped:
            stripped = without_sentence_punctuation.rstrip()
            continue
        if stripped.endswith(")") and stripped.count(")") > stripped.count("("):
            stripped = stripped[:-1].rstrip()
            continue
        return stripped
    return stripped


def _titles_match(provided: str, fetched: str) -> bool:
    provided = _strip_retraction_prefix(provided)
    fetched = _strip_retraction_prefix(fetched)
    if _same_title(provided, fetched):
        return True
    # A citation or a registry record may drop a subtitle or an edition note ("Main title:
    # Subtitle", "Title - Part two", "Title, Second Edition").
    return any(_same_title(provided, prefix) for prefix in _title_prefixes(fetched)) or any(
        _same_title(prefix, fetched) for prefix in _title_prefixes(provided)
    )


def _same_title(provided: str, fetched: str) -> bool:
    if _numbers(provided) != _numbers(fetched):
        return False
    # Joined tokens so "Ti3AlC2" equals CrossRef's subscripted "Ti <sub>3</sub> AlC <sub>2</sub>".
    return "".join(_title_tokens(provided)) == "".join(_title_tokens(fetched))


_TITLE_SEPARATOR = re.compile(r"\s*(?::|\s[-\u2013\u2014]|[.?!,](?=\s))\s")


def _title_prefixes(title: str) -> list[str]:
    # A one- or two-word lead-in ("Review: ...", "CP2K: ...") is too generic to stand for the paper.
    prefixes = [title[: match.start()] for match in _TITLE_SEPARATOR.finditer(title)]
    return [prefix for prefix in prefixes if len(_title_tokens(prefix)) >= 3]


def _strip_retraction_prefix(title: str) -> str:
    # Publishers prepend "RETRACTED:" to the stored title, and a citation may or may not
    # carry it; the retraction itself is reported separately, never as a title mismatch.
    return re.sub(
        r"^\s*(?:retracted(?:\s+article)?|withdrawn|retraction)\s*:\s*", "", title, flags=re.IGNORECASE
    )


def record_titles(record: PaperRecord) -> list[str]:
    return [record.title, *record.alt_titles]


def record_years(record: PaperRecord) -> list[int]:
    return [year for year in (record.year, *record.alt_years) if year is not None]


def _author_matches(provided: str, fetched: str | None) -> bool:
    if not fetched:
        return False
    if _HANGUL_NAME.match(provided):
        return hangul_surname_matches(provided, fetched)
    provided_tokens = _author_tokens(provided)
    fetched_tokens = _author_tokens(fetched)
    if not provided_tokens or not fetched_tokens:
        return False
    if _looks_like_group_author(provided_tokens) or _looks_like_group_author(
        fetched_tokens,
    ):
        return provided_tokens == fetched_tokens
    return provided_tokens[-1] == fetched_tokens[-1]


def _author_tokens(value: str) -> list[str]:
    normalized = _strip_diacritics(value.casefold())
    cleaned = re.sub(r"[^a-z -]", " ", normalized).strip()
    return [part for part in re.split(r"\s+", cleaned) if part]


def _looks_like_group_author(tokens: list[str]) -> bool:
    return bool(set(tokens) & _GROUP_AUTHOR_TERMS)


def _numbers(value: str) -> list[str]:
    return [
        number.replace(",", "")
        for number in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", value)
    ]


def _title_tokens(value: str) -> list[str]:
    normalized = _transliterate_greek_letters(_strip_diacritics(value.casefold()))
    return [_singularize(token) for token in re.findall(r"[^\W_]+", normalized)]


def _singularize(token: str) -> str:
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token


def _strip_diacritics(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )


def _transliterate_greek_letters(value: str) -> str:
    return "".join(
        f" {_GREEK_LETTER_NAMES[char]} " if char in _GREEK_LETTER_NAMES else char
        for char in value
    )


titles_match = _titles_match
author_matches = _author_matches
author_tokens = _author_tokens


def title_in_text(title: str, text: str) -> bool:
    key = "".join(_title_tokens(_strip_retraction_prefix(title)))
    if not key:
        return False
    tokens = _title_tokens(text)
    starts: set[int] = set()
    ends: set[int] = set()
    offset = 0
    for token in tokens:
        starts.add(offset)
        offset += len(token)
        ends.add(offset)
    # Match on whole tokens of the joined text, so spacing differences inside a formula
    # ("Ti3AlC2" vs "Ti 3 AlC 2") do not matter but "ion gels" never matches "fusion gels".
    joined = "".join(tokens)
    index = joined.find(key)
    while index != -1:
        if index in starts and index + len(key) in ends:
            return True
        index = joined.find(key, index + 1)
    return False


def hangul_surname_matches(name: str, fetched: str) -> bool:
    # CrossRef stores Korean authors romanized ("Yoon"), while Korean reference lists write
    # them in Hangul ("윤혜리"); compare the surname through its usual romanizations.
    match = _HANGUL_NAME.match(name)
    if not match:
        return False
    hangul = match.group(1)
    fetched_tokens = _author_tokens(fetched)
    if not fetched_tokens:
        return False
    candidates = {fetched_tokens[0], fetched_tokens[-1]}
    for surname in (hangul[:2], hangul[:1]):
        if surname in _HANGUL_SURNAMES:
            return bool(candidates & _HANGUL_SURNAMES[surname])
    return False


def title_token_overlap(title: str, text: str) -> float:
    title_tokens = set(_title_tokens(_strip_retraction_prefix(title)))
    if not title_tokens:
        return 0.0
    return len(title_tokens & set(_title_tokens(text))) / len(title_tokens)
