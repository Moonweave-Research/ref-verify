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


def check_numeric_claim_support(abstract: str, claim: str) -> NumericClaimResult:
    claim_expression = _extract_claim_expression(claim)
    if claim_expression is None:
        return NumericClaimResult(
            status="NOT_NUMERIC",
            reason="The claim does not contain a supported numeric expression.",
            evidence="",
        )

    related_evidence = ""
    for clause in _clauses(abstract):
        if _has_unsupported_frame(clause):
            related_evidence = related_evidence or clause
            continue
        evidence_expressions = _extract_evidence_expressions(clause)
        if not evidence_expressions:
            continue
        if _subject_terms_match(claim_expression.subject_terms, clause):
            related_evidence = related_evidence or clause
        for evidence_expression in evidence_expressions:
            if not _units_match(claim_expression.unit, evidence_expression.unit):
                continue
            if not _subject_terms_match(claim_expression.subject_terms, clause):
                continue
            if _evidence_entails_claim(
                evidence_expression.value,
                evidence_expression.comparator,
                claim_expression.value,
                claim_expression.comparator,
            ):
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
            )
        )
    return expressions


def _clauses(value: str) -> list[str]:
    clauses: list[str] = []
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
            clauses.extend(_split_numeric_comma_clauses(part))
    return clauses


def _split_numeric_comma_clauses(value: str) -> list[str]:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if len(parts) <= 1:
        return [value.strip()]
    if parts[0].lower().split()[:1] in (["after"], ["before"], ["under"], ["in"]):
        return [value.strip()]
    if sum(1 for part in parts if _MEASUREMENT_PATTERN.search(part)) >= 2:
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


def _units_match(left: str, right: str) -> bool:
    return left == right


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
    prefix_tokens = re.findall(r"[a-zA-Z]+", value.lower())[:2]
    return any(token in {"after", "before", "under", "in"} for token in prefix_tokens)


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
        return claim_comparator in {"lt", "lte"} and evidence_value <= claim_value
    if claim_comparator == "gt":
        return evidence_value > claim_value
    if claim_comparator == "gte":
        return evidence_value >= claim_value
    if claim_comparator == "lt":
        return evidence_value < claim_value
    if claim_comparator == "lte":
        return evidence_value <= claim_value
    return evidence_comparator == "exact" and evidence_value == claim_value
