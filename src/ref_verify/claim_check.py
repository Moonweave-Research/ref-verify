from __future__ import annotations

import re

from ref_verify.models import ClaimSupportResult, PaperRecord

_STOPWORDS = {
    "a",
    "an",
    "and",
    "above",
    "as",
    "at",
    "can",
    "for",
    "in",
    "of",
    "over",
    "that",
    "the",
    "to",
    "up",
    "with",
}

_STRAIN_QUALIFIER_STEMS = {
    "bend",
    "bending",
    "compressive",
    "compression",
    "elongation",
    "shear",
    "tensile",
    "torsion",
    "torsional",
}

_TEXT_CLAIM_COMPARATIVE_SUFFIXES = {
    "additional",
    "decreased",
    "extra",
    "fewer",
    "greater",
    "higher",
    "increased",
    "less",
    "longer",
    "lower",
    "more",
    "shorter",
    "than",
}

_TEXT_CLAIM_SCOPE_SUFFIXES = {
    "after",
    "before",
    "during",
    "except",
    "following",
    "only",
    "then",
    "under",
    "unless",
    "until",
    "when",
    "while",
}

_UNRELATED_PERCENTAGE_SUBJECT_STEMS = {
    "breakdown",
    "conductivity",
    "cycle",
    "efficiency",
    "energy",
    "field",
    "force",
    "frequency",
    "lifetime",
    "modulus",
    "power",
    "pressure",
    "speed",
    "stress",
    "temperature",
    "voltage",
}

_UNSUPPORTED_CLAIM_FRAME_PATTERNS = (
    r"\baccording to\b",
    r"\bwhether\b",
    r"\bif\b",
    r"\bnot true that\b",
    r"\bfalse that\b",
    r"\b(?:did|do|does|is|are|was|were|has|have|had) not\b",
    r"\b(?:didn t|don t|doesn t|isn t|aren t|wasn t|weren t)\b",
    r"\bnever\b",
    r"\bno "
    r"(?:sample|samples|specimen|specimens|device|devices|case|cases|paper|papers|study|studies)\b",
    r"\bnone of (?:the )?"
    r"(?:sample|samples|specimen|specimens|device|devices|case|cases|paper|papers|study|studies)\b",
    r"\bnone "
    r"(?:show|shows|showed|had|has|have|observed|found|reported|reached|exceeded|met|demonstrated)\b",
    r"\b(?:previous|prior|earlier) (?:work|study|studies|research)\b",
    r"\b(?:reported|claimed|suggested)\b",
    r"\bachievable\b",
    r"\bpossible\b",
)


def check_claim_support(record: PaperRecord, claim: str) -> ClaimSupportResult:
    if not record.abstract:
        return ClaimSupportResult(
            status="UNVERIFIABLE",
            verdict="WARN",
            reason="No abstract was available from the fetched record.",
            evidence="",
            paper=record,
            claim=claim,
        )

    threshold = _claim_percentage_threshold(claim)
    comparator = _claim_percentage_comparator(claim)
    evidence_sentences = _ranked_evidence_sentences(record.abstract, claim)
    evidence_sentence = evidence_sentences[0] if evidence_sentences else record.abstract.strip()

    if threshold is not None:
        for sentence in evidence_sentences:
            supported = _sentence_supports_percentage_claim(
                sentence,
                threshold,
                comparator,
                claim,
            )
            if supported:
                return ClaimSupportResult(
                    status="SUPPORTED",
                    verdict="ACCEPT",
                    reason="Fetched abstract explicitly reports a matching quantitative claim.",
                    evidence=sentence,
                    paper=record,
                    claim=claim,
                )

        for sentence in evidence_sentences:
            if _all_percentage_evidence_is_prestrain(sentence):
                return ClaimSupportResult(
                    status="PARTIAL",
                    verdict="WARN",
                    reason=(
                        "The abstract percentage appears in a pre-strain context, "
                        "not an actuation output."
                    ),
                    evidence=sentence,
                    paper=record,
                    claim=claim,
                )

    if threshold is None:
        for sentence in evidence_sentences:
            if _sentence_supports_text_claim(sentence, claim):
                return ClaimSupportResult(
                    status="SUPPORTED",
                    verdict="ACCEPT",
                    reason="Fetched abstract explicitly states the claim.",
                    evidence=sentence,
                    paper=record,
                    claim=claim,
                )

    if _term_overlap(claim, record.abstract) > 0:
        return ClaimSupportResult(
            status="PARTIAL",
            verdict="WARN",
            reason="The abstract is related, but does not explicitly support the specific claim.",
            evidence=evidence_sentence,
            paper=record,
            claim=claim,
        )

    return ClaimSupportResult(
        status="PARTIAL",
        verdict="WARN",
        reason="The abstract does not explicitly support the specific claim.",
        evidence=evidence_sentence,
        paper=record,
        claim=claim,
    )


def _claim_percentage_threshold(claim: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", claim)
    return float(match.group(1)) if match else None


def _claim_percentage_comparator(claim: str) -> str:
    normalized = claim.lower()
    if ">=" in normalized:
        return "gte"
    if "<=" in normalized:
        return "lte"
    if re.search(r"\b(at least|not less than)\b", normalized):
        return "gte"
    if re.search(r"\b(at most|no more than)\b", normalized):
        return "lte"
    if re.search(r"\b(below|under|less than)\b", normalized):
        return "lt"
    if re.search(
        r"\b(above|over|greater than|more than|exceeded|exceeds|exceeding)\b",
        normalized,
    ):
        return "gt"
    return "exact"


def _ranked_evidence_sentences(abstract: str, claim: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", abstract.strip())
    if not sentences:
        return [abstract.strip()]
    stripped = [sentence.strip() for sentence in sentences if sentence.strip()]
    return sorted(stripped, key=lambda sentence: _term_overlap(claim, sentence), reverse=True)


def _sentence_supports_percentage_claim(
    sentence: str,
    threshold: float,
    comparator: str,
    claim: str,
) -> bool:
    if _has_unsupported_claim_frame(sentence):
        return False
    contexts = _percentage_contexts(sentence)
    for index, (value, context) in enumerate(contexts):
        if _mentions_prestrain_context(context):
            continue
        if _has_unsupported_claim_frame(context):
            continue
        if not _has_actuation_strain_context(context, claim):
            continue
        evidence_comparator = _evidence_percentage_comparator(context)
        if _evidence_entails_claim(value, evidence_comparator, threshold, comparator):
            if _has_contradictory_percentage_context(
                contexts,
                index,
                threshold,
                comparator,
                claim,
                sentence,
            ):
                continue
            return True
    return False


def _evidence_entails_claim(
    value: float,
    evidence_comparator: str,
    threshold: float,
    claim_comparator: str,
) -> bool:
    if evidence_comparator == "up_to":
        if claim_comparator == "exact":
            return False
        return _compare_percentage(value, threshold, claim_comparator)
    if evidence_comparator == "lt":
        return claim_comparator in {"lt", "lte"} and value <= threshold
    if evidence_comparator == "lte":
        if claim_comparator == "lt":
            return value < threshold
        return claim_comparator == "lte" and value <= threshold
    if evidence_comparator == "gt":
        return claim_comparator in {"gt", "gte"} and value >= threshold
    if evidence_comparator == "gte":
        if claim_comparator == "gt":
            return value > threshold
        return claim_comparator == "gte" and value >= threshold
    return _compare_percentage(value, threshold, claim_comparator)


def _compare_percentage(value: float, threshold: float, comparator: str) -> bool:
    if comparator == "lt":
        return value < threshold
    if comparator == "lte":
        return value <= threshold
    if comparator == "gte":
        return value >= threshold
    if comparator == "gt":
        return value > threshold
    return value == threshold


def _has_contradictory_percentage_context(
    contexts: list[tuple[float, str]],
    supporting_index: int,
    threshold: float,
    claim_comparator: str,
    claim: str,
    sentence: str,
) -> bool:
    for index, (value, context) in enumerate(contexts):
        if index == supporting_index:
            continue
        if _mentions_prestrain_context(context):
            continue
        if _has_unsupported_claim_frame(context):
            continue
        if not _has_percentage_subject_context(context, sentence, claim):
            continue
        evidence_comparator = _evidence_percentage_comparator(context)
        if _evidence_contradicts_claim(
            value,
            evidence_comparator,
            threshold,
            claim_comparator,
        ):
            return True
    return False


def _has_percentage_subject_context(context: str, sentence: str, claim: str) -> bool:
    if _has_actuation_strain_context(context, claim):
        return True
    return _inherits_actuation_strain_subject(context, sentence, claim)


def _inherits_actuation_strain_subject(context: str, sentence: str, claim: str) -> bool:
    claim_terms = {_stem(token) for token in _tokens(claim)}
    if "actuat" not in claim_terms:
        return False

    sentence_terms = {_stem(token) for token in _tokens(sentence)}
    if not {"actuat", "strain"} <= sentence_terms:
        return False

    context_terms = {_stem(token) for token in _tokens(context)}
    if context_terms & _STRAIN_QUALIFIER_STEMS:
        return False
    return not bool(context_terms & _UNRELATED_PERCENTAGE_SUBJECT_STEMS)


def _evidence_contradicts_claim(
    value: float,
    evidence_comparator: str,
    threshold: float,
    claim_comparator: str,
) -> bool:
    if claim_comparator == "lt":
        return (
            (evidence_comparator == "exact" and value >= threshold)
            or (evidence_comparator == "gt" and value >= threshold)
            or (evidence_comparator == "gte" and value >= threshold)
        )
    if claim_comparator == "lte":
        return (
            (evidence_comparator == "exact" and value > threshold)
            or (evidence_comparator == "gt" and value >= threshold)
            or (evidence_comparator == "gte" and value > threshold)
        )
    if claim_comparator == "gt":
        return (
            (evidence_comparator == "exact" and value <= threshold)
            or (evidence_comparator in {"lt", "lte", "up_to"} and value <= threshold)
        )
    if claim_comparator == "gte":
        return (
            (evidence_comparator == "exact" and value < threshold)
            or (evidence_comparator == "lt" and value <= threshold)
            or (evidence_comparator in {"lte", "up_to"} and value < threshold)
        )
    return (
        (evidence_comparator == "exact" and value != threshold)
        or (evidence_comparator == "lt" and value <= threshold)
        or (evidence_comparator in {"lte", "up_to"} and value < threshold)
        or (evidence_comparator == "gt" and value >= threshold)
        or (evidence_comparator == "gte" and value > threshold)
    )


def _sentence_supports_text_claim(sentence: str, claim: str) -> bool:
    claim_numbers = set(_numbers(claim))
    if claim_numbers and not claim_numbers <= set(_numbers(sentence)):
        return False

    claim_tokens = _phrase_tokens(claim)
    if not claim_tokens:
        return False
    sentence_tokens = _phrase_tokens(sentence)

    for start in _token_sequence_offsets(sentence_tokens, claim_tokens):
        end = start + len(claim_tokens)
        if _has_unsupported_claim_frame(sentence):
            continue
        if _has_comparative_suffix(sentence_tokens, end):
            continue
        return True
    return False


def _all_percentage_evidence_is_prestrain(value: str) -> bool:
    contexts = [context for _, context in _percentage_contexts(value)]
    return bool(contexts) and all(_mentions_prestrain_context(context) for context in contexts)


def _percentage_contexts(value: str) -> list[tuple[float, str]]:
    contexts: list[tuple[float, str]] = []
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*%", value):
        start, end = _clause_bounds(value, match.start(), match.end())
        contexts.append((float(match.group(1)), value[start:end]))
    return contexts


def _evidence_percentage_comparator(context: str) -> str:
    percentage = re.search(r"\d+(?:\.\d+)?\s*%", context)
    if not percentage:
        return "exact"

    prefix = context[: percentage.start()].lower()
    if re.search(r"\b(at least|not less than)\s*$", prefix):
        return "gte"
    if re.search(r"\b(at most|no more than)\s*$", prefix):
        return "lte"
    if re.search(r"\bup to\s*$", prefix):
        return "up_to"
    if re.search(r"\b(below|under|less than)\s*$", prefix):
        return "lt"
    if re.search(
        r"\b(above|over|greater than|more than|exceeded|exceeds|exceeding)\s*$",
        prefix,
    ):
        return "gt"
    return "exact"


def _clause_bounds(value: str, start: int, end: int) -> tuple[int, int]:
    boundary = r"(?:[.;:]\s+|,\s+|,?\s+\b(?:and|but|while|whereas|although)\b\s+)"
    context_start = 0
    for match in re.finditer(boundary, value[:start]):
        context_start = match.end()

    next_boundary = re.search(boundary, value[end:])
    context_end = end + next_boundary.start() if next_boundary else len(value)
    return context_start, context_end


def _mentions_prestrain_context(value: str) -> bool:
    normalized = value.lower()
    return "pre-strain" in normalized or "prestrain" in normalized


def _has_actuation_strain_context(sentence: str, claim: str) -> bool:
    terms = {_stem(token) for token in _tokens(sentence)}
    claim_terms = {_stem(token) for token in _tokens(claim)}
    if "strain" not in terms:
        return False
    if "actuat" in claim_terms:
        if "actuat" not in terms:
            return False
        return not bool(terms & _STRAIN_QUALIFIER_STEMS)
    claim_qualifiers = claim_terms & _STRAIN_QUALIFIER_STEMS
    if claim_qualifiers and not claim_qualifiers <= terms:
        return False
    return True


def _term_overlap(left: str, right: str) -> int:
    left_terms = {_stem(token) for token in _tokens(left)}
    right_terms = {_stem(token) for token in _tokens(right)}
    return len(left_terms & right_terms)


def _tokens(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-zA-Z]+", value.lower())
        if token not in _STOPWORDS
    ]


def _numbers(value: str) -> list[str]:
    return [
        number.replace(",", "")
        for number in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", value)
    ]


def _phrase_tokens(value: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]+", value.lower())


def _token_sequence_offsets(tokens: list[str], target: list[str]) -> list[int]:
    width = len(target)
    return [
        index
        for index in range(0, len(tokens) - width + 1)
        if tokens[index : index + width] == target
    ]


def _has_unsupported_claim_frame(value: str) -> bool:
    normalized = " ".join(_phrase_tokens(value))
    return any(
        re.search(pattern, normalized)
        for pattern in _UNSUPPORTED_CLAIM_FRAME_PATTERNS
    )


def _has_comparative_suffix(tokens: list[str], claim_end: int) -> bool:
    if claim_end >= len(tokens):
        return False

    suffix = tokens[claim_end:]
    if any(token in _TEXT_CLAIM_COMPARATIVE_SUFFIXES for token in suffix):
        return True
    if any(token in _TEXT_CLAIM_SCOPE_SUFFIXES for token in suffix):
        return True
    return False


def _stem(token: str) -> str:
    if token.startswith("actuat"):
        return "actuat"
    if token.startswith("strain"):
        return "strain"
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token
