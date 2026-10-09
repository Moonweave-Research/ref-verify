from __future__ import annotations

import re
from dataclasses import dataclass


_NUMBER_PATTERN = r"\d+(?:,\d{3})*(?:\.\d+)?"
_UNIT_PATTERN = (
    r"(?:mg\s*/\s*ml|g\s*/\s*l|(?:g|m|k)?(?:ohm|Ω|Ω)[-·]cm|"
    r"(?:m|k)?v\s*/\s*(?:mm|cm|m)|(?:m|k)?s\s*/\s*m|"
    r"per\s+cent|percent|cycles?|patients?|subjects?|samples?|devices?|"
    r"°c|degc|mev|kev|ev|gpa|mpa|kpa|pa|khz|mhz|mv|kv|ma|"
    r"mg|ml|kg|mm|cm|nm|hz|%|v|a|c|g|l|m|n|j)"
)
_MEASUREMENT_PATTERN = re.compile(
    rf"(?<![\d,])(?P<value>{_NUMBER_PATTERN})\s*(?P<unit>{_UNIT_PATTERN})(?=$|[^\w/·\-ΩΩ°])",
    re.IGNORECASE,
)

_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "in",
    "of",
    "on",
    "the",
    "to",
    "was",
    "were",
    "with",
}

_NON_SUBJECT_TERMS = {
    "above",
    "at",
    "below",
    "equal",
    "exceed",
    "exceeded",
    "exceeding",
    "exceeds",
    "greater",
    "higher",
    "least",
    "less",
    "lower",
    "more",
    "most",
    "no",
    "not",
    "than",
    "under",
    "up",
}

_UNSUPPORTED_FRAME_PATTERNS = (
    r"\baccording to\b",
    r"\bwhether\b",
    r"\bnot true that\b",
    r"\bfalse that\b",
    r"\b(?:did|do|does|is|are|was|were|has|have|had) not\b",
    r"\b(?:fail|fails|failed) to\b",
    r"\bwithout\b",
    r"\bnever\b",
    r"\bno\b.*\b(?:observed|found|shown|showed|reported|measured|demonstrated|had)\b",
    r"\bno (?:sample|samples|specimen|specimens|device|devices|case|cases)\b",
    r"\bnone of (?:the )?(?:sample|samples|specimen|specimens|device|devices|case|cases)\b",
    r"\bnone (?:show|shows|showed|had|has|have|observed|found|reported|reached|met|demonstrated)\b",
    r"\b(?:previous|prior|earlier) (?:work|study|studies|research)\b",
    r"\b(?:may|might|would|should)\b",
    r"\b(?:appear|appears|appeared|appearing) to\b",
    r"\b(?:seem|seems|seemed|seeming) to\b",
    r"\b(?:the )?(?:paper|article|study|work) (?:report|reports|reported|reporting)\b",
    r"\b(?:the )?authors? (?:report|reports|reported|found|finds|observed|observes|noted|notes|claim|claims)\b",
    r"\breportedly\b",
    r"\b(?:claim|claims|claimed|claiming)\b",
    r"\b(?:suggest|suggests|suggested|suggesting)\b",
    r"\b(?:indicate|indicates|indicated|indicating)\b",
    r"\b(?:imply|implies|implied|implying)\b",
)

_SCOPE_OR_COMPARATIVE_SUFFIX_TERMS = {
    "across",
    "after",
    "among",
    "at",
    "average",
    "averaged",
    "averages",
    "before",
    "during",
    "except",
    "following",
    "for",
    "from",
    "in",
    "longer",
    "max",
    "maximum",
    "mean",
    "median",
    "min",
    "minimum",
    "more",
    "only",
    "then",
    "typical",
    "typically",
    "under",
    "unless",
    "until",
    "when",
    "while",
    "within",
}

_PHYSICAL_MEASUREMENT_UNITS = {
    "c",
    "ev",
    "kev",
    "mev",
    "ohm-cm",
    "gohm-cm",
    "mohm-cm",
    "kohm-cm",
    "s/m",
    "ms/m",
    "ks/m",
    "pa",
    "kpa",
    "mpa",
    "gpa",
    "v/m",
    "mv/m",
    "kv/m",
    "v/cm",
    "mv/cm",
    "kv/cm",
    "v/mm",
    "mv/mm",
    "kv/mm",
}

_MEASUREMENT_CONDITION_TERMS = {
    "bias",
    "field",
    "frequency",
    "humidity",
    "hz",
    "k",
    "khz",
    "mhz",
    "pressure",
    "range",
    "ranges",
    "relative",
    "rh",
    "temperature",
    "voltage",
}

_UNIT_TERMS = {
    "a",
    "c",
    "cycle",
    "cycles",
    "degc",
    "device",
    "devices",
    "ev",
    "g",
    "gohmcm",
    "gpa",
    "hz",
    "j",
    "kg",
    "khz",
    "kv",
    "kvcm",
    "kvm",
    "kvmm",
    "l",
    "m",
    "ma",
    "mg",
    "mgml",
    "mpa",
    "mvcm",
    "mvm",
    "mvmm",
    "mhz",
    "ml",
    "mm",
    "mv",
    "nm",
    "n",
    "ohmcm",
    "pa",
    "patient",
    "patients",
    "per",
    "percent",
    "sample",
    "samples",
    "sm",
    "subject",
    "subjects",
    "v",
    "vcm",
    "vm",
    "vmm",
}


@dataclass(frozen=True)
class NumericClaimResult:
    status: str
    reason: str
    evidence: str


@dataclass(frozen=True)
class NumericExpression:
    value: float
    unit: str
    comparator: str
    subject_terms: set[str]
    evidence: str
    prefix_scale: str = ""


def check_numeric_claim_support(abstract: str, claim: str) -> NumericClaimResult:
    claim_expression = _extract_claim_expression(claim)
    if claim_expression is None:
        return NumericClaimResult(
            status="NOT_NUMERIC",
            reason="The claim does not contain a supported numeric expression.",
            evidence="",
        )

    related_evidence = ""
    for clause, subject_context in _clause_contexts(abstract):
        if _has_unsupported_frame(clause):
            related_evidence = related_evidence or clause
            continue
        evidence_expressions = _extract_evidence_expressions(clause)
        if not evidence_expressions:
            continue
        if _subject_terms_match(claim_expression.subject_terms, subject_context):
            related_evidence = related_evidence or clause
        for evidence_expression in evidence_expressions:
            if not _units_match(claim_expression, evidence_expression):
                continue
            if not _subject_terms_match(claim_expression.subject_terms, subject_context):
                continue
            if _evidence_entails_claim(
                evidence_expression.value,
                evidence_expression.comparator,
                claim_expression.value,
                claim_expression.comparator,
            ) and claim_quantities_supported(claim, clause):
                return NumericClaimResult(
                    status="SUPPORTED",
                    reason="The abstract explicitly reports a matching numeric claim.",
                    evidence=clause,
                )
            related_evidence = related_evidence or clause

    return NumericClaimResult(
        status="PARTIAL",
        reason="The abstract contains numeric evidence, but not a clear subject-bound match.",
        evidence=related_evidence or _best_numeric_clause(abstract),
    )


def claim_quantities_supported(claim: str, evidence: str) -> bool:
    # The engines above bind one quantity of the claim; this checks the rest. Every number
    # in the claim, with its unit and comparator, has to be entailed by a number in the
    # same evidence text, and a direction word the claim uses ("higher", "decreased")
    # outside a number's own comparator has to appear there too.
    claim = _CITATION_MARKER_PATTERN.sub(" ", claim)
    claim_quantities = _quantities(claim)
    evidence_quantities = _quantities(evidence)
    if not all(
        any(_quantity_entails(found, wanted) for found in evidence_quantities)
        for wanted in claim_quantities
    ):
        return False
    comparator_spans = [quantity.comparator_span for quantity in claim_quantities]
    evidence_words = {word.lower() for word in re.findall(r"[A-Za-z]+", evidence)}
    for word in re.finditer(r"[A-Za-z]+", claim):
        if word.group().lower() not in _DIRECTION_WORDS:
            continue
        if any(start <= word.start() < end for start, end in comparator_spans):
            continue
        if word.group().lower() not in evidence_words:
            return False
    return True


@dataclass(frozen=True)
class _Quantity:
    value: float
    unit: str
    raw_unit: str
    comparator: str
    comparator_span: tuple[int, int]


_SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")
_DASHES = "-‐‑−–—"
_SCIENTIFIC_PATTERN = re.compile(
    r"(?P<mantissa>\d+(?:\.\d+)?)\s*[×x]\s*10\s*"
    r"(?:\^\s*(?P<caret>[-−–]?\s*\d+)|(?P<signed>[-−–]\s*\d+)"
    r"|(?P<superscript>[⁻⁺]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+))"
)
# Thousands may be grouped with commas or (thin) spaces: "10,000", "10 000".
_PLAIN_NUMBER_PATTERN = re.compile(r"\d{1,3}(?:[,\u2009\u202f\u00a0 ]\d{3})+(?:\.\d+)?(?![\d,])|\d+(?:\.\d+)?")
_RANGE_CONNECTOR_PATTERN = re.compile(r"\s*(?:[-‐‑−–—~]|,?\s*(?:to|and|or)\b)\s*(?=[-−–]?\d)")
_UNCERTAINTY_PATTERN = re.compile(r"\s*(?:±|\+/-|\+-)\s*\d+(?:\.\d+)?")
_CITATION_MARKER_PATTERN = re.compile(r"\[\s*\d+(?:\s*[,–\-]\s*\d+)*\s*\]|\([^()]*\b(?:19|20)\d{2}[a-z]?\)")
_NO_UNIT_WORDS = {
    "after",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "before",
    "by",
    "compared",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "over",
    "respectively",
    "than",
    "that",
    "the",
    "to",
    "under",
    "versus",
    "vs",
    "was",
    "were",
    "when",
    "which",
    "while",
    "with",
    "within",
    "x",
    "×",
}
_UNIT_SYNONYMS = {
    "percent": "%",
    "pct": "%",
    "℃": "°c",
    "degc": "°c",
    "oc": "°c",
    "hour": "h",
    "hr": "h",
    "hrs": "h",
    "minute": "min",
    "sec": "s",
    "second": "s",
    "day": "d",
    "yr": "year",
    "yrs": "year",
    "week": "wk",
    "gram": "g",
    "milligram": "mg",
    "kilogram": "kg",
    "liter": "l",
    "litre": "l",
    "milliliter": "ml",
    "millilitre": "ml",
    "time": "fold",
    "x": "fold",
    "×": "fold",
}
_DIRECTION_WORDS = {
    "better",
    "bigger",
    "decline",
    "declined",
    "declines",
    "decrease",
    "decreased",
    "decreases",
    "decreasing",
    "drop",
    "dropped",
    "drops",
    "enhanced",
    "fell",
    "fewer",
    "greater",
    "higher",
    "improved",
    "increase",
    "increased",
    "increases",
    "increasing",
    "larger",
    "less",
    "longer",
    "lower",
    "lowered",
    "more",
    "raised",
    "reduced",
    "rose",
    "shorter",
    "smaller",
    "stronger",
    "weaker",
    "worse",
}


def _quantities(text: str) -> list[_Quantity]:
    spans: list[tuple[int, int, float]] = []
    for match in _SCIENTIFIC_PATTERN.finditer(text):
        sign = _number_sign(text, match.start(), match.group("mantissa"))
        if sign is None:
            continue
        exponent = match.group("caret") or match.group("signed") or match.group("superscript")
        exponent = re.sub(r"\s", "", exponent.translate(_SUPERSCRIPTS)).translate(str.maketrans("−–", "--"))
        spans.append((match.start(), match.end(), sign * float(match.group("mantissa")) * 10 ** int(exponent)))
    for match in _PLAIN_NUMBER_PATTERN.finditer(text):
        if any(start <= match.start() < end for start, end, _ in spans):
            continue
        sign = _number_sign(text, match.start(), match.group())
        if sign is None:
            continue
        spans.append((match.start(), match.end(), sign * float(re.sub(r"[^\d.]", "", match.group()))))
    spans.sort()

    quantities: list[_Quantity | None] = []
    inherits: list[bool] = []
    previous_end = 0
    for start, end, value in spans:
        number_start = start - 1 if value < 0 else start
        unit_end = end
        uncertainty = _UNCERTAINTY_PATTERN.match(text, unit_end)
        if uncertainty:
            unit_end = uncertainty.end()
        raw_unit = ""
        comparator_suffix = ""
        inherit = bool(_RANGE_CONNECTOR_PATTERN.match(text, unit_end))
        if not inherit:
            raw_unit, unit_end, comparator_suffix = _unit_token(text, unit_end)
        if raw_unit is None:
            quantities.append(None)
            inherits.append(False)
            continue
        comparator, comparator_start = _quantity_comparator(text[previous_end:number_start], comparator_suffix)
        quantities.append(
            _Quantity(
                value=value,
                unit=_normalize_quantity_unit(raw_unit),
                raw_unit=raw_unit,
                comparator=comparator,
                comparator_span=(previous_end + comparator_start, number_start),
            )
        )
        inherits.append(inherit)
        previous_end = unit_end
    # "0–6 kPa", "50 and 60 nm": a number with no unit of its own takes the next one's.
    for index in range(len(quantities) - 2, -1, -1):
        current, following = quantities[index], quantities[index + 1]
        if inherits[index] and current is not None and following is not None:
            quantities[index] = _Quantity(
                value=current.value,
                unit=following.unit,
                raw_unit=following.raw_unit,
                comparator=current.comparator,
                comparator_span=current.comparator_span,
            )
    return [quantity for quantity in quantities if quantity is not None]


def _number_sign(text: str, start: int, number: str) -> int | None:
    # None marks a number that is part of a name or a unit exponent (Fe2C, KIT-6, cm−1).
    previous = text[start - 1 : start]
    if not previous:
        return 1
    if previous.isalpha() or previous.isdigit() or previous in "_.,/":
        return None
    if previous not in _DASHES:
        return 1
    before = text[start - 2 : start - 1]
    if before.isdigit():
        return 1
    if before and not before.isspace() and before not in "([=:,;≈~<>≤≥":
        return None
    # "kPa −1", "S cm −1": a spaced exponent after a unit, not a negative number.
    unit_word = re.search(r"([A-Za-zµμΩ°]+)\s?[-‐‑−–—]$", text[:start])
    if (
        unit_word
        and len(unit_word.group(1)) <= 4
        and unit_word.group(1) != "a"
        and unit_word.group(1).lower() not in _NO_UNIT_WORDS
        and re.fullmatch(r"[1-4]", number)
    ):
        return None
    return -1


def _unit_token(text: str, position: int) -> tuple[str | None, int, str]:
    attached = not text[position : position + 1].isspace()
    match = re.compile(r"\s*(\S+)").match(text, position)
    if not match:
        return "", position, ""
    token = match.group(1)
    end = match.end()
    if not attached and (token[:1] in "([" or re.match(r"[-−–]?\d", token)):
        return "", position, text[position:]
    stripped = token.rstrip(",.;:!?")
    while stripped.endswith((")", "]")) and stripped.count("(") < stripped.count(")") + stripped.count("]"):
        stripped = stripped[:-1].rstrip(",.;:!?")
    stripped = stripped.lstrip(_DASHES)
    plus = stripped.endswith("+")
    stripped = stripped.rstrip("+")
    if attached and re.match(r"(?:st|nd|rd|th|D)\b", stripped):
        return None, end, ""
    # "a" is an article, "A" an ampere.
    if not attached and (stripped == "a" or stripped.lower() in _NO_UNIT_WORDS):
        return "", position, text[position:]
    if stripped.lower() == "per" and re.match(r"\s+cent\b", text[end:]):
        stripped = "percent"
        end = re.compile(r"\s+cent\b").match(text, end).end()
    exponent = re.compile(r"\s?([-−–])\s?([1-4])(?![\d.])").match(text, end)
    if stripped.isalpha() and len(stripped) <= 4 and exponent:
        stripped = f"{stripped}-{exponent.group(2)}"
        end = exponent.end()
    return stripped, end, ("+" if plus else "") + text[end:]


def _normalize_quantity_unit(raw_unit: str) -> str:
    unit = raw_unit.translate(_SUPERSCRIPTS)
    unit = re.sub(r"[−–—‐‑]", "-", unit).replace("µ", "u").replace("μ", "u")
    unit = re.sub(r"[ΩΩω]", "ohm", unit)
    unit = re.sub(r"[()\[\]{}·⋅•.]", "", unit).lower()
    # "ohm-cm" and "Ω·cm" are one unit; a hyphen before a digit is an exponent and stays.
    unit = re.sub(r"(?<=[a-z])-(?=[a-z])", "", unit)
    parts = []
    for part in unit.split("/"):
        if part.isalpha() and len(part) > 3 and part.endswith("s") and not part.endswith("ss"):
            part = part[:-1]
        parts.append(_UNIT_SYNONYMS.get(part, part))
    return "/".join(parts)


def _quantity_comparator(prefix: str, suffix: str) -> tuple[str, int]:
    text = prefix.lower().rstrip()
    patterns = (
        ("approx", r"(?:[~∼≈]|\b(?:about|approximately|approx\.?|around|roughly|nearly|almost|circa|ca\.))$"),
        (
            "gte",
            r"(?:≥|>=|\b(?:at least|not less than|no less than|no lower than|"
            r"(?:more|greater|higher) than or equal to))$",
        ),
        (
            "lte",
            r"(?:≤|<=|\b(?:at most|no more than|not more than|no greater than|no higher than|"
            r"(?:less|lower|fewer) than or equal to))$",
        ),
        ("gt", r"(?:>|\b(?:above|over|exceed|exceeds|exceeded|exceeding|(?:more|greater|higher) than))$"),
        ("lt", r"(?:<|\b(?:below|under|(?:less|lower|fewer) than))$"),
        ("up_to", r"\bup to$"),
    )
    for comparator, pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return comparator, match.start()
    following = suffix.lower()
    if following.startswith("+") or re.match(
        r"\s*[,;:]?\s*(?:or\s+(?:more|greater|higher|above|longer)|min|minimum)\b", following
    ):
        return "gte", len(prefix)
    if re.match(r"\s*[,;:]?\s*(?:or\s+(?:less|fewer|lower|below|shorter)|max|maximum)\b", following):
        return "lte", len(prefix)
    return "exact", len(prefix)


def _quantity_entails(found: _Quantity, wanted: _Quantity) -> bool:
    if wanted.unit and not _quantity_units_match(found, wanted):
        return False
    if wanted.comparator == "approx":
        return found.comparator in {"exact", "approx"} and found.value == wanted.value
    # An approximate figure in the evidence supports only an approximate claim.
    if found.comparator == "approx":
        return False
    # "Up to 117%" reports that 117% was reached, which supports "above 100%".
    if found.comparator == "up_to" and wanted.comparator in {"gt", "gte"}:
        return found.value > wanted.value if wanted.comparator == "gt" else found.value >= wanted.value
    return _evidence_entails_claim(found.value, found.comparator, wanted.value, wanted.comparator)


def _quantity_units_match(found: _Quantity, wanted: _Quantity) -> bool:
    if found.unit != wanted.unit:
        return False
    # "mPa" and "MPa" differ by 10^9; only an all-lowercase token is left ambiguous.
    left, right = found.raw_unit, wanted.raw_unit
    return not (
        left[:1] in "mM"
        and right[:1] in "mM"
        and left[:1] != right[:1]
        and left != left.lower()
        and right != right.lower()
    )


def _extract_claim_expression(claim: str) -> NumericExpression | None:
    match = _MEASUREMENT_PATTERN.search(claim)
    if not match:
        return None
    return NumericExpression(
        value=_parse_value(match.group("value")),
        unit=_normalize_unit(match.group("unit")),
        comparator=_claim_comparator(claim[: match.start()]),
        subject_terms=_subject_terms(claim[: match.start()]),
        evidence=claim,
        prefix_scale=_prefix_scale(match.group("unit")),
    )


def _extract_evidence_expressions(clause: str) -> list[NumericExpression]:
    expressions: list[NumericExpression] = []
    for match in _MEASUREMENT_PATTERN.finditer(clause):
        expressions.append(
            NumericExpression(
                value=_parse_value(match.group("value")),
                unit=_normalize_unit(match.group("unit")),
                comparator=_evidence_comparator(
                    clause[: match.start()],
                    clause[match.end() :],
                ),
                subject_terms=_subject_terms(clause[: match.start()]),
                evidence=clause,
                prefix_scale=_prefix_scale(match.group("unit")),
            )
        )
    return expressions


def _clauses(value: str) -> list[str]:
    return [clause for clause, _ in _clause_contexts(value)]


def _clause_contexts(value: str) -> list[tuple[str, str]]:
    clauses: list[tuple[str, str]] = []
    previous_sentence = ""
    for sentence in re.split(r"(?<=[.!?])\s+|[.;:]\s+", value.strip()):
        sentence = sentence.strip()
        if not sentence:
            continue
        parts = [
            part.strip()
            for part in re.split(r",?\s+\b(?:and|but|while|whereas)\b\s+", sentence)
            if part.strip()
        ]
        for part in parts:
            for clause in _split_numeric_comma_clauses(part):
                clauses.append((clause, _subject_context(clause, previous_sentence)))
        previous_sentence = sentence
    return clauses


def _subject_context(clause: str, previous_sentence: str) -> str:
    tokens = _tokens(clause)
    if tokens and _stem(tokens[0]) in {"measurement", "measurements"} and previous_sentence:
        return f"{previous_sentence} {clause}"
    return clause


def _split_numeric_comma_clauses(value: str) -> list[str]:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if len(parts) <= 1:
        return [value.strip()]
    if parts[0].lower().split()[:1] in (["after"], ["before"], ["under"], ["in"]):
        return [value.strip()]
    units = [
        _normalize_unit(match.group("unit"))
        for part in parts
        for match in _MEASUREMENT_PATTERN.finditer(part)
    ]
    if len(units) != len(set(units)):
        return parts
    return [value.strip()]


def _best_numeric_clause(value: str) -> str:
    for clause in _clauses(value):
        if _MEASUREMENT_PATTERN.search(clause):
            return clause
    return value.strip()


def _subject_terms_match(subject_terms: set[str], clause: str) -> bool:
    if not subject_terms:
        return False
    clause_terms = {_stem(token) for token in _tokens(clause)}
    return subject_terms <= clause_terms


def _subject_terms(value: str) -> set[str]:
    return {
        _stem(token)
        for token in _tokens(value)
        if _stem(token) not in _NON_SUBJECT_TERMS and _stem(token) not in _UNIT_TERMS
    }


def _tokens(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-zA-Z°]+", value.lower().replace("/", ""))
        if token not in _STOPWORDS
    ]


def _stem(token: str) -> str:
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token


def _parse_value(value: str) -> float:
    return float(value.replace(",", ""))


def _normalize_unit(value: str) -> str:
    normalized = value.replace("Ω", "ohm").replace("Ω", "ohm").replace("ω", "ohm").lower()
    normalized = normalized.replace("·", "-")
    normalized = re.sub(r"\s*/\s*", "/", normalized)
    normalized = normalized.replace(" ", "")
    if normalized in {"%", "percent"}:
        return "%"
    if normalized in {"°c", "degc", "c"}:
        return "c"
    if normalized in {"cycle", "cycles"}:
        return "cycle"
    if normalized in {"patient", "patients", "subject", "subjects"}:
        return "person"
    if normalized in {"sample", "samples", "device", "devices"}:
        return normalized.rstrip("s")
    return normalized.rstrip("s")


def _units_match(left: NumericExpression, right: NumericExpression) -> bool:
    if left.unit != right.unit:
        return False
    # "mV" and "MV" differ by a factor of a million; only an all-lowercase token
    # (common in typed claims) is left ambiguous and allowed to match either.
    if left.prefix_scale and right.prefix_scale:
        return left.prefix_scale == right.prefix_scale
    return True


_PREFIX_SENSITIVE_UNITS = {
    "ma",
    "mev",
    "mhz",
    "mohm-cm",
    "mpa",
    "ms/m",
    "mv",
    "mv/cm",
    "mv/m",
    "mv/mm",
}


def _prefix_scale(raw_unit: str) -> str:
    if _normalize_unit(raw_unit) not in _PREFIX_SENSITIVE_UNITS:
        return ""
    stripped = raw_unit.strip()
    if stripped == stripped.lower():
        return ""
    return "mega" if stripped[0] == "M" else "milli"


def _claim_comparator(prefix: str) -> str:
    normalized = prefix.lower()
    if ">=" in normalized or "≥" in normalized:
        return "gte"
    if "<=" in normalized or "≤" in normalized:
        return "lte"
    if ">" in normalized:
        return "gt"
    if "<" in normalized:
        return "lt"
    if re.search(r"\b(?:more|greater|higher) than or equal to\b", normalized):
        return "gte"
    if re.search(r"\b(?:less|lower|fewer) than or equal to\b", normalized):
        return "lte"
    if re.search(r"\b(?:at least|not less than)\b", normalized):
        return "gte"
    if re.search(r"\b(?:at most|no more than)\b", normalized):
        return "lte"
    if re.search(r"\bup to\b", normalized):
        return "up_to"
    if re.search(r"\b(?:below|under|less than)\b", normalized):
        return "lt"
    if re.search(r"\b(?:above|over|greater than|more than|exceeded|exceeds)\b", normalized):
        return "gt"
    return "exact"


def _evidence_comparator(prefix: str, suffix: str = "") -> str:
    normalized = prefix.lower().rstrip()
    normalized_suffix = suffix.lower().lstrip()
    if normalized.endswith((">=", "≥")):
        return "gte"
    if normalized.endswith(("<=", "≤")):
        return "lte"
    if normalized.endswith(">"):
        return "gt"
    if normalized.endswith("<"):
        return "lt"
    if re.search(r"\b(?:at least|not less than)\s*$", normalized):
        return "gte"
    if re.search(r"\b(?:at most|no more than)\s*$", normalized):
        return "lte"
    if re.search(r"\b(?:below|under|less than)\s*$", normalized):
        return "lt"
    if re.search(r"\b(?:above|over|greater than|more than|exceeded|exceeds|reached|survived|maintained)\s*$", normalized):
        return "exact"
    if re.search(r"\bup to\s*$", normalized):
        return "up_to"
    if re.search(r"^\s*(?:or\s+)?(?:more|greater|higher|min|minimum)\b", normalized_suffix):
        return "gte"
    if re.search(r"^\s*(?:or\s+)?(?:less|fewer|lower|max|maximum)\b", normalized_suffix):
        return "lte"
    return "exact"


def _has_unsupported_frame(value: str) -> bool:
    normalized = " ".join(re.findall(r"[a-zA-Z0-9]+", value.lower()))
    if any(re.search(pattern, normalized) for pattern in _UNSUPPORTED_FRAME_PATTERNS):
        return True
    for match in _MEASUREMENT_PATTERN.finditer(value):
        prefix_tokens = [
            token
            for token in re.findall(r"[a-zA-Z]+", value[: match.start()].lower())
        ]
        if any(
            token in {"average", "averaged", "mean", "median", "typical", "typically"}
            for token in prefix_tokens
        ):
            return True
        suffix_tokens = [
            token
            for token in re.findall(r"[a-zA-Z]+", value[match.end() :].lower())
        ]
        if _has_disqualifying_suffix(match.group("unit"), suffix_tokens):
            return True
    if _starts_with_current_study_intro(value):
        return False
    prefix_tokens = re.findall(r"[a-zA-Z]+", value.lower())[:2]
    return any(token in {"after", "before", "under", "in"} for token in prefix_tokens)


def _starts_with_current_study_intro(value: str) -> bool:
    normalized = " ".join(re.findall(r"[a-zA-Z]+", value.lower()))
    return bool(
        re.match(
            r"^(?:hence|therefore|accordingly)?\s*in "
            r"(?:(?:the|this|our)\s+)?(?:present\s+)?(?:study|work)\b",
            normalized,
        )
    )


def _has_disqualifying_suffix(unit: str, suffix_tokens: list[str]) -> bool:
    if not any(token in _SCOPE_OR_COMPARATIVE_SUFFIX_TERMS for token in suffix_tokens):
        return False
    normalized_unit = _normalize_unit(unit)
    if (
        normalized_unit in _PHYSICAL_MEASUREMENT_UNITS
        and _looks_like_measurement_condition(suffix_tokens)
    ):
        return False
    return True


def _looks_like_measurement_condition(tokens: list[str]) -> bool:
    return any(token in _MEASUREMENT_CONDITION_TERMS for token in tokens)


def _evidence_entails_claim(
    evidence_value: float,
    evidence_comparator: str,
    claim_value: float,
    claim_comparator: str,
) -> bool:
    if evidence_comparator == "up_to":
        if claim_comparator == "up_to":
            return evidence_value == claim_value
        return claim_comparator in {"lt", "lte"} and evidence_value <= claim_value
    # Evidence that only bounds the value from one side cannot support a claim
    # bounding it from the other side ("below 50" never establishes "above 40").
    if evidence_comparator in {"lt", "lte"}:
        if claim_comparator == "lt":
            return evidence_value <= claim_value if evidence_comparator == "lt" else evidence_value < claim_value
        if claim_comparator == "lte":
            return evidence_value <= claim_value
        return False
    if evidence_comparator in {"gt", "gte"}:
        if claim_comparator == "gt":
            return evidence_value >= claim_value if evidence_comparator == "gt" else evidence_value > claim_value
        if claim_comparator == "gte":
            return evidence_value >= claim_value
        return False
    if claim_comparator == "gt":
        return evidence_value > claim_value
    if claim_comparator == "gte":
        return evidence_value >= claim_value
    if claim_comparator == "lt":
        return evidence_value < claim_value
    if claim_comparator == "lte":
        return evidence_value <= claim_value
    return evidence_comparator == "exact" and evidence_value == claim_value
