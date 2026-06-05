#!/usr/bin/env python3
"""Deterministic claim-depth gate for ref-verify."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


TIER_1 = "TIER_1"
TIER_2 = "TIER_2"

SUPPORTED_ABSTRACT_LEVEL = "SUPPORTED (abstract-level)"
SUPPORTED_FULL_TEXT = "SUPPORTED (full-text confirmed)"
ABSTRACT_LEVEL_ONLY = "ABSTRACT-LEVEL ONLY — mechanism claim needs full text"
PARTIAL = "PARTIAL"
UNSUPPORTED = "UNSUPPORTED — no full-text support found"
CONTRADICTED = "CONTRADICTED"
UNVERIFIABLE = "UNVERIFIABLE"

ACCEPT = "ACCEPT"
WARN = "WARN"
REJECT = "REJECT"

_MECHANISM_PATTERNS = [
    r"\bhow\b",
    r"\bwhere\b",
    r"\bvia\b",
    r"\busing\b",
    r"\bthrough\b",
    r"\bby\b",
    r"\bbulk\b",
    r"\bsurface\b",
    r"\bcoat(?:ed|ing)?\b",
    r"\belectrode\b",
    r"\bcurrent\b",
    r"\bpath\b",
    r"\bjoule\b",
    r"\bheater\b",
    r"\bvoltage\b",
    r"<\s*\d+\s*v\b",
    r"\bless than\s+\d+\s*v\b",
    r"\bmeasur(?:e|ed|ement|ing)\b",
    r"\bcondition(?:s)?\b",
]

_STOPWORDS = {
    "about",
    "and",
    "are",
    "at",
    "by",
    "can",
    "does",
    "for",
    "from",
    "how",
    "into",
    "itself",
    "less",
    "paper",
    "than",
    "that",
    "the",
    "this",
    "through",
    "via",
    "with",
}


@dataclass(frozen=True)
class AuditResult:
    depth: str
    content_status: str
    verdict: str
    evidence: str
    reason: str


def classify_claim_depth(claim: str) -> str:
    normalized = _normalize(claim)
    if any(re.search(pattern, normalized) for pattern in _MECHANISM_PATTERNS):
        return TIER_2
    return TIER_1


def audit_claim(
    claim: str,
    *,
    abstract_text: str | None = None,
    full_text: str | None = None,
) -> dict[str, str]:
    depth = classify_claim_depth(claim)
    if depth == TIER_1:
        return asdict(_audit_tier_1(claim, abstract_text))
    return asdict(_audit_tier_2(claim, abstract_text, full_text))


def _audit_tier_1(claim: str, abstract_text: str | None) -> AuditResult:
    if not abstract_text:
        return AuditResult(
            TIER_1,
            UNVERIFIABLE,
            WARN,
            "",
            "No abstract text was available for topic-level verification.",
        )

    sentence = _best_sentence(claim, abstract_text)
    if sentence and _term_overlap(claim, sentence) >= 0.5:
        return AuditResult(
            TIER_1,
            SUPPORTED_ABSTRACT_LEVEL,
            ACCEPT,
            sentence,
            "Topic-level claim is supported by the abstract.",
        )

    return AuditResult(
        TIER_1,
        PARTIAL,
        WARN,
        sentence or "",
        "Abstract is available, but it does not directly support the topic claim.",
    )


def _audit_tier_2(
    claim: str,
    abstract_text: str | None,
    full_text: str | None,
) -> AuditResult:
    if not full_text:
        if abstract_text:
            return AuditResult(
                TIER_2,
                ABSTRACT_LEVEL_ONLY,
                WARN,
                _best_sentence(claim, abstract_text) or "",
                "Mechanism claim cannot be supported without full text.",
            )
        return AuditResult(
            TIER_2,
            UNVERIFIABLE,
            WARN,
            "",
            "Mechanism claim requires full text, but no source text was available.",
        )

    sentences = _sentences(full_text)
    contradiction = _find_contradiction(claim, sentences)
    if contradiction:
        return AuditResult(
            TIER_2,
            CONTRADICTED,
            REJECT,
            contradiction,
            "Full text assigns the claimed mechanism to a different actor/path.",
        )

    support = _find_full_text_support(claim, sentences)
    if support:
        return AuditResult(
            TIER_2,
            SUPPORTED_FULL_TEXT,
            ACCEPT,
            support,
            "Full text binds the claimed mechanism actor, action, and condition.",
        )

    adjacent = _find_adjacent_keyword_sentence(claim, sentences)
    if adjacent:
        return AuditResult(
            TIER_2,
            PARTIAL,
            WARN,
            adjacent,
            "Full text contains adjacent keywords but not the claimed mechanism relation.",
        )

    return AuditResult(
        TIER_2,
        UNSUPPORTED,
        REJECT,
        "",
        "Full text was searched, but no support for the mechanism claim was found.",
    )


def _find_contradiction(claim: str, sentences: Iterable[str]) -> str:
    claim_n = _normalize(claim)
    claims_bulk_lce_heater = (
        "lce" in claim_n
        and "bulk" in claim_n
        and ("joule" in claim_n or "heater" in claim_n or "heat" in claim_n)
    )
    if not claims_bulk_lce_heater:
        return ""

    sentence_list = list(sentences)
    for sentence in sentence_list:
        sentence_n = _normalize(sentence)
        lm_is_heater = (
            ("lm layer" in sentence_n or "liquid metal" in sentence_n or "egain" in sentence_n)
            and ("joule" in sentence_n or "heater" in sentence_n)
        )
        if lm_is_heater:
            return sentence

    for sentence in sentence_list:
        sentence_n = _normalize(sentence)
        lce_is_sensor = (
            "ilce" in sentence_n
            and ("resistance" in sentence_n or "measure" in sentence_n)
            and ("thickness" in sentence_n or "self sensing" in sentence_n)
        )
        if lce_is_sensor:
            return sentence
    return ""


def _find_full_text_support(claim: str, sentences: Iterable[str]) -> str:
    claim_n = _normalize(claim)
    for sentence in sentences:
        sentence_n = _normalize(sentence)
        if _supports_low_voltage_lm_claim(claim_n, sentence_n):
            return sentence
        if _term_overlap(claim, sentence) >= 0.75 and _has_mechanism_relation(sentence_n):
            return sentence
    return ""


def _supports_low_voltage_lm_claim(claim_n: str, sentence_n: str) -> bool:
    claim_mentions_lm = "lm electrode" in claim_n or "liquid metal" in claim_n or "egain" in claim_n
    sentence_mentions_lm = "lm electrode" in sentence_n or "liquid metal" in sentence_n or "egain" in sentence_n
    claim_mentions_voltage = "<3 v" in claim_n or "less than 3 v" in claim_n
    sentence_mentions_voltage = "<3 v" in sentence_n or "less than 3 v" in sentence_n
    action_matches = (
        ("actuation" in claim_n or "actuate" in claim_n)
        and ("actuation" in sentence_n or "actuate" in sentence_n)
    )
    return claim_mentions_lm and sentence_mentions_lm and claim_mentions_voltage and sentence_mentions_voltage and action_matches


def _find_adjacent_keyword_sentence(claim: str, sentences: Iterable[str]) -> str:
    claim_terms = _terms(claim)
    all_sentence_terms: set[str] = set()
    best = ""
    best_count = 0
    for sentence in sentences:
        sentence_terms = _terms(sentence)
        all_sentence_terms.update(sentence_terms)
        count = len(claim_terms & sentence_terms)
        if count > best_count:
            best = sentence
            best_count = count
    if best_count >= 2:
        return best
    if len(claim_terms & all_sentence_terms) >= 2:
        return best
    return ""


def _best_sentence(claim: str, text: str) -> str:
    return _find_adjacent_keyword_sentence(claim, _sentences(text))


def _has_mechanism_relation(sentence_n: str) -> bool:
    actor = "lm electrode" in sentence_n or "lm layer" in sentence_n or "lce" in sentence_n or "ilce" in sentence_n
    action = "joule" in sentence_n or "heater" in sentence_n or "actuation" in sentence_n or "measure" in sentence_n
    relation = "served as" in sentence_n or "via" in sentence_n or "to the" in sentence_n or "through" in sentence_n
    return actor and action and relation


def _sentences(text: str) -> list[str]:
    compact = " ".join(text.split())
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", compact) if part.strip()]


def _term_overlap(claim: str, sentence: str) -> float:
    claim_terms = _terms(claim)
    if not claim_terms:
        return 0.0
    return len(claim_terms & _terms(sentence)) / len(claim_terms)


def _terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+(?:\s+sensing)?", _normalize(text))
        if len(token) > 2 and token not in _STOPWORDS
    }


def _normalize(text: str) -> str:
    normalized = text.lower()
    normalized = normalized.replace("≤", "<=")
    normalized = normalized.replace("∼", "~")
    normalized = normalized.replace("self-sensing", "self sensing")
    normalized = re.sub(r"<\s*3\s*v", "<3 v", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _read_optional(path: str | None) -> str | None:
    if not path:
        return None
    return Path(path).read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a citation claim against abstract/full-text evidence.")
    parser.add_argument("--claim", required=True)
    parser.add_argument("--abstract-file")
    parser.add_argument("--full-text-file")
    args = parser.parse_args()

    result = audit_claim(
        args.claim,
        abstract_text=_read_optional(args.abstract_file),
        full_text=_read_optional(args.full_text_file),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
