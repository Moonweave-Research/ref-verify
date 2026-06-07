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
    if "<=" in normalized:
        return "lte"
    if ">=" in normalized:
        return "gte"
    if re.search(r"\b(below|under|less than|at most|no more than)\b", normalized):
        return "lte"
    if re.search(r"\b(at least|not less than)\b", normalized):
        return "gte"
    return "gt"


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
    if not _has_actuation_strain_context(sentence, claim):
        return False

    for value, context in _percentage_contexts(sentence):
        if _mentions_prestrain_context(context):
            continue
        if _compare_percentage(value, threshold, comparator):
            return True
    return False


def _compare_percentage(value: float, threshold: float, comparator: str) -> bool:
    if comparator == "lte":
        return value <= threshold
    if comparator == "gte":
        return value >= threshold
    return value > threshold


def _sentence_supports_text_claim(sentence: str, claim: str) -> bool:
    claim_numbers = set(_numbers(claim))
    if claim_numbers and not claim_numbers <= set(_numbers(sentence)):
        return False

    claim_terms = {_stem(token) for token in _tokens(claim)}
    if not claim_terms:
        return False
    sentence_terms = {_stem(token) for token in _tokens(sentence)}
    overlap = claim_terms & sentence_terms
    return len(overlap) / len(claim_terms) >= 0.8


def _all_percentage_evidence_is_prestrain(value: str) -> bool:
    contexts = [context for _, context in _percentage_contexts(value)]
    return bool(contexts) and all(_mentions_prestrain_context(context) for context in contexts)


def _percentage_contexts(value: str) -> list[tuple[float, str]]:
    contexts: list[tuple[float, str]] = []
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*%", value):
        start = max(0, match.start() - 40)
        end = min(len(value), match.end() + 40)
        contexts.append((float(match.group(1)), value[start:end]))
    return contexts


def _mentions_prestrain_context(value: str) -> bool:
    normalized = value.lower()
    return "pre-strain" in normalized or "prestrain" in normalized


def _has_actuation_strain_context(sentence: str, claim: str) -> bool:
    terms = {_stem(token) for token in _tokens(sentence)}
    claim_terms = {_stem(token) for token in _tokens(claim)}
    has_actuation = "actuat" in terms or "actuat" in claim_terms
    return has_actuation and "strain" in terms


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


def _stem(token: str) -> str:
    if token.startswith("actuat"):
        return "actuat"
    if token.startswith("strain"):
        return "strain"
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token
